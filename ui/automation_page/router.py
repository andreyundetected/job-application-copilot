from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

from core.automation import pipeline
from core.db import crud
from core.db.session import SessionLocal, get_session
from core.discovery.query_builder import (
    DEFAULT_MAX_QUERY_WORDS,
    DEFAULT_TARGET_SITES,
    PLANNED_TARGET_SITES,
    build_catch_all_queries,
    build_query_string,
    count_words,
    fit_query_to_word_limit,
    suggest_search_queries,
    validate_query_length,
)

# Budget given to the LLM when it drafts query term groups - kept below the real
# 32-word Google limit so the model has slack and doesn't hug the ceiling; any
# group that still comes back over the real limit gets trimmed, not dropped.
_SUGGEST_MAX_QUERY_WORDS = 32
_SUGGEST_MAX_ATTEMPTS = 3
from core.providers.factory import get_llm_provider
from core.tasks.executor import submit_task
from core.tasks.runner import run_tracked_task
from ui.common.i18n import get_language, load_page_strings

router = APIRouter(prefix="/automation")

templates = Jinja2Templates(directory="ui/automation_page/templates")
templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader("ui/automation_page/templates"),
        FileSystemLoader("ui/common/templates"),
    ]
)

_TIME_RANGE_OPTIONS = ["d1", "w1", "m1"]

_TAILORING_MATRIX = [
    ("soft", "title"),
    ("soft", "company_name"),
    ("soft", "skills"),
    ("medium", "summary"),
    ("medium", "bullet"),
]


def _serialize_run(run) -> dict:
    return {
        "id": run.id,
        "status": run.status,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "queries_planned": run.queries_planned or [],
        "max_results_override": run.max_results_override,
        "max_queries_override": run.max_queries_override,
        "found_count": run.found_count,
        "quick_filtered_count": run.quick_filtered_count,
        "scraped_count": run.scraped_count,
        "evaluated_count": run.evaluated_count,
        "passed_count": run.passed_count,
        "archived_count": run.archived_count,
        "error": run.error,
    }


def _tailoring_matrix_state(session: Session) -> list[dict]:
    return [
        {
            "level": level,
            "change_type": change_type,
            "auto_apply": crud.is_auto_apply(session, level, change_type),
        }
        for level, change_type in _TAILORING_MATRIX
    ]


def _get_or_create_settings(session: Session):
    settings = crud.get_automation_settings(session)
    if settings is None:
        settings = crud.upsert_automation_settings(session)
    return settings


@router.get("", response_class=HTMLResponse)
def automation_page(
    request: Request,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    settings = _get_or_create_settings(session)
    runs = crud.list_automation_runs(session, limit=20)
    usage_by_run = {run.id: crud.sum_usage_for_run(session, run.id) for run in runs}
    base_questions = crud.list_automation_base_questions(session)

    return templates.TemplateResponse(
        "automation.html",
        {
            "request": request,
            "settings": settings,
            "runs": [_serialize_run(run) for run in runs],
            "usage_by_run": usage_by_run,
            "tailoring_matrix": _tailoring_matrix_state(session),
            "soft_active": crud.level_has_auto_apply(session, "soft"),
            "medium_active": crud.level_has_auto_apply(session, "medium"),
            "base_questions": base_questions,
            "target_sites": DEFAULT_TARGET_SITES,
            "planned_sites": PLANNED_TARGET_SITES,
            "max_query_words": DEFAULT_MAX_QUERY_WORDS,
            "catch_all_query_preview": " / ".join(build_catch_all_queries()),
            "lang": lang,
            "t": load_page_strings("ui/automation_page", lang),
        },
    )


@router.post("/base-questions")
def add_base_question(question_text: str = Form(...), session: Session = Depends(get_session)):
    text = question_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Question text cannot be empty")

    question = crud.create_automation_base_question(session, question_text=text)
    return JSONResponse({"id": question.id, "question_text": question.question_text})


@router.post("/base-questions/{question_id}/delete")
def delete_base_question(question_id: int, session: Session = Depends(get_session)):
    crud.delete_automation_base_question(session, question_id)
    return JSONResponse({"status": "ok", "id": question_id})


@router.post("/settings")
def update_settings(
    min_score_to_proceed: int | None = Form(None),
    max_score_to_archive: int | None = Form(None),
    quick_filter_enabled: str | None = Form(None),
    auto_archive_enabled: str | None = Form(None),
    default_time_range: str | None = Form(None),
    serpent_num_per_query: int | None = Form(None),
    catch_all_enabled: str | None = Form(None),
    max_pages_per_query: int | None = Form(None),
    session: Session = Depends(get_session),
):
    """Autosave endpoint - the client posts only the field(s) that just changed,
    so every field here is optional and only touched keys are written."""
    settings = _get_or_create_settings(session)

    if default_time_range is not None and default_time_range not in _TIME_RANGE_OPTIONS:
        raise HTTPException(status_code=400, detail="Invalid time range")

    new_min = min_score_to_proceed if min_score_to_proceed is not None else settings.min_score_to_proceed
    new_max = max_score_to_archive if max_score_to_archive is not None else settings.max_score_to_archive
    if new_min <= new_max:
        raise HTTPException(
            status_code=400, detail="min_score_to_proceed must be greater than max_score_to_archive"
        )

    kwargs = {}
    if min_score_to_proceed is not None:
        kwargs["min_score_to_proceed"] = min_score_to_proceed
    if max_score_to_archive is not None:
        kwargs["max_score_to_archive"] = max_score_to_archive
    if quick_filter_enabled is not None:
        kwargs["quick_filter_enabled"] = quick_filter_enabled == "true"
    if auto_archive_enabled is not None:
        kwargs["auto_archive_enabled"] = auto_archive_enabled == "true"
    if default_time_range is not None:
        kwargs["default_time_range"] = default_time_range
    if serpent_num_per_query is not None:
        kwargs["serpent_num_per_query"] = max(1, min(serpent_num_per_query, 100))
    if catch_all_enabled is not None:
        kwargs["catch_all_enabled"] = catch_all_enabled == "true"
    if max_pages_per_query is not None:
        kwargs["max_pages_per_query"] = max(1, min(max_pages_per_query, 50))

    crud.upsert_automation_settings(session, **kwargs)
    return JSONResponse({"status": "ok"})


@router.post("/tailoring-permissions")
def update_tailoring_permission(
    level: str = Form(...),
    change_type: str = Form(...),
    auto_apply: bool = Form(False),
    session: Session = Depends(get_session),
):
    if (level, change_type) not in _TAILORING_MATRIX:
        raise HTTPException(status_code=400, detail="Unknown level/change_type combination")

    crud.set_tailoring_permission(session, level=level, change_type=change_type, auto_apply=auto_apply)
    return JSONResponse(
        {
            "status": "ok",
            "soft_active": crud.level_has_auto_apply(session, "soft"),
            "medium_active": crud.level_has_auto_apply(session, "medium"),
        }
    )


@router.post("/saved-queries")
def add_saved_query(query_text: str = Form(...), session: Session = Depends(get_session)):
    query = query_text.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    if not validate_query_length(query, DEFAULT_MAX_QUERY_WORDS):
        raise HTTPException(
            status_code=400,
            detail=f"Query exceeds the {DEFAULT_MAX_QUERY_WORDS}-word limit ({count_words(query)} words)",
        )

    settings = _get_or_create_settings(session)
    saved_queries = list(settings.saved_queries or [])
    saved_queries.append(query)

    updated = crud.upsert_automation_settings(session, saved_queries=saved_queries)
    return JSONResponse({"saved_queries": updated.saved_queries})


@router.post("/saved-queries/{index}/delete")
def delete_saved_query(index: int, session: Session = Depends(get_session)):
    settings = crud.get_automation_settings(session)
    if settings is None:
        raise HTTPException(status_code=404, detail="Settings not found")

    saved_queries = list(settings.saved_queries or [])
    if index < 0 or index >= len(saved_queries):
        raise HTTPException(status_code=404, detail="Query not found")

    saved_queries.pop(index)
    updated = crud.upsert_automation_settings(session, saved_queries=saved_queries)
    return JSONResponse({"saved_queries": updated.saved_queries})


@router.post("/suggest-queries")
def suggest_queries(session: Session = Depends(get_session)):
    resume = crud.get_active_resume_version(session, "resume")
    linkedin = crud.get_active_resume_version(session, "linkedin")

    if resume is None:
        raise HTTPException(status_code=400, detail="No active resume set")

    candidate_context = resume.raw_text
    if linkedin is not None:
        candidate_context += "\n\n" + linkedin.raw_text

    task_id = run_tracked_task("automation_suggest_queries", _run_suggest_queries, candidate_context)
    return JSONResponse({"task_id": task_id})


def _run_suggest_queries(candidate_context: str) -> dict:
    session = SessionLocal()
    try:
        provider = get_llm_provider()

        groups: list[list[str]] = []
        for _ in range(_SUGGEST_MAX_ATTEMPTS):
            groups = suggest_search_queries(provider, candidate_context, max_query_words=_SUGGEST_MAX_QUERY_WORDS)
            if groups:
                break

        added = []
        dropped = 0
        for terms in groups:
            query = build_query_string(terms)
            if validate_query_length(query):
                added.append(query)
                continue

            # Over the real 32-word limit even with the tighter 32-word budget we
            # gave the model - trim trailing terms rather than lose the group entirely.
            fitted = fit_query_to_word_limit(terms)
            if fitted:
                added.append(fitted)
            else:
                dropped += 1

        settings = _get_or_create_settings(session)
        saved_queries = list(settings.saved_queries or [])
        saved_queries.extend(added)
        updated = crud.upsert_automation_settings(session, saved_queries=saved_queries)

        return {"added": added, "dropped": dropped, "saved_queries": updated.saved_queries}
    finally:
        session.close()


@router.post("/runs")
def start_run(
    time_range: str = Form("w1"),
    max_results_override: str = Form(""),
    max_queries_override: str = Form(""),
    session: Session = Depends(get_session),
):
    if time_range not in _TIME_RANGE_OPTIONS:
        raise HTTPException(status_code=400, detail="Invalid time range")

    settings = _get_or_create_settings(session)

    if settings.catch_all_enabled:
        queries = build_catch_all_queries()
    else:
        queries = list(settings.saved_queries or [])
        if not queries:
            raise HTTPException(status_code=400, detail="No saved queries - add at least one first")

    results_cap = int(max_results_override) if max_results_override.strip().isdigit() else None
    queries_cap = int(max_queries_override) if max_queries_override.strip().isdigit() else None

    if settings.default_time_range != time_range:
        crud.upsert_automation_settings(session, default_time_range=time_range)

    run = crud.create_automation_run(
        session,
        queries_planned=queries,
        max_results_override=results_cap,
        max_queries_override=queries_cap,
    )

    submit_task(pipeline.run_automation_pipeline_task, run.id)

    return JSONResponse({"run_id": run.id})


@router.get("/runs/{run_id}")
def get_run_status(run_id: int, session: Session = Depends(get_session)):
    run = crud.get_automation_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    usage = crud.sum_usage_for_run(session, run_id)
    return JSONResponse({**_serialize_run(run), "usage": usage})