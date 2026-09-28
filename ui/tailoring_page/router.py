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
from core.gap_analysis.block_generation import generate_block_fragments
from core.gap_analysis.pipeline import run_full_gap_analysis
from core.gap_analysis.title_suggestions import suggest_title_changes
from core.parsing.html_blocks import (
    TITLE_KINDS,
    block_fragments,
    build_title_targets,
    normalize_elements,
    replace_block_elements,
)
from core.parsing.html_sanitize import sanitize_html
from core.parsing.html_to_text import html_to_text
from core.providers.factory import get_llm_provider
from core.rendering.docx_renderer import render_html_export_to_docx
from core.rendering.pdf_renderer import render_html_export_to_pdf
from core.rendering.txt_renderer import render_html_export_to_txt
from core.tailoring.blocks_service import ensure_session_blocks
from core.tailoring.fragment_pipeline import (
    propose_medium_fragment_changes,
    propose_soft_fragment_changes,
    run_agent_fragment_turn,
)
from core.tailoring.html_diff import apply_fragment, strip_marks
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


def _find_block(blocks: list[dict], field_path: str) -> dict | None:
    return next((block for block in blocks if block["field_path"] == field_path), None)


def _body_blocks(blocks: list[dict]) -> list[dict]:
    return [block for block in blocks if block["kind"] not in TITLE_KINDS]


def _replace_block(blocks: list[dict], new_block: dict) -> list[dict]:
    return [new_block if block["id"] == new_block["id"] else block for block in blocks]


def _title_sort_key(item: dict, block_order: dict[str, int]) -> tuple:
    if "order" in item:
        return (item["order"], item.get("line", 0))
    return (block_order.get(item.get("key"), len(block_order)), item.get("line", 0))


def pregenerate_tailoring_context(job_posting_id: int, lang: str = "en") -> None:
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
    tailoring_session = ensure_session_blocks(session, tailoring_session)

    job_context = _get_job_context(session, job_id)

    return templates.TemplateResponse(
        "tailor.html",
        {
            "request": request,
            "job": job,
            "session_id": tailoring_session.id,
            "resume_html": tailoring_session.working_html or "",
            "blocks": tailoring_session.blocks or [],
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
        "disabled_field_paths": item.disabled_field_paths or [],
        "recommend_keep": item.recommend_keep,
        "included": item.included,
    }


@router.get("/session/{session_id}/gap-items")
def get_gap_items(session_id: int, session: Session = Depends(get_session)):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    items = crud.list_gap_items_for_session(session, session_id)
    blocks = tailoring_session.blocks or []

    title_suggestions = tailoring_session.title_suggestions
    if title_suggestions is not None:
        valid = [s for s in title_suggestions if s.get("key")]
        title_suggestions = valid if valid or not title_suggestions else None

    return JSONResponse(
        {
            "ready": tailoring_session.gap_analysis_ready,
            "items": [_serialize_gap_item(i) for i in items],
            "block_comments": tailoring_session.block_comments or {},
            "block_order": [block["field_path"] for block in _body_blocks(blocks)],
            "blocks": blocks,
            "resume_items": tailoring_session.resume_items or [],
            "edited_blocks": tailoring_session.edited_blocks or {},
            "title_suggestions": title_suggestions,
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
        blocks = tailoring_session.blocks or []

        provider = get_llm_provider()

        result = run_full_gap_analysis(
            provider,
            job_posting_text=job.raw_text,
            resume_html=tailoring_session.working_html or "",
            linkedin_text=linkedin.raw_text if linkedin else "",
            extra_info=profile.extra_info if profile else None,
            blocks=blocks,
        )
        gap_items = result["gap_items"]
        resume_items = result["resume_items"]

        valid_paths = {block["field_path"] for block in _body_blocks(blocks)}
        for item in gap_items:
            item["suggested_field_paths"] = [
                path for path in item.get("suggested_field_paths") or [] if path in valid_paths
            ]

        if not gap_items:
            logger.warning("[session %s] run_gap_analysis: 0 gap items after retries", session_id)

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
    is_original: str = Form(""),
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
        item = existing[0]
        if field_path not in (item.assigned_field_paths or []):
            item = crud.toggle_gap_item_location(session, item.id, field_path)
        if is_original == "true" and not item.original_field_path:
            item.original_field_path = field_path
            session.commit()
            session.refresh(item)
        return JSONResponse({"item": _serialize_gap_item(item)})

    original_field_path = field_path if is_original == "true" else None
    item = crud.create_custom_gap_item(session, session_id, cleaned, field_path, original_field_path=original_field_path)
    return JSONResponse({"item": _serialize_gap_item(item)})


@router.post("/session/{session_id}/title-suggestions")
def save_title_suggestions(
    session_id: int,
    suggestions_json: str = Form(...),
    session: Session = Depends(get_session),
):
    import json as _json

    try:
        suggestions = _json.loads(suggestions_json)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    tailoring_session = crud.save_title_suggestions(session, session_id, suggestions)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return JSONResponse({"status": "ok"})


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

        targets = build_title_targets(tailoring_session.working_html or "", tailoring_session.blocks or [])
        suggestions = suggest_title_changes(get_llm_provider(), targets, job.raw_text)

        crud.save_title_suggestions(session, session_id, suggestions)
        return {"suggestions": suggestions}
    finally:
        session.close()


@router.post("/session/{session_id}/apply-title")
def apply_title(
    session_id: int,
    key: str = Form(...),
    line: int = Form(0),
    current_text: str = Form(...),
    new_text: str = Form(...),
    session: Session = Depends(get_session),
):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    blocks = tailoring_session.blocks or []
    block = _find_block(blocks, key)
    if block is None or block["kind"] not in TITLE_KINDS:
        raise HTTPException(status_code=404, detail="Title block not found")

    html = tailoring_session.working_html or ""
    fragments = block_fragments(html, block)
    if not fragments:
        raise HTTPException(status_code=409, detail="Title block is empty")

    if block["kind"] == "title_main" and 0 <= line < len(fragments):
        candidate_indexes = [line]
    else:
        candidate_indexes = list(range(len(fragments)))

    new_fragments = list(fragments)
    applied = False
    for index in candidate_indexes:
        try:
            new_fragments[index] = apply_fragment(fragments[index], current_text, new_text)
            applied = True
            break
        except ValueError:
            continue
    if not applied:
        raise HTTPException(status_code=409, detail="Title text not found in the resume")

    try:
        new_html, new_block = replace_block_elements(html, block, new_fragments)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    crud.update_working_html(session, session_id, new_html)
    crud.set_session_blocks(session, session_id, _replace_block(blocks, new_block))

    matched = None
    remaining = []
    for suggestion in tailoring_session.title_suggestions or []:
        is_match = (
            matched is None
            and suggestion.get("key") == key
            and suggestion.get("current") == current_text
            and (suggestion.get("kind") != "main" or suggestion.get("line") == line)
        )
        if is_match:
            matched = suggestion
        else:
            remaining.append(suggestion)
    if matched is not None:
        crud.save_title_suggestions(session, session_id, remaining)

    crud.mark_block_edited(session, session_id, key, "\n".join(fragments), title_suggestion=matched)
    refreshed = crud.get_tailoring_session(session, session_id)
    return JSONResponse(
        {
            "html": strip_marks(new_html),
            "blocks": refreshed.blocks or [],
            "edited_blocks": refreshed.edited_blocks or {},
        }
    )


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
        {
            "status": "ok",
            "assigned_field_paths": item.assigned_field_paths or [],
            "disabled_field_paths": item.disabled_field_paths or [],
            "item_status": item.status,
        }
    )


@router.post("/gap-items/{gap_item_id}/toggle-disabled")
def toggle_gap_item_disabled(
    gap_item_id: int,
    field_path: str = Form(...),
    session: Session = Depends(get_session),
):
    item = crud.toggle_gap_item_disabled(session, gap_item_id, field_path)
    if item is None:
        raise HTTPException(status_code=404, detail="Gap item not found")
    return JSONResponse({"status": "ok", "disabled_field_paths": item.disabled_field_paths or []})


@router.post("/gap-items/{gap_item_id}/move-location")
def move_gap_item_location(
    gap_item_id: int,
    from_field_path: str = Form(...),
    to_field_path: str = Form(...),
    session: Session = Depends(get_session),
):
    item = crud.move_gap_item_location(session, gap_item_id, from_field_path, to_field_path)
    if item is None:
        raise HTTPException(status_code=404, detail="Gap item not found")
    return JSONResponse(
        {
            "status": "ok",
            "assigned_field_paths": item.assigned_field_paths or [],
            "disabled_field_paths": item.disabled_field_paths or [],
            "item_status": item.status,
        }
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

        blocks = tailoring_session.blocks or []
        block = _find_block(blocks, field_path)
        if block is None or block["kind"] in TITLE_KINDS:
            raise ValueError("Block not found")

        html = tailoring_session.working_html or ""
        originals = block_fragments(html, block)
        if not originals:
            raise ValueError("Block is empty")

        items = crud.list_gap_items_for_session(session, session_id)
        included_texts = [
            item.text
            for item in items
            if item.status in ("match", "can_add")
            and field_path in (item.assigned_field_paths or [])
            and field_path not in (item.disabled_field_paths or [])
        ]
        included_texts += [
            item.text
            for item in items
            if item.status in ("miss", "over")
            and field_path in (item.assigned_field_paths or [])
            and field_path not in (item.disabled_field_paths or [])
        ]
        keep_texts = [
            item.text
            for item in items
            if item.status == "over" and item.recommend_keep and item.original_field_path == field_path
        ]
        comment = (tailoring_session.block_comments or {}).get(field_path, "")

        fragments = generate_block_fragments(
            get_llm_provider(),
            originals,
            block["label"],
            html_to_text(strip_marks(html)),
            job.raw_text,
            included_texts,
            keep_texts,
            comment,
            kind=block["kind"],
        )

        if fragments == originals:
            return {"unchanged": True}

        new_html, new_block = replace_block_elements(html, block, fragments)
        updated_blocks = _replace_block(blocks, new_block)
        crud.update_working_html(session, session_id, new_html)
        crud.set_session_blocks(session, session_id, updated_blocks)
        crud.mark_block_edited(session, session_id, field_path, "\n".join(originals))

        refreshed = crud.get_tailoring_session(session, session_id)
        return {
            "html": strip_marks(new_html),
            "blocks": updated_blocks,
            "edited_blocks": refreshed.edited_blocks or {},
        }
    finally:
        session.close()


@router.post("/session/{session_id}/revert-block")
def revert_block(
    session_id: int,
    field_path: str = Form(...),
    session: Session = Depends(get_session),
):
    tailoring_session = crud.get_tailoring_session(session, session_id)
    if tailoring_session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    record = (tailoring_session.edited_blocks or {}).get(field_path)
    if record is None:
        raise HTTPException(status_code=400, detail="No stored original for this block")

    original_html = record["original_html"] if isinstance(record, dict) else record
    restored_suggestions = list(record.get("title_suggestions") or []) if isinstance(record, dict) else []

    blocks = tailoring_session.blocks or []
    block = _find_block(blocks, field_path)
    if block is None:
        raise HTTPException(status_code=409, detail="Block not found")

    from core.parsing.html_blocks import split_top_level

    fragments = [element["html"] for element in split_top_level(original_html)]
    if not fragments:
        raise HTTPException(status_code=409, detail="Stored original is empty")

    try:
        new_html, new_block = replace_block_elements(tailoring_session.working_html or "", block, fragments)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    crud.update_working_html(session, session_id, new_html)
    crud.set_session_blocks(session, session_id, _replace_block(blocks, new_block))
    crud.unmark_block_edited(session, session_id, field_path)

    if restored_suggestions:
        latest = crud.get_tailoring_session(session, session_id)
        order = {block["field_path"]: index for index, block in enumerate(latest.blocks or [])}
        merged = list(latest.title_suggestions or []) + restored_suggestions
        merged.sort(key=lambda item: _title_sort_key(item, order))
        crud.save_title_suggestions(session, session_id, merged)

    refreshed = crud.get_tailoring_session(session, session_id)
    return JSONResponse(
        {
            "html": strip_marks(new_html),
            "blocks": refreshed.blocks or [],
            "edited_blocks": refreshed.edited_blocks or {},
            "title_suggestions": refreshed.title_suggestions or [],
        }
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
    normalized, blocks = normalize_elements(cleaned, tailoring_session.blocks or [])
    crud.update_working_html(session, session_id, normalized)
    crud.set_session_blocks(session, session_id, blocks)
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

            changes = propose_soft_fragment_changes(
                provider,
                job_posting_text=job.raw_text,
                resume_html=tailoring_session.working_html or "",
                matched_factors=matched_factors,
                keywords=_keyword_texts(keywords),
            )
            if not changes:
                logger.warning("[session %s] propose-soft: LLM returned 0 changes", session_id)

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

            changes = propose_medium_fragment_changes(
                provider,
                job_posting_text=job.raw_text,
                resume_html=tailoring_session.working_html or "",
                matched_factors=matched_factors,
                keywords=keyword_texts,
            )
            if not changes:
                logger.warning("[session %s] propose-medium: LLM returned 0 changes", session_id)

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