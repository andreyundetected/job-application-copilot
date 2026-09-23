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
from core.gap_analysis.block_extraction import extract_ordered_blocks
from core.gap_analysis.pipeline import run_full_gap_analysis
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
    return tailoring_session.working_html or ""


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


def _serialize_gap_item(item) -> dict:
    return {
        "id": item.id,
        "text": item.text,
        "category": item.category,
        "status": item.status,
        "priority": item.priority,
        "source": item.source,
        "original_field_path": item.original_field_path,
        "suggested_field_paths": item.suggested_field_paths or [],
        "suggested_reason": item.suggested_reason,
        "assigned_field_paths": item.assigned_field_paths or [],
        "recommend_keep": item.recommend_keep,
        "included": item.included,
    }


@router.get("/session/{session_id}/gap-items")
def get_gap_items(session_id: int, session: Session = Depends(get_session)):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    items = crud.list_gap_items_for_session(session, session_id)
    blocks = extract_ordered_blocks(tailoring_session.working_html or "")
    block_order = [b["field_path"] for b in blocks]

    logger.info("[session %s] get_gap_items: ready=%s, %s items", session_id, tailoring_session.gap_analysis_ready, len(items))
    return JSONResponse(
        {
            "ready": tailoring_session.gap_analysis_ready,
            "items": [_serialize_gap_item(i) for i in items],
            "block_comments": tailoring_session.block_comments or {},
            "block_order": block_order,
            "resume_items": tailoring_session.resume_items or [],
        }
    )


@router.post("/session/{session_id}/run-gap-analysis")
def run_gap_analysis(session_id: int, session: Session = Depends(get_session)):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    task_id = run_tracked_task("gap_analysis", _run_gap_analysis_task, session_id)
    return JSONResponse({"task_id": task_id})


def _run_gap_analysis_task(session_id: int) -> dict:
    session = SessionLocal()
    try:
        tailoring_session = crud.get_tailoring_session(session, session_id)
        job = crud.get_job_posting(session, tailoring_session.job_posting_id)
        linkedin = crud.get_active_resume_version(session, "linkedin")
        profile = crud.get_candidate_profile(session)

        provider = get_llm_provider()

        logger.info("[session %s] run_gap_analysis: starting, resume_html_len=%s", session_id, len(tailoring_session.working_html or ""))

        result = run_full_gap_analysis(
            provider,
            job_posting_text=job.raw_text,
            resume_html=tailoring_session.working_html or "",
            linkedin_text=linkedin.raw_text if linkedin else "",
            extra_info=profile.extra_info if profile else None,
        )
        gap_items = result["gap_items"]
        resume_items = result["resume_items"]

        logger.info(
            "[session %s] run_gap_analysis: got %s gap items, %s resume items",
            session_id, len(gap_items), len(resume_items),
        )
        if not gap_items:
            logger.warning("[session %s] run_gap_analysis: 0 gap items after retries - check LLM output format", session_id)

        crud.clear_gap_items_for_session(session, session_id)
        created = crud.bulk_create_gap_items(session, session_id, gap_items)
        crud.set_resume_items(session, session_id, resume_items)
        crud.mark_gap_analysis_ready(session, session_id)

        return {
            "items": [_serialize_gap_item(i) for i in created],
            "resume_items": resume_items,
            "count": len(created),
        }
    finally:
        session.close()


@router.post("/session/{session_id}/gap-items/custom")
def add_custom_gap_item(
    session_id: int,
    text: str = Form(...),
    field_path: str = Form(...),
    session: Session = Depends(get_session),
):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    existing = [i for i in crud.list_gap_items_for_session(session, session_id) if i.text.lower() == cleaned.lower()]
    if existing:
        item = crud.toggle_gap_item_location(session, existing[0].id, field_path)
        return JSONResponse({"item": _serialize_gap_item(item)})

    item = crud.create_custom_gap_item(session, session_id, cleaned, field_path)
    return JSONResponse({"item": _serialize_gap_item(item)})


def _extract_titles(html: str) -> tuple[str, list[dict]]:
    import re

    title_match = re.search(r'font-size:16pt[^>]*>(.*?)<', html)
    main_title = title_match.group(1).strip() if title_match else ""

    experience_titles = []
    for match in re.finditer(r'font-size:11pt[^>]*>(.*?)<', html):
        full_line = match.group(1).strip()
        parts = full_line.split(" - ", 1)
        company = parts[0].strip()
        title = parts[1].strip() if len(parts) > 1 else full_line
        if company:
            experience_titles.append({"company": company, "title": title})

    return main_title, experience_titles


@router.post("/session/{session_id}/suggest-titles")
def suggest_titles_endpoint(session_id: int, session: Session = Depends(get_session)):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    task_id = run_tracked_task("gap_suggest_titles", _run_suggest_titles, session_id)
    return JSONResponse({"task_id": task_id})


def _run_suggest_titles(session_id: int) -> dict:
    session = SessionLocal()
    try:
        tailoring_session = crud.get_tailoring_session(session, session_id)
        job = crud.get_job_posting(session, tailoring_session.job_posting_id)

        main_title, experience_titles = _extract_titles(tailoring_session.working_html or "")

        provider = get_llm_provider()
        from core.gap_analysis.pipeline import suggest_titles

        suggestions = suggest_titles(provider, main_title, experience_titles, job.raw_text)

        current_by_company = {e["company"]: e["title"] for e in experience_titles}
        for suggestion in suggestions:
            if suggestion["kind"] == "main":
                suggestion["current"] = main_title
            else:
                suggestion["current"] = current_by_company.get(suggestion["company"], "")

        return {"suggestions": suggestions}
    finally:
        session.close()


@router.post("/session/{session_id}/apply-title")
def apply_title(
    session_id: int,
    current_text: str = Form(...),
    new_text: str = Form(...),
    kind: str = Form("main"),
    company: str = Form(""),
    session: Session = Depends(get_session),
):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    html = tailoring_session.working_html or ""

    if kind == "experience" and company.strip():
        import re

        pattern = re.compile(
            r'(font-size:11pt[^>]*>\s*' + re.escape(company.strip()) + r'\s*-\s*)'
            + re.escape(current_text)
            + r'(\s*<)'
        )
        if not pattern.search(html):
            raise HTTPException(status_code=409, detail="Original title line not found for this company")
        new_html = pattern.sub(lambda m: m.group(1) + new_text + m.group(2), html, count=1)
    else:
        try:
            new_html = apply_fragment(html, current_text, new_text)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))

    crud.update_working_html(session, session_id, new_html)
    return JSONResponse({"html": new_html})


@router.post("/gap-items/{gap_item_id}/toggle-location")
def toggle_gap_item_location(
    gap_item_id: int,
    field_path: str = Form(...),
    session: Session = Depends(get_session),
):
    item = crud.toggle_gap_item_location(session, gap_item_id, field_path)
    if item is None:
        raise HTTPException(status_code=404, detail="Gap item not found")
    return JSONResponse(
        {"status": "ok", "assigned_field_paths": item.assigned_field_paths or [], "item_status": item.status}
    )


@router.post("/session/{session_id}/block-comment")
def set_block_comment(
    session_id: int,
    block_path: str = Form(...),
    comment: str = Form(""),
    session: Session = Depends(get_session),
):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    crud.set_block_comment(session, session_id, block_path, comment)
    return JSONResponse({"status": "ok"})


@router.post("/session/{session_id}/generate-block")
def generate_block(
    session_id: int,
    field_path: str = Form(...),
    session: Session = Depends(get_session),
):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    task_id = run_tracked_task("gap_generate_block", _run_generate_block, session_id, field_path)
    return JSONResponse({"task_id": task_id})


def _run_generate_block(session_id: int, field_path: str) -> dict:
    session = SessionLocal()
    try:
        tailoring_session = crud.get_tailoring_session(session, session_id)
        job = crud.get_job_posting(session, tailoring_session.job_posting_id)

        blocks = extract_ordered_blocks(tailoring_session.working_html or "")
        block = next((b for b in blocks if b["field_path"] == field_path), None)
        if block is None or not block["body_text"]:
            raise HTTPException(status_code=400, detail="Section is empty or not found in the resume")

        items = crud.list_gap_items_for_session(session, session_id)
        included_texts = [
            item.text
            for item in items
            if item.status in ("match", "can_add") and field_path in (item.assigned_field_paths or [])
        ]
        keep_texts = [
            item.text
            for item in items
            if item.status == "over" and item.recommend_keep and field_path in (item.original_field_path or "")
        ]
        comment = (tailoring_session.block_comments or {}).get(field_path, "")

        provider = get_llm_provider()

        from core.gap_analysis.block_generation import generate_block_content

        result = generate_block_content(
            provider,
            resume_html=tailoring_session.working_html or "",
            job_posting_text=job.raw_text,
            field_path=field_path,
            current_text=block["body_text"],
            included_items=included_texts,
            comment=comment,
            keep_items=keep_texts,
        )

        if not result["new_text"]:
            raise HTTPException(status_code=502, detail="No content returned by the model")

        new_html = apply_fragment(tailoring_session.working_html or "", block["body_text"], result["new_text"])
        crud.update_working_html(session, session_id, new_html)

        return {"html": strip_marks(new_html)}
    finally:
        session.close()


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

    return JSONResponse({"html": tailoring_session.working_html or ""})


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