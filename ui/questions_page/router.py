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
        "links": links,
    }


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

    return templates.TemplateResponse(
        "questions.html",
        {
            "request": request,
            "application": application,
            "job": job,
            "questions": [_serialize_question(q) for q in questions],
            "chat_messages": [_serialize_chat_message(m) for m in chat_messages],
            "changes": [_serialize_change(c) for c in changes],
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

    task_id = run_tracked_task("questions_split", _run_split_and_generate, application_id, raw_text)
    return JSONResponse({"task_id": task_id})


def _run_split_and_generate(application_id: int, raw_text: str) -> dict:
    session = SessionLocal()
    try:
        provider = get_llm_provider()
        prepared = split_and_prepare_questions(provider, raw_text=raw_text)

        existing_count = len(crud.list_form_questions_for_application(session, application_id))
        created = crud.bulk_create_form_questions(session, application_id, prepared, order_offset=existing_count)

        context = _gather_context(session, application_id)

        by_category: dict[str, list] = {"cover_letter": [], "summary": [], "general": []}
        for question in created:
            by_category.setdefault(question.category or "general", []).append(question)

        answers_by_id: dict[int, dict] = {}

        if by_category["cover_letter"]:
            payload = [
                {"id": q.id, "question_text": q.question_text, "char_limit": q.char_limit}
                for q in by_category["cover_letter"]
            ]
            answers_by_id.update(
                generate_cover_letter_answers(
                    provider,
                    payload,
                    job_posting_text=context["job_posting_text"],
                    resume_text=context["resume_text"],
                    linkedin_text=context["linkedin_text"],
                    extra_info=context["extra_info"],
                    links=context["links"],
                )
            )

        if by_category["summary"]:
            payload = [
                {"id": q.id, "question_text": q.question_text, "char_limit": q.char_limit}
                for q in by_category["summary"]
            ]
            answers_by_id.update(
                generate_summary_answers(
                    provider,
                    payload,
                    job_posting_text=context["job_posting_text"],
                    resume_text=context["resume_text"],
                    linkedin_text=context["linkedin_text"],
                    extra_info=context["extra_info"],
                    links=context["links"],
                )
            )

        if by_category["general"]:
            payload = [
                {"id": q.id, "question_text": q.question_text, "char_limit": q.char_limit}
                for q in by_category["general"]
            ]
            answers_by_id.update(
                generate_general_answers_initial(
                    provider,
                    payload,
                    job_posting_text=context["job_posting_text"],
                    resume_text=context["resume_text"],
                    linkedin_text=context["linkedin_text"],
                    extra_info=context["extra_info"],
                    links=context["links"],
                )
            )

        updated_questions = []
        for question in created:
            result = answers_by_id.get(question.id)
            if result is None:
                continue
            updated = crud.set_question_generation_result(
                session,
                question.id,
                answer_text=result["answer_text"],
                selected_option=None,
                needs_manual_input=result["needs_manual_input"],
                flag_reason=result["flag_reason"],
            )
            crud.create_question_change(
                session,
                question_id=question.id,
                chat_message_id=None,
                original_text="",
                proposed_text=result["answer_text"] or "",
            )
            updated_questions.append(updated)

        return {"questions": [_serialize_question(q) for q in updated_questions]}
    finally:
        session.close()


@router.post("/application/{application_id}/manual")
def add_manual_question(
    application_id: int,
    question_text: str = Form(...),
    category: str = Form("general"),
    char_limit: str = Form(""),
    session: Session = Depends(get_session),
):
    application = crud.get_application(session, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    if category not in ("cover_letter", "summary", "general"):
        category = "general"

    parsed_char_limit = int(char_limit) if char_limit.strip().isdigit() else None
    existing_count = len(crud.list_form_questions_for_application(session, application_id))

    question = crud.create_form_question(
        session,
        application_id=application_id,
        question_text=question_text,
        answer_type="document",
        category=category,
        char_limit=parsed_char_limit,
        order=existing_count,
    )

    return JSONResponse({"question": _serialize_question(question)})


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

        if selected_question_id is None:
            questions = crud.list_form_questions_for_application(session, application_id)
            history = crud.list_chat_messages(session, application_id)
            history_dicts = [{"role": m.role, "text": m.text} for m in history if m.id != user_msg_id]

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

        history = crud.list_chat_messages(session, application_id)
        changes_for_question = {
            c.chat_message_id: c
            for c in crud.list_changes_for_application(session, application_id)
            if c.question_id == question.id
        }

        history_dicts = []
        for m in history:
            if m.id == user_msg_id:
                continue
            if m.referenced_question_id != question.id:
                continue
            entry = {"role": m.role, "text": m.text}
            change = changes_for_question.get(m.id)
            if change:
                entry["change_status"] = change.status
            history_dicts.append(entry)

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