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
from core.parsing.html_sanitize import sanitize_html
from core.providers.factory import get_llm_provider
from core.rendering.docx_renderer import render_html_export_to_docx
from core.rendering.pdf_renderer import render_html_export_to_pdf
from core.rendering.txt_renderer import render_html_export_to_txt
from core.tailoring.fragment_pipeline import (
    propose_medium_fragment_changes,
    propose_soft_fragment_changes,
    run_agent_fragment_turn,
)
from core.tailoring.html_diff import apply_fragment, strip_marks, wrap_highlights
from core.tailoring.keyword_extraction import extract_tailoring_keywords
from core.tasks.runner import run_tracked_task
from ui.common.i18n import get_language, load_page_strings

_DOWNLOAD_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "txt": "text/plain",
}

router = APIRouter(prefix="/tailor")

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="ui/tailoring_page/templates")
templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader("ui/tailoring_page/templates"),
        FileSystemLoader("ui/common/templates"),
    ]
)


def _get_matched_factors(session: Session, job_posting_id: int) -> list[dict]:
    evaluations = crud.list_evaluations_for_job(session, job_posting_id)
    if not evaluations:
        return []
    return (evaluations[0].checked_keywords or {}).get("matched_factors", [])


def _get_job_context(session: Session, job_posting_id: int) -> dict:
    evaluations = crud.list_evaluations_for_job(session, job_posting_id)
    latest_evaluation = evaluations[0] if evaluations else None
    checked = (latest_evaluation.checked_keywords or {}) if latest_evaluation else {}
    salary = checked.get("salary") or {}

    return {
        "score": latest_evaluation.fit_score if latest_evaluation else None,
        "location": checked.get("location"),
        "work_mode": checked.get("work_mode"),
        "salary": salary,
        "summary": checked.get("summary"),
    }


def _serialize_change(change) -> dict:
    return {
        "id": change.id,
        "level": change.level,
        "change_type": change.change_type,
        "original_text": change.original_text,
        "proposed_text": change.proposed_text,
        "status": change.status,
        "message_id": change.message_id,
    }


def _get_or_create_session(session: Session, job_id: int):
    tailoring_session = crud.get_tailoring_session_for_job(session, job_id)
    if tailoring_session is not None:
        return tailoring_session

    resume = crud.get_active_resume_version(session, "resume")
    if resume is None or not resume.content_html:
        raise HTTPException(
            status_code=400,
            detail="No active resume HTML found. Upload and parse a resume in Settings first.",
        )

    return crud.create_tailoring_session(
        session,
        job_posting_id=job_id,
        resume_version_id=resume.id,
        working_content={},
        working_html=resume.content_html,
    )


def _ensure_keywords(session: Session, tailoring_session, job, provider=None) -> list[dict]:
    if tailoring_session.extracted_keywords:
        return tailoring_session.extracted_keywords

    provider = provider or get_llm_provider()
    keywords = extract_tailoring_keywords(provider, job.raw_text)
    crud.update_extracted_keywords(session, tailoring_session.id, keywords)
    return keywords


def _keyword_texts(keywords: list[dict]) -> list[str]:
    return [k["text"] for k in keywords]


def _soft_message_text(lang: str) -> str:
    return (
        "Soft-изменения: заголовок, названия должностей и подбор скиллов под вакансию "
        "(только терминология, ничего не переписывается по сути)."
        if lang == "ru"
        else "Soft changes: title, job titles and skills selection matched to the posting "
        "(terminology only, nothing rewritten in substance)."
    )


def _medium_message_text(lang: str) -> str:
    return (
        "Medium-изменения: точечные правки summary и experience под ключевые слова вакансии "
        "(добавляем нужные слова в нужные места, не переписываем сильно)."
        if lang == "ru"
        else "Medium changes: targeted summary/experience edits weaving in the posting's keywords "
        "(words inserted in the right places, not a heavy rewrite)."
    )


def _store_changes_with_dedup(
    session: Session, session_id: int, message_id: int, changes: list[dict]
) -> tuple[list, list]:
    originals = {c["original_text"] for c in changes if c.get("original_text")}
    superseded = crud.supersede_pending_changes_by_original(session, session_id, originals)
    created = crud.bulk_create_session_changes(session, session_id, message_id, changes)
    return created, superseded


def _pending_changes_for_render(session: Session, session_id: int) -> list[dict]:
    changes = crud.list_tailoring_changes_for_session(session, session_id)
    return [_serialize_change(c) for c in changes if c.status == "pending"]


def _approved_changes_for_render(session: Session, session_id: int) -> list[dict]:
    changes = crud.list_tailoring_changes_for_session(session, session_id)
    return [_serialize_change(c) for c in changes if c.status == "approved"]


def _render_working_html(session: Session, tailoring_session) -> str:
    pending = _pending_changes_for_render(session, tailoring_session.id)
    approved = _approved_changes_for_render(session, tailoring_session.id)
    highlighted_html = wrap_highlights(tailoring_session.working_html or "", pending)
    highlighted_html = wrap_highlights(
        highlighted_html, approved, search_field="proposed_text", css_class="approved-mark"
    )
    return highlighted_html


def pregenerate_tailoring_context(job_posting_id: int, lang: str = "en") -> None:
    """Runs keyword extraction + soft + medium proposals ahead of time, right after a
    high-scoring evaluation, so the tailoring page opens already populated. Guarded by
    the app_settings pregenerate toggle and min-score threshold - see evaluator_page router."""
    session = SessionLocal()
    try:
        resume = crud.get_active_resume_version(session, "resume")
        if resume is None or not resume.content_html:
            logger.warning(
                "[job %s] pregenerate skipped: no active resume with content_html", job_posting_id
            )
            return

        tailoring_session = crud.get_tailoring_session_for_job(session, job_posting_id)
        if tailoring_session is None:
            tailoring_session = crud.create_tailoring_session(
                session,
                job_posting_id=job_posting_id,
                resume_version_id=resume.id,
                working_content={},
                working_html=resume.content_html,
            )

        if crud.list_tailoring_messages(session, tailoring_session.id):
            logger.info("[job %s] pregenerate skipped: session already has messages", job_posting_id)
            return

        logger.info("[job %s] pregenerate: starting soft + medium proposals", job_posting_id)

        job = crud.get_job_posting(session, job_posting_id)
        if job is None:
            return

        matched_factors = _get_matched_factors(session, job_posting_id)
        provider = get_llm_provider()
        keywords = _ensure_keywords(session, tailoring_session, job, provider=provider)
        keyword_texts = _keyword_texts(keywords)

        soft_changes = propose_soft_fragment_changes(
            provider,
            job_posting_text=job.raw_text,
            resume_html=tailoring_session.working_html or "",
            matched_factors=matched_factors,
            keywords=keyword_texts,
        )
        soft_message = crud.create_tailoring_message(
            session, tailoring_session.id, role="assistant", text=_soft_message_text(lang)
        )
        _store_changes_with_dedup(session, tailoring_session.id, soft_message.id, soft_changes)

        medium_changes = propose_medium_fragment_changes(
            provider,
            job_posting_text=job.raw_text,
            resume_html=tailoring_session.working_html or "",
            matched_factors=matched_factors,
            keywords=keyword_texts,
        )
        medium_message = crud.create_tailoring_message(
            session, tailoring_session.id, role="assistant", text=_medium_message_text(lang)
        )
        _store_changes_with_dedup(session, tailoring_session.id, medium_message.id, medium_changes)
    finally:
        session.close()


@router.get("", response_class=HTMLResponse)
def tailor_page(
    request: Request,
    job_id: int,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    job = crud.get_job_posting(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    tailoring_session = _get_or_create_session(session, job_id)
    highlighted_html = _render_working_html(session, tailoring_session)

    messages = crud.list_tailoring_messages(session, tailoring_session.id)
    changes = crud.list_tailoring_changes_for_session(session, tailoring_session.id)

    changes_by_message: dict[int, list[dict]] = {}
    for change in changes:
        changes_by_message.setdefault(change.message_id, []).append(_serialize_change(change))

    job_context = _get_job_context(session, job_id)

    return templates.TemplateResponse(
        "tailor.html",
        {
            "request": request,
            "job": job,
            "session_id": tailoring_session.id,
            "resume_html": highlighted_html,
            "messages": messages,
            "changes_by_message": changes_by_message,
            "keywords": tailoring_session.extracted_keywords or [],
            **job_context,
            "lang": lang,
            "t": load_page_strings("ui/tailoring_page", lang),
        },
    )


@router.post("/session/{session_id}/extract-keywords")
def extract_keywords(
    session_id: int,
    session: Session = Depends(get_session),
):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if tailoring_session.extracted_keywords:
        return JSONResponse({"task_id": None, "keywords": tailoring_session.extracted_keywords})

    task_id = run_tracked_task("tailoring_keywords", _run_extract_keywords, session_id)
    return JSONResponse({"task_id": task_id})


def _run_extract_keywords(session_id: int) -> dict:
    session = SessionLocal()
    try:
        tailoring_session = crud.get_tailoring_session(session, session_id)
        job = crud.get_job_posting(session, tailoring_session.job_posting_id)

        provider = get_llm_provider()
        keywords = _ensure_keywords(session, tailoring_session, job, provider=provider)

        return {"keywords": keywords}
    finally:
        session.close()


def _filename_segment(value: str | None, fallback: str) -> str:
    value = (value or "").strip() or fallback
    cleaned = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "-", cleaned.strip())
    return cleaned or fallback


@router.get("/session/{session_id}/download")
def download_resume(
    session_id: int,
    format: str = "docx",
    session: Session = Depends(get_session),
):
    if format not in _DOWNLOAD_MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported format")

    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    job = crud.get_job_posting(session, tailoring_session.job_posting_id)
    profile = crud.get_candidate_profile(session)
    html_content = strip_marks(tailoring_session.working_html or "")

    name_part = _filename_segment(profile.full_name if profile else None, "Resume")
    role_part = _filename_segment(job.title if job else None, "Role")
    company_part = _filename_segment(job.company if job else None, "Company")

    output_filename = f"{name_part}_{role_part}_{company_part}.{format}"
    output_path = str(config.OUTPUT_DIR / output_filename)

    if format == "docx":
        render_html_export_to_docx(html_content, output_path)
    elif format == "pdf":
        render_html_export_to_pdf(html_content, output_path)
    else:
        render_html_export_to_txt(html_content, output_path)

    return FileResponse(output_path, media_type=_DOWNLOAD_MEDIA_TYPES[format], filename=output_filename)


@router.get("/session/{session_id}/render")
def render_session(session_id: int, session: Session = Depends(get_session)):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    highlighted_html = _render_working_html(session, tailoring_session)
    return JSONResponse({"html": highlighted_html})


@router.post("/session/{session_id}/manual-edit")
def manual_edit(
    session_id: int,
    html_content: str = Form(...),
    session: Session = Depends(get_session),
):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    cleaned = sanitize_html(strip_marks(html_content))
    crud.update_working_html(session, session_id, cleaned)
    return JSONResponse({"status": "ok"})


@router.post("/session/{session_id}/propose-soft")
def propose_soft(
    session_id: int,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    task_id = run_tracked_task("tailoring_soft", _run_propose_soft, session_id, lang)
    return JSONResponse({"task_id": task_id})


def _run_propose_soft(session_id: int, lang: str = "en") -> dict:
    session = SessionLocal()
    try:
        tailoring_session = crud.get_tailoring_session(session, session_id)
        job = crud.get_job_posting(session, tailoring_session.job_posting_id)
        crud.set_job_activity(session, job.id, "Tailoring resume (soft)...")
        try:
            matched_factors = _get_matched_factors(session, job.id)

            provider = get_llm_provider()
            keywords = _ensure_keywords(session, tailoring_session, job, provider=provider)

            logger.info("[session %s] propose-soft: calling LLM (job=%s)", session_id, job.id)
            changes = propose_soft_fragment_changes(
                provider,
                job_posting_text=job.raw_text,
                resume_html=tailoring_session.working_html or "",
                matched_factors=matched_factors,
                keywords=_keyword_texts(keywords),
            )
            logger.info("[session %s] propose-soft: got %s changes", session_id, len(changes))
            if not changes:
                logger.warning(
                    "[session %s] propose-soft: LLM returned 0 changes (check working_html and prompt output)",
                    session_id,
                )

            message = crud.create_tailoring_message(
                session, session_id, role="assistant", text=_soft_message_text(lang)
            )
            created, superseded = _store_changes_with_dedup(session, session_id, message.id, changes)

            return {
                "message_id": message.id,
                "message_text": message.text,
                "level": "soft",
                "changes": [_serialize_change(c) for c in created],
                "superseded_change_ids": [c.id for c in superseded],
                "keywords": keywords,
            }
        finally:
            crud.set_job_activity(session, job.id, None)
    finally:
        session.close()


@router.post("/session/{session_id}/propose-medium")
def propose_medium(
    session_id: int,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    task_id = run_tracked_task("tailoring_medium", _run_propose_medium, session_id, lang)
    return JSONResponse({"task_id": task_id})


def _run_propose_medium(session_id: int, lang: str = "en") -> dict:
    session = SessionLocal()
    try:
        tailoring_session = crud.get_tailoring_session(session, session_id)
        job = crud.get_job_posting(session, tailoring_session.job_posting_id)
        crud.set_job_activity(session, job.id, "Tailoring resume (medium)...")
        try:
            matched_factors = _get_matched_factors(session, job.id)

            provider = get_llm_provider()
            keywords = _ensure_keywords(session, tailoring_session, job, provider=provider)
            keyword_texts = _keyword_texts(keywords)

            logger.info("[session %s] propose-medium: calling LLM (job=%s)", session_id, job.id)
            changes = propose_medium_fragment_changes(
                provider,
                job_posting_text=job.raw_text,
                resume_html=tailoring_session.working_html or "",
                matched_factors=matched_factors,
                keywords=keyword_texts,
            )
            logger.info("[session %s] propose-medium: got %s changes", session_id, len(changes))
            if not changes:
                logger.warning(
                    "[session %s] propose-medium: LLM returned 0 changes (check working_html and prompt output)",
                    session_id,
                )

            message = crud.create_tailoring_message(
                session, session_id, role="assistant", text=_medium_message_text(lang)
            )
            created, superseded = _store_changes_with_dedup(session, session_id, message.id, changes)

            return {
                "message_id": message.id,
                "message_text": message.text,
                "level": "medium",
                "changes": [_serialize_change(c) for c in created],
                "superseded_change_ids": [c.id for c in superseded],
                "keywords": keywords,
            }
        finally:
            crud.set_job_activity(session, job.id, None)
    finally:
        session.close()


@router.post("/session/{session_id}/message")
def send_message(
    session_id: int,
    user_message: str = Form(...),
    session: Session = Depends(get_session),
):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    history = crud.list_tailoring_messages(session, session_id)
    history_dicts = [{"role": m.role, "text": m.text} for m in history]

    crud.create_tailoring_message(session, session_id, role="user", text=user_message)

    task_id = run_tracked_task(
        "tailoring_agent_turn", _run_agent_turn, session_id, history_dicts, user_message
    )
    return JSONResponse({"task_id": task_id})


def _run_agent_turn(session_id: int, history_dicts: list[dict], user_message: str) -> dict:
    session = SessionLocal()
    try:
        tailoring_session = crud.get_tailoring_session(session, session_id)
        job = crud.get_job_posting(session, tailoring_session.job_posting_id)
        crud.set_job_activity(session, job.id, "Tailoring resume...")
        try:
            matched_factors = _get_matched_factors(session, job.id)

            provider = get_llm_provider()
            keywords = _ensure_keywords(session, tailoring_session, job, provider=provider)

            result = run_agent_fragment_turn(
                provider,
                job_posting_text=job.raw_text,
                resume_html=tailoring_session.working_html or "",
                matched_factors=matched_factors,
                conversation_history=history_dicts,
                user_message=user_message,
                keywords=_keyword_texts(keywords),
            )

            message = crud.create_tailoring_message(
                session, session_id, role="assistant", text=result["message"]
            )
            created, superseded = _store_changes_with_dedup(
                session, session_id, message.id, result["changes"]
            )

            return {
                "message_id": message.id,
                "message_text": message.text,
                "level": "custom",
                "changes": [_serialize_change(c) for c in created],
                "superseded_change_ids": [c.id for c in superseded],
                "keywords": keywords,
            }
        finally:
            crud.set_job_activity(session, job.id, None)
    finally:
        session.close()


@router.post("/changes/{change_id}/resolve")
def resolve_change(
    change_id: int,
    action: str = Form(...),
    session: Session = Depends(get_session),
):
    change = crud.get_tailoring_change(session, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")

    if action == "approve":
        tailoring_session = crud.get_tailoring_session(session, change.session_id)
        try:
            new_html = apply_fragment(
                tailoring_session.working_html or "", change.original_text, change.proposed_text
            )
        except ValueError as error:
            logger.warning("[change %s] approve failed: %s", change_id, error)
            crud.resolve_tailoring_change(session, change_id, status="failed")
            return JSONResponse({"status": "error", "detail": str(error)}, status_code=409)

        crud.update_working_html(session, tailoring_session.id, new_html)
        crud.resolve_tailoring_change(session, change_id, status="approved")
    elif action == "reject":
        crud.resolve_tailoring_change(session, change_id, status="rejected")
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    return JSONResponse({"status": "ok"})


@router.post("/changes/{change_id}/revert")
def revert_change(
    change_id: int,
    session: Session = Depends(get_session),
):
    change = crud.get_tailoring_change(session, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Change not found")
    if change.status != "approved":
        raise HTTPException(status_code=400, detail="Only approved changes can be reverted")

    tailoring_session = crud.get_tailoring_session(session, change.session_id)
    try:
        new_html = apply_fragment(
            tailoring_session.working_html or "", change.proposed_text, change.original_text
        )
    except ValueError as error:
        logger.warning("[change %s] revert failed: %s", change_id, error)
        return JSONResponse({"status": "error", "detail": str(error)}, status_code=409)

    crud.update_working_html(session, tailoring_session.id, new_html)
    crud.resolve_tailoring_change(session, change_id, status="reverted", final_text=change.original_text)

    return JSONResponse({"status": "ok"})