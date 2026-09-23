from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

from core.db import crud
from core.db.session import get_session
from core.discovery.ats import default_target_sites
from core.discovery.backlog import run_backlog_pass
from core.discovery.poll_cycle import run_poll_tick
from core.discovery.wayback_scan import run_wayback_scan_cycle
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal
from core.tasks.executor import submit_task
from ui.common.i18n import get_language, load_page_strings

router = APIRouter(prefix="/automation")

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
            "base_questions": base_questions,
            "target_sites": DEFAULT_TARGET_SITES,
            "discovery_enabled": discovery_settings.enabled,
            "discovery_wayback_interval_hours": discovery_settings.wayback_interval_hours,
            "discovery_initial_backlog_hours": discovery_settings.initial_backlog_hours,
            "telegram_bot_token": app_settings.telegram_bot_token or "",
            "telegram_chat_id": app_settings.telegram_chat_id or "",
            "telegram_notify_enabled": app_settings.telegram_notify_enabled,
            "telegram_notify_only_successful": app_settings.telegram_notify_only_successful,
            "telegram_notify_min_score": app_settings.telegram_notify_min_score,
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
):
    discovery_session = DiscoverySessionLocal()
    try:
        kwargs = {}
        if wayback_interval_hours is not None:
            kwargs["wayback_interval_hours"] = max(1, wayback_interval_hours)
        if initial_backlog_hours is not None:
            kwargs["initial_backlog_hours"] = max(0, initial_backlog_hours)
        discovery_crud.update_settings(discovery_session, **kwargs)
    finally:
        discovery_session.close()

    return JSONResponse({"status": "ok"})


def _run_discovery_bootstrap(backlog_hours: int) -> None:
    import datetime

    session = DiscoverySessionLocal()
    try:
        settings = discovery_crud.get_or_create_settings(session)
        due = (
            settings.last_wayback_run_at is None
            or datetime.datetime.utcnow() - settings.last_wayback_run_at
            >= datetime.timedelta(hours=settings.wayback_interval_hours)
        )
    finally:
        session.close()

    if due:
        run_wayback_scan_cycle()

    run_poll_tick()
    run_backlog_pass(backlog_hours)


@router.post("/discovery/start")
def start_discovery():
    discovery_session = DiscoverySessionLocal()
    try:
        settings = discovery_crud.update_settings(discovery_session, enabled=True)
        backlog_hours = settings.initial_backlog_hours
    finally:
        discovery_session.close()

    submit_task(_run_discovery_bootstrap, backlog_hours)

    return JSONResponse({"status": "ok", "enabled": True})


@router.post("/discovery/stop")
def stop_discovery():
    discovery_session = DiscoverySessionLocal()
    try:
        discovery_crud.update_settings(discovery_session, enabled=False)
    finally:
        discovery_session.close()

    return JSONResponse({"status": "ok", "enabled": False})


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