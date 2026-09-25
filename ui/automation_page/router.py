import datetime
import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

from core.db import crud
from core.db.session import get_session
from core.discovery import run_control
from core.discovery.ats import default_target_sites
from core.discovery.backlog import run_backlog_pass, run_catch_up_pass
from core.discovery.poll_cycle import (
    PASS_GAP_SECONDS,
    run_empty_group_sweep,
    run_initial_collection,
    run_one_live_quantile_cycle,
)
from core.discovery.wayback_scan import run_wayback_scan_cycle
from core.discovery_db import crud as discovery_crud
from core.discovery_db.models import DiscoveredCompany, DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal
from core.tasks.executor import submit_task
from ui.common.i18n import get_language, load_page_strings

router = APIRouter(prefix="/automation")

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory="ui/automation_page/templates")
templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader("ui/automation_page/templates"),
        FileSystemLoader("ui/common/templates"),
    ]
)

_TAILORING_MATRIX = [
    ("soft", "title"),
    ("soft", "company_name"),
    ("soft", "skills"),
    ("medium", "summary"),
    ("medium", "bullet"),
]

DEFAULT_TARGET_SITES = default_target_sites()


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
    base_questions = crud.list_automation_base_questions(session)
    app_settings = crud.get_app_settings(session) or crud.upsert_app_settings(session)

    discovery_session = DiscoverySessionLocal()
    try:
        discovery_settings = discovery_crud.get_or_create_settings(discovery_session)
    finally:
        discovery_session.close()

    return templates.TemplateResponse(
        "automation.html",
        {
            "request": request,
            "settings": settings,
            "tailoring_matrix": _tailoring_matrix_state(session),
            "soft_active": crud.level_has_auto_apply(session, "soft"),
            "medium_active": crud.level_has_auto_apply(session, "medium"),
            "auto_tailor_master_enabled": settings.auto_tailor_master_enabled,
            "auto_questions_master_enabled": settings.auto_questions_master_enabled,
            "base_questions": base_questions,
            "target_sites": DEFAULT_TARGET_SITES,
            "discovery_enabled": discovery_settings.enabled,
            "discovery_wayback_interval_hours": discovery_settings.wayback_interval_hours,
            "discovery_initial_backlog_hours": discovery_settings.initial_backlog_hours,
            "discovery_quick_batch_enabled": discovery_settings.quick_batch_enabled,
            "discovery_batch_window_minutes": discovery_settings.batch_window_minutes,
            "discovery_batch_force_flush_size": discovery_settings.batch_force_flush_size,
            "discovery_empty_group_check_every_n_cycles": discovery_settings.empty_group_check_every_n_cycles,
            "telegram_bot_token": app_settings.telegram_bot_token or "",
            "telegram_chat_id": app_settings.telegram_chat_id or "",
            "telegram_notify_enabled": app_settings.telegram_notify_enabled,
            "telegram_notify_only_successful": app_settings.telegram_notify_only_successful,
            "telegram_notify_min_score": app_settings.telegram_notify_min_score if app_settings.telegram_notify_min_score is not None else 7,
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
    auto_archive_enabled: str | None = Form(None),
    session: Session = Depends(get_session),
):
    settings = _get_or_create_settings(session)

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
    if auto_archive_enabled is not None:
        kwargs["auto_archive_enabled"] = auto_archive_enabled == "true"

    crud.upsert_automation_settings(session, **kwargs)
    return JSONResponse({"status": "ok"})


@router.post("/master-toggles")
def update_master_toggles(
    auto_tailor_master_enabled: str | None = Form(None),
    auto_questions_master_enabled: str | None = Form(None),
    session: Session = Depends(get_session),
):
    kwargs = {}
    if auto_tailor_master_enabled is not None:
        kwargs["auto_tailor_master_enabled"] = auto_tailor_master_enabled == "true"
    if auto_questions_master_enabled is not None:
        kwargs["auto_questions_master_enabled"] = auto_questions_master_enabled == "true"

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


@router.post("/discovery/settings")
def update_discovery_settings(
    wayback_interval_hours: int | None = Form(None),
    initial_backlog_hours: int | None = Form(None),
    quick_batch_enabled: str | None = Form(None),
    batch_window_minutes: int | None = Form(None),
    batch_force_flush_size: int | None = Form(None),
    empty_group_check_every_n_cycles: int | None = Form(None),
):
    discovery_session = DiscoverySessionLocal()
    try:
        kwargs = {}
        if wayback_interval_hours is not None:
            kwargs["wayback_interval_hours"] = max(1, wayback_interval_hours)
        if initial_backlog_hours is not None:
            kwargs["initial_backlog_hours"] = max(0, initial_backlog_hours)
        turning_batch_off = False
        if quick_batch_enabled is not None:
            new_value = quick_batch_enabled == "true"
            current_settings = discovery_crud.get_or_create_settings(discovery_session)
            turning_batch_off = current_settings.quick_batch_enabled and not new_value
            kwargs["quick_batch_enabled"] = new_value
        if batch_window_minutes is not None:
            kwargs["batch_window_minutes"] = max(1, batch_window_minutes)
        if batch_force_flush_size is not None:
            kwargs["batch_force_flush_size"] = max(1, batch_force_flush_size)
        if empty_group_check_every_n_cycles is not None:
            kwargs["empty_group_check_every_n_cycles"] = max(1, empty_group_check_every_n_cycles)
        discovery_crud.update_settings(discovery_session, **kwargs)
    finally:
        discovery_session.close()

    if turning_batch_off:
        submit_task(run_catch_up_pass)

    return JSONResponse({"status": "ok"})


@router.get("/discovery/live-stats")
def discovery_live_stats():
    from core.discovery.posting_batch import pending_count

    discovery_session = DiscoverySessionLocal()
    try:
        settings = discovery_crud.get_or_create_settings(discovery_session)
    finally:
        discovery_session.close()

    batch_stats = run_control.get_batch_stats()
    eval_stats = run_control.get_eval_stats()

    return JSONResponse(
        {
            "quick_batch_enabled": settings.quick_batch_enabled,
            "batch_window_minutes": settings.batch_window_minutes,
            "batch_force_flush_size": settings.batch_force_flush_size,
            "batch_last_flush_at": batch_stats["last_flush_at"],
            "pending_count": pending_count(),
            "batch_evaluating": batch_stats["evaluating_batch"],
            "last_batch_size": batch_stats["last_batch_size"],
            "last_batch_skipped": batch_stats["last_batch_skipped"],
            "last_batch_proceeded": batch_stats["last_batch_proceeded"],
            "eval_in_flight": eval_stats["in_flight"],
            "eval_evaluated_count": eval_stats["evaluated_count"],
            "eval_passed_count": eval_stats["passed_count"],
            "eval_archived_count": eval_stats["archived_count"],
        }
    )


def _run_discovery_bootstrap(backlog_hours: int) -> None:
    logger.info("[bootstrap] run started")

    if run_control.should_skip_wayback():
        logger.info("[bootstrap] wayback skipped by request")
        run_control.set_phase("collecting")
    elif not run_control.is_cancelled():
        run_wayback_scan_cycle()

    if run_control.is_cancelled():
        logger.info("[bootstrap] cancelled after wayback")
        return

    logger.info("[bootstrap] starting initial collection (resumable)")
    run_initial_collection()

    if run_control.is_cancelled():
        logger.info("[bootstrap] cancelled after initial collection")
        return

    if backlog_hours and backlog_hours > 0:
        logger.info("[bootstrap] running backlog pass (%sh)", backlog_hours)
        run_backlog_pass(backlog_hours)
    else:
        logger.info("[bootstrap] backlog pass skipped (no age limit set)")

    logger.info("[bootstrap] entering continuous listening loop")
    cycle_count = 0
    while not run_control.is_cancelled():
        cycle_count += 1
        found = run_one_live_quantile_cycle()
        if run_control.is_cancelled():
            break

        discovery_session = DiscoverySessionLocal()
        try:
            settings = discovery_crud.get_or_create_settings(discovery_session)
            n_cycles = max(1, settings.empty_group_check_every_n_cycles)
        finally:
            discovery_session.close()

        if cycle_count % n_cycles == 0:
            found += run_empty_group_sweep()

        if run_control.is_cancelled():
            break

        if found:
            logger.info("[listening] cycle %s done, found %s new postings, pausing %ss before next cycle", cycle_count, found, PASS_GAP_SECONDS)
        run_control.wait_or_cancel(PASS_GAP_SECONDS)

    logger.info("[bootstrap] stopped")


@router.post("/discovery/start")
def start_discovery(skip_wayback: str = Form("")):
    discovery_session = DiscoverySessionLocal()
    try:
        settings = discovery_crud.update_settings(discovery_session, enabled=True)
        backlog_hours = settings.initial_backlog_hours
    finally:
        discovery_session.close()

    run_control.reset_run()
    if skip_wayback == "true":
        run_control.request_skip_wayback()
    else:
        run_control.request_skip_wayback_if_recent()
    submit_task(_run_discovery_bootstrap, backlog_hours)

    return JSONResponse({"status": "ok", "enabled": True})


@router.post("/discovery/skip-wayback")
def skip_wayback():
    run_control.request_skip_wayback()
    return JSONResponse({"status": "ok"})


@router.post("/discovery/catch-up")
def trigger_catch_up():
    submit_task(run_catch_up_pass)
    return JSONResponse({"status": "ok"})


@router.post("/discovery/stop")
def stop_discovery():
    run_control.cancel_run()
    discovery_session = DiscoverySessionLocal()
    try:
        discovery_crud.update_settings(discovery_session, enabled=False)
    finally:
        discovery_session.close()

    from core.discovery.posting_batch import pending_count, flush_now

    if pending_count() > 0:
        submit_task(flush_now)

    return JSONResponse({"status": "ok", "enabled": False})


@router.get("/discovery/status")
def discovery_status():
    discovery_session = DiscoverySessionLocal()
    try:
        settings = discovery_crud.get_or_create_settings(discovery_session)
        total_companies = discovery_session.query(DiscoveredCompany).filter(DiscoveredCompany.is_deleted.is_(False)).count()
        total_postings = discovery_session.query(DiscoveredJobPosting).count()

        postings_after_collection = 0
        companies_after_collection = 0
        if settings.initial_collection_done_at is not None:
            postings_after_collection = (
                discovery_session.query(DiscoveredJobPosting)
                .filter(DiscoveredJobPosting.first_seen_at >= settings.initial_collection_done_at)
                .count()
            )
            companies_after_collection = discovery_crud.count_companies_since(
                discovery_session, settings.initial_collection_done_at
            )
    finally:
        discovery_session.close()

    stats = run_control.get_stats()
    tier_found = run_control.get_tier_found_counts()
    tier_processed = run_control.get_tier_processed_counts()
    return JSONResponse(
        {
            "enabled": settings.enabled,
            "phase": stats["phase"],
            "current_tier": run_control.get_current_tier(),
            "tier_found_counts": {str(k): v for k, v in tier_found.items()},
            "tier_processed_counts": {str(k): v for k, v in tier_processed.items()},
            "new_companies_this_run": stats["new_companies_this_run"],
            "new_postings_this_run": stats["new_postings_this_run"],
            "total_companies": total_companies,
            "total_postings": total_postings,
            "postings_after_initial_collection": postings_after_collection,
            "companies_after_initial_collection": companies_after_collection,
            "initial_collection_done": settings.initial_collection_done_at is not None,
            "wayback_ats_done": stats["wayback_ats_done"],
            "wayback_ats_total": stats["wayback_ats_total"],
            "collection_checked": stats["collection_checked"],
            "collection_total": stats["collection_total"],
            "collection_done": stats["collection_done"],
            "screening_checked": stats["screening_checked"],
            "screening_total": stats["screening_total"],
            "screening_done": stats["screening_done"],
            "last_pass_duration_seconds": stats["last_pass_duration_seconds"],
        }
    )


@router.get("/discovery/metrics")
def discovery_metrics():
    from core.discovery.quantile_queue import LIVE_QUANTILE_COUNT

    discovery_session = DiscoverySessionLocal()
    try:
        rank_stats = discovery_crud.count_rank_quantile_stats(discovery_session)
    finally:
        discovery_session.close()

    avg_per_quantile = rank_stats["total_live"] / LIVE_QUANTILE_COUNT if rank_stats["total_live"] else 0
    duration_averages = run_control.get_quantile_duration_averages()

    return JSONResponse(
        {
            "total_all": rank_stats["total_all"],
            "total_live": rank_stats["total_live"],
            "total_empty": rank_stats["total_empty"],
            "avg_companies_per_quantile": avg_per_quantile,
            "quantile_avg_duration_seconds": {str(k): v for k, v in duration_averages.items()},
            "ats_checked_counts": run_control.get_ats_checked_counts(),
        }
    )


@router.post("/notifications")
def update_notifications(
    telegram_bot_token: str | None = Form(None),
    telegram_chat_id: str | None = Form(None),
    telegram_notify_enabled: str | None = Form(None),
    telegram_notify_only_successful: str | None = Form(None),
    telegram_notify_min_score: str | None = Form(None),
    session: Session = Depends(get_session),
):
    current = crud.get_app_settings(session) or crud.upsert_app_settings(session)

    resolved_token = telegram_bot_token if telegram_bot_token is not None else current.telegram_bot_token
    resolved_chat_id = telegram_chat_id if telegram_chat_id is not None else current.telegram_chat_id

    if telegram_notify_enabled == "true" and (not (resolved_token or "").strip() or not (resolved_chat_id or "").strip()):
        raise HTTPException(status_code=400, detail="Missing Telegram bot token or chat ID in settings")

    kwargs = {}
    if telegram_bot_token is not None:
        kwargs["telegram_bot_token"] = telegram_bot_token.strip() or None
    if telegram_chat_id is not None:
        kwargs["telegram_chat_id"] = telegram_chat_id.strip() or None
    if telegram_notify_enabled is not None:
        kwargs["telegram_notify_enabled"] = telegram_notify_enabled == "true"
    if telegram_notify_only_successful is not None:
        kwargs["telegram_notify_only_successful"] = telegram_notify_only_successful == "true"
    if telegram_notify_min_score is not None:
        kwargs["telegram_notify_min_score"] = int(telegram_notify_min_score) if telegram_notify_min_score.strip().isdigit() else None

    crud.upsert_app_settings(session, **kwargs)
    return JSONResponse({"status": "ok"})


@router.post("/wipe-data")
def wipe_data(session: Session = Depends(get_session)):
    from core.db.models import (
        Application,
        ApplicationChatMessage,
        Evaluation,
        FormQuestion,
        GapItem,
        JobPosting,
        QuestionChange,
        TailoredResume,
        TailoringChange,
        TailoringMessage,
        TailoringSession,
    )

    session.query(QuestionChange).delete(synchronize_session=False)
    session.query(ApplicationChatMessage).delete(synchronize_session=False)
    session.query(FormQuestion).delete(synchronize_session=False)
    session.query(Application).delete(synchronize_session=False)
    session.query(TailoredResume).delete(synchronize_session=False)
    session.query(GapItem).delete(synchronize_session=False)
    session.query(TailoringChange).delete(synchronize_session=False)
    session.query(TailoringMessage).delete(synchronize_session=False)
    session.query(TailoringSession).delete(synchronize_session=False)
    session.query(Evaluation).delete(synchronize_session=False)
    session.query(JobPosting).delete(synchronize_session=False)
    session.commit()

    discovery_session = DiscoverySessionLocal()
    try:
        discovery_session.query(DiscoveredJobPosting).delete(synchronize_session=False)
        discovery_session.query(DiscoveredCompany).delete(synchronize_session=False)
        discovery_crud.update_settings(
            discovery_session, last_wayback_run_at=None, initial_collection_done_at=None
        )
        discovery_session.commit()
    finally:
        discovery_session.close()

    return JSONResponse({"status": "ok"})