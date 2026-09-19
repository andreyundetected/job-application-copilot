from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

from core.automation import pipeline
from core.db import crud
from core.db.session import SessionLocal, get_session
from core.discovery.query_builder import (
    build_query_string,
    count_words,
    suggest_search_queries,
    validate_query_length,
)
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

    return templates.TemplateResponse(
        "automation.html",
        {
            "request": request,
            "settings": settings,
            "runs": [_serialize_run(run) for run in runs],
            "usage_by_run": usage_by_run,
            "tailoring_matrix": _tailoring_matrix_state(session),
            "lang": lang,
            "t": load_page_strings("ui/automation_page", lang),
        },
    )


@router.post("/settings")
def update_settings(
    min_score_to_proceed: int = Form(...),
    max_score_to_archive: int = Form(...),
    quick_filter_enabled: bool = Form(False),
    auto_archive_enabled: bool = Form(False),
    max_query_words: int = Form(32),
    default_time_range: str = Form("w1"),
    session: Session = Depends(get_session),
):
    if default_time_range not in _TIME_RANGE_OPTIONS:
        raise HTTPException(status_code=400, detail="Invalid time range")
    if min_score_to_proceed <= max_score_to_archive:
        raise HTTPException(
            status_code=400, detail="min_score_to_proceed must be greater than max_score_to_archive"
        )

    crud.upsert_automation_settings(
        session,
        min_score_to_proceed=min_score_to_proceed,
        max_score_to_archive=max_score_to_archive,
        quick_filter_enabled=quick_filter_enabled,
        auto_archive_enabled=auto_archive_enabled,
        max_query_words=max(1, max_query_words),
        default_time_range=default_time_range,
    )
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
    return JSONResponse({"status": "ok"})


@router.post("/target-sites")
def add_target_site(site: str = Form(...), session: Session = Depends(get_session)):
    site = site.strip()
    if not site:
        raise HTTPException(status_code=400, detail="Site cannot be empty")

    settings = _get_or_create_settings(session)
    target_sites = list(settings.target_sites or [])
    if site not in target_sites:
        target_sites.append(site)

    updated = crud.upsert_automation_settings(session, target_sites=target_sites)
    return JSONResponse({"target_sites": updated.target_sites})


@router.post("/target-sites/{index}/delete")
def delete_target_site(index: int, session: Session = Depends(get_session)):
    settings = crud.get_automation_settings(session)
    if settings is None:
        raise HTTPException(status_code=404, detail="Settings not found")

    target_sites = list(settings.target_sites or [])
    if index < 0 or index >= len(target_sites):
        raise HTTPException(status_code=404, detail="Site not found")

    target_sites.pop(index)
    updated = crud.upsert_automation_settings(session, target_sites=target_sites)
    return JSONResponse({"target_sites": updated.target_sites})


@router.post("/saved-queries")
def add_saved_query(query_text: str = Form(...), session: Session = Depends(get_session)):
    query = query_text.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    settings = _get_or_create_settings(session)

    if not validate_query_length(query, settings.max_query_words):
        raise HTTPException(
            status_code=400,
            detail=f"Query exceeds the {settings.max_query_words}-word limit ({count_words(query)} words)",
        )

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

    settings = _get_or_create_settings(session)

    candidate_context = resume.raw_text
    if linkedin is not None:
        candidate_context += "\n\n" + linkedin.raw_text

    task_id = run_tracked_task(
        "automation_suggest_queries",
        _run_suggest_queries,
        candidate_context,
        settings.target_sites,
        settings.max_query_words,
    )
    return JSONResponse({"task_id": task_id})


def _run_suggest_queries(candidate_context: str, target_sites: list, max_query_words: int) -> dict:
    session = SessionLocal()
    try:
        provider = get_llm_provider()
        groups = suggest_search_queries(provider, candidate_context, target_sites, max_query_words)

        added = []
        dropped = 0
        for terms in groups:
            query = build_query_string(terms, target_sites)
            if validate_query_length(query, max_query_words):
                added.append(query)
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
    num_per_query: int = Form(30),
    max_results_override: str = Form(""),
    max_queries_override: str = Form(""),
    session: Session = Depends(get_session),
):
    if time_range not in _TIME_RANGE_OPTIONS:
        raise HTTPException(status_code=400, detail="Invalid time range")

    settings = _get_or_create_settings(session)
    queries = list(settings.saved_queries or [])
    if not queries:
        raise HTTPException(status_code=400, detail="No saved queries - add at least one first")

    results_cap = int(max_results_override) if max_results_override.strip().isdigit() else None
    queries_cap = int(max_queries_override) if max_queries_override.strip().isdigit() else None

    if settings.serpent_num_per_query != num_per_query or settings.default_time_range != time_range:
        crud.upsert_automation_settings(
            session, serpent_num_per_query=num_per_query, default_time_range=time_range
        )

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