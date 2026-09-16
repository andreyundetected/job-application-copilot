from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

from core.db import crud
from core.db.session import get_session
from ui.common.i18n import get_language, load_page_strings

router = APIRouter(prefix="")

templates = Jinja2Templates(directory="ui/dashboard_page/templates")
templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader("ui/dashboard_page/templates"),
        FileSystemLoader("ui/common/templates"),
    ]
)


def _card_data(job) -> dict:
    latest_evaluation = job.evaluations[-1] if job.evaluations else None

    if latest_evaluation is None:
        return {
            "job_id": job.id,
            "company": job.company or "Unknown company",
            "role": job.title or "Unknown role",
            "score": None,
            "location": None,
            "work_mode": None,
            "salary_text": None,
            "is_estimate": False,
        }

    checked = latest_evaluation.checked_keywords or {}
    salary = checked.get("salary") or {}

    return {
        "job_id": job.id,
        "company": job.company or "Unknown company",
        "role": job.title or "Unknown role",
        "score": latest_evaluation.fit_score,
        "location": checked.get("location"),
        "work_mode": checked.get("work_mode"),
        "salary_text": salary.get("original_text"),
        "is_estimate": salary.get("is_estimate", False),
    }


@router.get("/", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    jobs = crud.list_job_postings(session, include_archived=False)
    cards = [_card_data(job) for job in jobs]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "cards": cards,
            "lang": lang,
            "t": load_page_strings("ui/dashboard_page", lang),
        },
    )


@router.post("/jobs/{job_id}/archive")
def archive_job(job_id: int, session: Session = Depends(get_session)):
    crud.archive_job_posting(session, job_id)
    return JSONResponse({"status": "ok", "id": job_id})