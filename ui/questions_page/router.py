import datetime
import logging
import re

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

import config
from core.db import crud
from core.db.session import SessionLocal, get_session
from core.providers.factory import get_llm_provider
from core.questions.pipeline import (
    classify_template_category,
    generate_cover_letter_answers,
    generate_general_answers_initial,
    generate_summary_answers,
    run_advisor_chat,
    run_targeted_revision,
    split_and_prepare_questions,
)
from core.rendering.plain_text_export import render_plain_text_to_docx, render_plain_text_to_pdf
from core.tasks.runner import run_tracked_task
from ui.common.i18n import get_language, load_page_strings

router = APIRouter(prefix="/questions")

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="ui/questions_page/templates")
templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader("ui/questions_page/templates"),
        FileSystemLoader("ui/common/templates"),
    ]
)

_DOWNLOAD_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def _filename_segment(value: str | None, fallback: str) -> str:
    value = (value or "").strip() or fallback
    cleaned = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "-", cleaned.strip())
    return cleaned or fallback


def _serialize_question(question) -> dict:
    return {
        "id": question.id,
        "question_text": question.question_text,
        "category": question.category,
        "char_limit": question.char_limit,
        "answer_text": question.answer_text,
        "needs_manual_input": question.needs_manual_input,
        "flag_reason": question.flag_reason,
        "pending_task_id": question.pending_task_id,
        "template_label": question.template_label,
    }


def _serialize_chat_message(message) -> dict:
    return {
        "id": message.id,
        "role": message.role,
        "text": message.text,
        "referenced_question_id": message.referenced_question_id,
    }


def _serialize_change(change) -> dict:
    return {
        "id": change.id,
        "question_id": change.question_id,
        "original_text": change.original_text,
        "proposed_text": change.proposed_text,
        "status": change.status,
    }


def _gather_context(session: Session, application_id: int) -> dict:
    application = crud.get_application(session, application_id)
    job = crud.get_job_posting(session, application.job_posting_id)
    resume = crud.get_active_resume_version(session, "resume")
    linkedin = crud.get_active_resume_version(session, "linkedin")
    profile = crud.get_candidate_profile(session)

    links = []
    if profile:
        if profile.github_url:
            links.append(profile.github_url)
        if profile.linkedin_url:
            links.append(profile.linkedin_url)
        links.extend(profile.extra_links or [])

    return {
        "application": application,
        "job": job,
        "job_posting_text": job.raw_text if job else "",
        "resume_text": resume.raw_text if resume else "",
        "linkedin_text": linkedin.raw_text if linkedin else "",
        "extra_info": profile.extra_info if profile else None,
        "writing_preferences": profile.writing_preferences if profile else None,
        "links": links,
    }


def _build_unified_history(
    session: Session, application_id: int, exclude_message_id: int | None = None, max_chars: int = 6000
) -> list[dict]:
    questions = crud.list_form_questions_for_application(session, application_id)
    changes = crud.list_changes_for_application(session, application_id)
    chat_messages = crud.list_chat_messages(session, application_id)

    events: list[tuple] = []

    for message in chat_messages:
        if message.id == exclude_message_id:
            continue
        tag = f"[id={message.referenced_question_id}] " if message.referenced_question_id else ""
        events.append((message.created_at, f"{tag}{message.role}: {message.text}"))

    known_text: dict[int, str] = {}

    for change in changes:
        events.append(
            (
                change.created_at,
                f"[id={change.question_id}] агент-технически: изменил \"{(change.original_text or '')[:300]}\" "
                f"на \"{(change.proposed_text or '')[:300]}\"",
            )
        )
        if change.status in ("approved", "rejected") and change.resolved_at:
            action = "Apply" if change.status == "approved" else "Skip"
            events.append(
                (change.resolved_at, f"[id={change.question_id}] пользователь-технически: нажал {action}")
            )
        if change.status == "approved":
            known_text[change.question_id] = change.proposed_text
        elif change.question_id not in known_text:
            known_text[change.question_id] = change.original_text

    now = datetime.datetime.utcnow()
    for question in questions:
        baseline = known_text.get(question.id)
        current = question.answer_text or ""
        if baseline is not None and current != baseline:
            events.append(
                (now, f"[id={question.id}] пользователь-технически: поменял текст на \"{current[:500]}\"")
            )

    events.sort(key=lambda item: item[0] or now)
    lines = [text for _, text in events]

    total = 0
    trimmed: list[str] = []
    for line in reversed(lines):
        total += len(line)
        if total > max_chars:
            break
        trimmed.append(line)
    trimmed.reverse()

    return [{"role": "system", "text": line} for line in trimmed]


def _job_side_info(session: Session, job) -> dict:
    if job is None:
        return {"score": None, "location": None, "work_mode": None, "salary": {}, "summary": None}

    evaluations = crud.list_evaluations_for_job(session, job.id)
    latest_evaluation = evaluations[0] if evaluations else None
    checked = (latest_evaluation.checked_keywords or {}) if latest_evaluation else {}

    return {
        "score": latest_evaluation.fit_score if latest_evaluation else None,
        "location": checked.get("location") or job.location,
        "work_mode": checked.get("work_mode") or job.work_mode,
        "salary": checked.get("salary") or {},
        "summary": checked.get("summary"),
    }


@router.get("", response_class=HTMLResponse)
def questions_page(
    request: Request,
    application_id: int,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    application = crud.get_application(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    job = crud.get_job_posting(session, application.job_posting_id)
    questions = crud.list_form_questions_for_application(session, application_id)
    chat_messages = crud.list_chat_messages(session, application_id)
    changes = crud.list_changes_for_application(session, application_id)
    profile = crud.get_candidate_profile(session)

    return templates.TemplateResponse(
        "questions.html",
        {
            "request": request,
            "application": application,
            "job": job,
            "questions": [_serialize_question(q) for q in questions],
            "chat_messages": [_serialize_chat_message(m) for m in chat_messages],
            "changes": [_serialize_change(c) for c in changes],
            "writing_preferences": profile.writing_preferences if profile else None,
            **_job_side_info(session, job),
            "lang": lang,
            "t": load_page_strings("ui/questions_page", lang),
        },
    )


@router.post("/application/{application_id}/submit")
def submit_questions(
    application_id: int,
    raw_text: str = Form(...),
    session: Session = Depends(get_session),
):
    application = crud.get_application(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    task_id = run_tracked_task("questions_split", _run_split_only, application_id, raw_text)
    return JSONResponse({"task_id": task_id})


def _run_split_only(application_id: int, raw_text: str) -> dict:
    session = SessionLocal()
    try:
        logger.info("[app %s] splitting questions from pasted text (%s chars)", application_id, len(raw_text))

        provider = get_llm_provider()
        prepared = split_and_prepare_questions(provider, raw_text=raw_text)

        logger.info("[app %s] split result: %s questions found: %s", application_id, len(prepared), [q["question_text"][:60] for q in prepared])

        existing_count = len(crud.list_form_questions_for_application(session, application_id))
        created = crud.bulk_create_form_questions(session, application_id, prepared, order_offset=existing_count)

        if not created:
            logger.warning("[app %s] no qualifying open-ended questions extracted from pasted text", application_id)
            return {"questions": []}

        app_settings = crud.get_app_settings(session)
        auto_answer_enabled = app_settings.auto_answer_questions_enabled if app_settings else True

        if not auto_answer_enabled:
            logger.info("[app %s] auto-answer disabled in settings, leaving %s questions unanswered", application_id, len(created))
            return {"questions": [_serialize_question(q) for q in created]}

        by_category: dict[str, list] = {"cover_letter": [], "summary": [], "general": []}
        for question in created:
            by_category.setdefault(question.category or "general", []).append(question)

        for category, questions_in_category in by_category.items():
            if not questions_in_category:
                continue
            logger.info(
                "[app %s] launching generation task for category=%s, %s questions",
                application_id, category, len(questions_in_category),
            )
            gen_task_id = run_tracked_task(
                f"questions_generate_{category}",
                _run_generate_category,
                application_id,
                category,
                [q.id for q in questions_in_category],
            )
            for question in questions_in_category:
                crud.set_question_pending_task(session, question.id, gen_task_id)

        stub_questions = [crud.get_form_question(session, question.id) for question in created]

        return {"questions": [_serialize_question(q) for q in stub_questions]}
    finally:
        session.close()


def _run_generate_category(application_id: int, category: str, question_ids: list[int]) -> dict:
    session = SessionLocal()
    try:
        application = crud.get_application(session, application_id)
        if application is not None:
            crud.set_job_activity(session, application.job_posting_id, "Answering application questions...")

        questions = [q for q in (crud.get_form_question(session, qid) for qid in question_ids) if q is not None]
        if not questions:
            logger.warning("[app %s] generate_category(%s): no matching questions found for ids=%s", application_id, category, question_ids)
            if application is not None:
                crud.set_job_activity(session, application.job_posting_id, None)
            return {"questions": []}

        context = _gather_context(session, application_id)
        logger.info(
            "[app %s] generate_category(%s): resume_len=%s linkedin_len=%s job_text_len=%s",
            application_id, category, len(context["resume_text"]), len(context["linkedin_text"]), len(context["job_posting_text"]),
        )
        provider = get_llm_provider()

        payload = [
            {
                "id": q.id,
                "question_text": q.question_text,
                "char_limit": q.char_limit,
                "template_instructions": q.template_instructions,
            }
            for q in questions
        ]

        if category == "cover_letter":
            answers_by_id = generate_cover_letter_answers(
                provider,
                payload,
                job_posting_text=context["job_posting_text"],
                resume_text=context["resume_text"],
                linkedin_text=context["linkedin_text"],
                extra_info=context["extra_info"],
                writing_preferences=context["writing_preferences"],
                links=context["links"],
            )
        elif category == "summary":
            answers_by_id = generate_summary_answers(
                provider,
                payload,
                job_posting_text=context["job_posting_text"],
                resume_text=context["resume_text"],
                linkedin_text=context["linkedin_text"],
                extra_info=context["extra_info"],
                writing_preferences=context["writing_preferences"],
                links=context["links"],
            )
        else:
            answers_by_id = generate_general_answers_initial(
                provider,
                payload,
                job_posting_text=context["job_posting_text"],
                resume_text=context["resume_text"],
                linkedin_text=context["linkedin_text"],
                extra_info=context["extra_info"],
                writing_preferences=context["writing_preferences"],
                links=context["links"],
            )

        logger.info("[app %s] generate_category(%s): got answers for %s/%s questions", application_id, category, len(answers_by_id), len(questions))

        updated_questions = []
        for question in questions:
            result = answers_by_id.get(question.id)
            if result is None:
                logger.warning("[app %s] question %s: no answer returned by LLM, leaving unanswered", application_id, question.id)
                crud.set_question_pending_task(session, question.id, None)
                continue
            updated = crud.set_question_generation_result(
                session,
                question.id,
                answer_text=result["answer_text"],
                selected_option=None,
                needs_manual_input=result["needs_manual_input"],
                flag_reason=result["flag_reason"],
            )
            crud.set_question_pending_task(session, question.id, None)
            updated_questions.append(updated)

        if application is not None:
            crud.set_job_activity(session, application.job_posting_id, None)

        return {"questions": [_serialize_question(q) for q in updated_questions]}
    finally:
        session.close()


@router.post("/application/{application_id}/manual")
def add_manual_question(
    application_id: int,
    question_text: str = Form(...),
    category: str = Form(""),
    char_limit: str = Form(""),
    session: Session = Depends(get_session),
):
    application = crud.get_application(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    text = question_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Question text cannot be empty")

    resolved_category = category.strip()
    if resolved_category not in ("cover_letter", "summary", "general"):
        provider = get_llm_provider()
        resolved_category = classify_template_category(provider, text)

    parsed_char_limit = int(char_limit) if char_limit.strip().isdigit() else None
    existing_count = len(crud.list_form_questions_for_application(session, application_id))

    question = crud.create_form_question(
        session,
        application_id=application_id,
        question_text=text,
        answer_type="document",
        category=resolved_category,
        char_limit=parsed_char_limit,
        order=existing_count,
    )

    app_settings = crud.get_app_settings(session)
    auto_answer_enabled = app_settings.auto_answer_questions_enabled if app_settings else True

    task_id = None
    if auto_answer_enabled:
        task_id = run_tracked_task(
            f"questions_generate_{resolved_category}",
            _run_generate_category,
            application_id,
            resolved_category,
            [question.id],
        )
        crud.set_question_pending_task(session, question.id, task_id)
        question = crud.get_form_question(session, question.id)

    return JSONResponse({"question": _serialize_question(question), "task_id": task_id})


@router.post("/{question_id}/answer")
def update_answer(
    question_id: int,
    answer_text: str = Form(""),
    session: Session = Depends(get_session),
):
    question = crud.update_form_question_answer(session, question_id, answer_text=answer_text or None)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return JSONResponse({"status": "ok"})


@router.post("/{question_id}/delete")
def delete_question(question_id: int, session: Session = Depends(get_session)):
    crud.delete_form_question(session, question_id)
    return JSONResponse({"status": "ok"})


@router.post("/application/{application_id}/chat")
def send_chat_message(
    application_id: int,
    user_message: str = Form(...),
    question_id: str = Form(""),
    session: Session = Depends(get_session),
):
    application = crud.get_application(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    selected_id = int(question_id) if question_id.strip().isdigit() else None

    user_msg = crud.create_chat_message(
        session, application_id, role="user", text=user_message, referenced_question_id=selected_id
    )

    task_id = run_tracked_task(
        "application_chat_turn", _run_chat_turn, application_id, user_message, selected_id, user_msg.id
    )
    return JSONResponse({"task_id": task_id})


def _run_chat_turn(
    application_id: int, user_message: str, selected_question_id: int | None, user_msg_id: int
) -> dict:
    session = SessionLocal()
    try:
        context = _gather_context(session, application_id)
        provider = get_llm_provider()
        history_dicts = _build_unified_history(session, application_id, exclude_message_id=user_msg_id)

        if selected_question_id is None:
            questions = crud.list_form_questions_for_application(session, application_id)

            reply_text = run_advisor_chat(
                provider,
                user_message=user_message,
                conversation_history=history_dicts,
                questions=[
                    {
                        "id": q.id,
                        "question_text": q.question_text,
                        "category": q.category,
                        "answer_text": q.answer_text,
                    }
                    for q in questions
                ],
                job_posting_text=context["job_posting_text"],
                resume_text=context["resume_text"],
                linkedin_text=context["linkedin_text"],
                extra_info=context["extra_info"],
            )

            assistant_msg = crud.create_chat_message(session, application_id, role="assistant", text=reply_text)
            return {"message_id": assistant_msg.id, "message": reply_text, "change": None}

        question = crud.get_form_question(session, selected_question_id)
        if question is None:
            reply_text = "That question no longer exists."
            assistant_msg = crud.create_chat_message(session, application_id, role="assistant", text=reply_text)
            return {"message_id": assistant_msg.id, "message": reply_text, "change": None}

        current_answer = question.answer_text or "(no answer yet)"

        result = run_targeted_revision(
            provider,
            category=question.category or "general",
            question_text=question.question_text,
            current_answer=current_answer,
            user_message=user_message,
            conversation_history=history_dicts,
            job_posting_text=context["job_posting_text"],
            resume_text=context["resume_text"],
            linkedin_text=context["linkedin_text"],
            char_limit=question.char_limit,
            extra_info=context["extra_info"],
            links=context["links"],
        )

        assistant_msg = crud.create_chat_message(
            session, application_id, role="assistant", text=result["message"], referenced_question_id=question.id
        )

        change = None
        if result["answer_text"] is not None:
            created_change = crud.create_question_change(
                session,
                question_id=question.id,
                chat_message_id=assistant_msg.id,
                original_text=question.answer_text or "",
                proposed_text=result["answer_text"],
            )
            change = _serialize_change(created_change)
        else:
            crud.set_question_generation_result(
                session,
                question.id,
                answer_text=question.answer_text,
                selected_option=None,
                needs_manual_input=True,
                flag_reason=result["flag_reason"],
            )

        return {"message_id": assistant_msg.id, "message": result["message"], "change": change}
    finally:
        session.close()


@router.post("/changes/{change_id}/resolve")
def resolve_change(
    change_id: int,
    action: str = Form(...),
    session: Session = Depends(get_session),
):
    change = crud.get_question_change(session, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")

    if action == "approve":
        crud.update_form_question_answer(session, change.question_id, answer_text=change.proposed_text)
        crud.set_question_generation_result(
            session,
            change.question_id,
            answer_text=change.proposed_text,
            selected_option=None,
            needs_manual_input=False,
            flag_reason=None,
        )
        crud.resolve_question_change(session, change_id, status="approved")
    elif action == "reject":
        crud.resolve_question_change(session, change_id, status="rejected")
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    return JSONResponse({"status": "ok"})


@router.get("/{question_id}/download")
def download_answer(
    question_id: int,
    format: str = "docx",
    session: Session = Depends(get_session),
):
    if format not in _DOWNLOAD_MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported format")

    question = crud.get_form_question(session, question_id)
    if question is None or not question.answer_text:
        raise HTTPException(status_code=404, detail="No answer to download")

    application = crud.get_application(session, question.application_id)
    job = crud.get_job_posting(session, application.job_posting_id)
    profile = crud.get_candidate_profile(session)

    name_part = _filename_segment(profile.full_name if profile else None, "Answer")
    doc_part = _filename_segment(question.category or "Document", "Document")
    company_part = _filename_segment(job.company if job else None, "Company")

    output_filename = f"{name_part}_{doc_part}_{company_part}.{format}"
    output_path = str(config.OUTPUT_DIR / output_filename)

    if format == "docx":
        render_plain_text_to_docx(question.answer_text, output_path)
    else:
        render_plain_text_to_pdf(question.answer_text, output_path)

    return FileResponse(output_path, media_type=_DOWNLOAD_MEDIA_TYPES[format], filename=output_filename)