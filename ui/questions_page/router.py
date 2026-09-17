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
from core.questions.pipeline import process_pasted_questions
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
        "answer_type": question.answer_type,
        "category": question.category,
        "answer_text": question.answer_text,
        "needs_manual_input": question.needs_manual_input,
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

    return templates.TemplateResponse(
        "questions.html",
        {
            "request": request,
            "application": application,
            "job": job,
            "questions": [_serialize_question(q) for q in questions],
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

    task_id = run_tracked_task("questions_process", _run_process_questions, application_id, raw_text)
    return JSONResponse({"task_id": task_id})


def _run_process_questions(application_id: int, raw_text: str) -> dict:
    session = SessionLocal()
    try:
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

        provider = get_llm_provider()
        results = process_pasted_questions(
            provider,
            raw_text=raw_text,
            job_posting_text=job.raw_text,
            resume_text=resume.raw_text if resume else "",
            linkedin_text=linkedin.raw_text if linkedin else "",
            extra_info=profile.extra_info if profile else None,
            links=links,
        )

        created = crud.bulk_create_form_questions(session, application_id, results)

        return {"questions": [_serialize_question(q) for q in created]}
    finally:
        session.close()


@router.post("/{question_id}/answer")
def update_answer(
    question_id: int,
    answer_text: str = Form(...),
    session: Session = Depends(get_session),
):
    question = crud.update_form_question_answer(session, question_id, answer_text=answer_text)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return JSONResponse({"status": "ok"})


@router.post("/{question_id}/delete")
def delete_question(question_id: int, session: Session = Depends(get_session)):
    crud.delete_form_question(session, question_id)
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