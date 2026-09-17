from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

from core.db import crud
from core.db.session import SessionLocal, get_session
from core.parsing.html_sanitize import sanitize_html
from core.providers.factory import get_llm_provider
from core.tailoring.fragment_pipeline import (
    propose_medium_fragment_changes,
    propose_soft_fragment_changes,
    run_agent_fragment_turn,
)
from core.tailoring.html_diff import apply_fragment, strip_marks, wrap_highlights
from core.tasks.runner import run_tracked_task
from ui.common.i18n import get_language, load_page_strings

router = APIRouter(prefix="/tailor")

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
    pending = _pending_changes_for_render(session, tailoring_session.id)
    highlighted_html = wrap_highlights(tailoring_session.working_html or "", pending)

    messages = crud.list_tailoring_messages(session, tailoring_session.id)
    changes = crud.list_tailoring_changes_for_session(session, tailoring_session.id)

    changes_by_message: dict[int, list[dict]] = {}
    for change in changes:
        changes_by_message.setdefault(change.message_id, []).append(_serialize_change(change))

    return templates.TemplateResponse(
        "tailor.html",
        {
            "request": request,
            "job": job,
            "session_id": tailoring_session.id,
            "resume_html": highlighted_html,
            "messages": messages,
            "changes_by_message": changes_by_message,
            "lang": lang,
            "t": load_page_strings("ui/tailoring_page", lang),
        },
    )


@router.get("/session/{session_id}/render")
def render_session(session_id: int, session: Session = Depends(get_session)):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    pending = _pending_changes_for_render(session, session_id)
    highlighted_html = wrap_highlights(tailoring_session.working_html or "", pending)
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
        matched_factors = _get_matched_factors(session, job.id)

        provider = get_llm_provider()
        changes = propose_soft_fragment_changes(
            provider,
            job_posting_text=job.raw_text,
            resume_html=tailoring_session.working_html or "",
            matched_factors=matched_factors,
        )

        text = (
            "Soft-изменения: заголовок, названия должностей и подбор скиллов под вакансию "
            "(только терминология, ничего не переписывается по сути)."
            if lang == "ru"
            else "Soft changes: title, job titles and skills selection matched to the posting "
            "(terminology only, nothing rewritten in substance)."
        )
        message = crud.create_tailoring_message(session, session_id, role="assistant", text=text)
        created, superseded = _store_changes_with_dedup(session, session_id, message.id, changes)

        return {
            "message_id": message.id,
            "message_text": message.text,
            "level": "soft",
            "changes": [_serialize_change(c) for c in created],
            "superseded_change_ids": [c.id for c in superseded],
        }
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
        matched_factors = _get_matched_factors(session, job.id)
        keywords = [factor.get("text", "") for factor in matched_factors]

        provider = get_llm_provider()
        changes = propose_medium_fragment_changes(
            provider,
            job_posting_text=job.raw_text,
            resume_html=tailoring_session.working_html or "",
            matched_factors=matched_factors,
            keywords=keywords,
        )

        text = (
            "Medium-изменения: точечные правки summary и experience под ключевые слова вакансии "
            "(добавляем нужные слова в нужные места, не переписываем сильно)."
            if lang == "ru"
            else "Medium changes: targeted summary/experience edits weaving in the posting's keywords "
            "(words inserted in the right places, not a heavy rewrite)."
        )
        message = crud.create_tailoring_message(session, session_id, role="assistant", text=text)
        created, superseded = _store_changes_with_dedup(session, session_id, message.id, changes)

        return {
            "message_id": message.id,
            "message_text": message.text,
            "level": "medium",
            "changes": [_serialize_change(c) for c in created],
            "superseded_change_ids": [c.id for c in superseded],
        }
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
        matched_factors = _get_matched_factors(session, job.id)

        provider = get_llm_provider()
        result = run_agent_fragment_turn(
            provider,
            job_posting_text=job.raw_text,
            resume_html=tailoring_session.working_html or "",
            matched_factors=matched_factors,
            conversation_history=history_dicts,
            user_message=user_message,
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
        }
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
            crud.resolve_tailoring_change(session, change_id, status="failed")
            return JSONResponse({"status": "error", "detail": str(error)}, status_code=409)

        crud.update_working_html(session, tailoring_session.id, new_html)
        crud.resolve_tailoring_change(session, change_id, status="approved")
    elif action == "reject":
        crud.resolve_tailoring_change(session, change_id, status="rejected")
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    return JSONResponse({"status": "ok"})