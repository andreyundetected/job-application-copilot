import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

from core.db import crud
from core.db.session import get_session
from ui.common.i18n import get_language, load_page_strings

router = APIRouter(prefix="/tracker")

templates = Jinja2Templates(directory="ui/tracker_page/templates")
templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader("ui/tracker_page/templates"),
        FileSystemLoader("ui/common/templates"),
    ]
)

STATUSES = ["draft", "applied", "interviewing", "offer", "rejected", "withdrawn"]


def _serialize_card(application, job, evaluation) -> dict:
    checked = (evaluation.checked_keywords or {}) if evaluation else {}
    salary = checked.get("salary") or {}

    return {
        "application_id": application.id,
        "job_id": job.id if job else None,
        "status": application.status,
        "company": job.company if job else None,
        "role": job.title if job else None,
        "location": checked.get("location") or (job.location if job else None),
        "work_mode": checked.get("work_mode") or (job.work_mode if job else None),
        "score": evaluation.fit_score if evaluation else None,
        "salary_text": salary.get("original_text"),
        "source_platform": application.source_platform,
        "applied_at": application.applied_at.isoformat() if application.applied_at else None,
        "interview_at": application.interview_at.isoformat() if application.interview_at else None,
        "interview_notes": application.interview_notes,
        "created_at": application.created_at.isoformat() if application.created_at else None,
    }


def _gather_board(session: Session) -> dict:
    applications = crud.list_applications(session)
    columns: dict[str, list] = {status: [] for status in STATUSES}

    for application in applications:
        job = crud.get_job_posting(session, application.job_posting_id)
        evaluations = crud.list_evaluations_for_job(session, application.job_posting_id) if job else []
        latest_evaluation = evaluations[0] if evaluations else None
        card = _serialize_card(application, job, latest_evaluation)
        columns.setdefault(application.status, [])
        columns[application.status].append(card)

    for status in columns:
        columns[status].sort(key=lambda c: c["created_at"] or "", reverse=True)

    return columns


@router.get("", response_class=HTMLResponse)
def tracker_page(
    request: Request,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    columns = _gather_board(session)

    return templates.TemplateResponse(
        "tracker.html",
        {
            "request": request,
            "columns": columns,
            "statuses": STATUSES,
            "lang": lang,
            "t": load_page_strings("ui/tracker_page", lang),
        },
    )


@router.get("/board")
def tracker_board_data(session: Session = Depends(get_session)):
    return JSONResponse({"columns": _gather_board(session)})


@router.post("/applications/{application_id}/move")
def move_application(
    application_id: int,
    status: str = Form(...),
    session: Session = Depends(get_session),
):
    if status not in STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    application = crud.move_application_status(session, application_id, status)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    return JSONResponse({"status": "ok"})


@router.post("/applications/{application_id}/interview")
def set_interview(
    application_id: int,
    interview_at: str = Form(""),
    interview_notes: str = Form(""),
    session: Session = Depends(get_session),
):
    parsed_dt = None
    if interview_at.strip():
        try:
            parsed_dt = datetime.datetime.fromisoformat(interview_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid datetime")

    application = crud.update_application_interview(
        session, application_id, interview_at=parsed_dt, interview_notes=interview_notes or None
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    return JSONResponse({"status": "ok"})


@router.post("/applications/{application_id}/delete")
def delete_application(application_id: int, session: Session = Depends(get_session)):
    deleted = crud.delete_application(session, application_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found")
    return JSONResponse({"status": "ok"})