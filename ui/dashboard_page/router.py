from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

from core.currency.converter import CurrencyConversionError, convert_salary
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


def _derive_country(location: str | None) -> str | None:
    if not location:
        return None
    segment = location.split(";")[0].split(",")[-1].strip()
    return segment or None


def _convert_salary_for_display(salary: dict | None, preferred_currency: str, preferred_period: str) -> dict:
    if not salary or salary.get("min") is None:
        return {"text": None, "min_converted": None, "max_converted": None, "is_estimate": False}

    currency = salary.get("currency") or "USD"
    period = salary.get("period") or "year"
    is_estimate = bool(salary.get("is_estimate"))

    try:
        min_converted = convert_salary(salary["min"], currency, period, preferred_currency, preferred_period)
        max_converted = convert_salary(
            salary.get("max") or salary["min"], currency, period, preferred_currency, preferred_period
        )
    except CurrencyConversionError:
        return {
            "text": salary.get("original_text"),
            "min_converted": None,
            "max_converted": None,
            "is_estimate": is_estimate,
        }

    period_suffix = {"hour": "/hr", "month": "/mo", "year": "/yr"}.get(preferred_period, "")
    if round(min_converted) == round(max_converted):
        text = f"{round(min_converted):,} {preferred_currency}{period_suffix}"
    else:
        text = f"{round(min_converted):,}\u2013{round(max_converted):,} {preferred_currency}{period_suffix}"

    return {
        "text": text,
        "min_converted": min_converted,
        "max_converted": max_converted,
        "is_estimate": is_estimate,
    }


def _get_currency_prefs(session: Session) -> tuple[str, str]:
    app_settings = crud.get_app_settings(session)
    if app_settings is None:
        return "USD", "year"
    return app_settings.preferred_currency or "USD", app_settings.preferred_salary_period or "year"


def _card_data(job, preferred_currency: str, preferred_period: str) -> dict:
    latest_evaluation = job.evaluations[-1] if job.evaluations else None
    pending = job.pending_task_id is not None or job.activity_label is not None

    if latest_evaluation is None:
        return {
            "job_id": job.id,
            "company": job.company or "Unknown company",
            "role": job.title or "Unknown role",
            "score": None,
            "location": job.location,
            "country": _derive_country(job.location),
            "work_mode": job.work_mode,
            "employment_type": job.employment_type,
            "tags": job.tags or [],
            "salary_text": None,
            "salary_min_converted": None,
            "salary_max_converted": None,
            "is_estimate": False,
            "pending": pending,
            "activity_label": job.activity_label,
        }

    checked = latest_evaluation.checked_keywords or {}
    salary_display = _convert_salary_for_display(checked.get("salary"), preferred_currency, preferred_period)
    location = checked.get("location") or job.location

    return {
        "job_id": job.id,
        "company": job.company or "Unknown company",
        "role": job.title or "Unknown role",
        "score": latest_evaluation.fit_score,
        "location": location,
        "country": _derive_country(location),
        "work_mode": checked.get("work_mode") or job.work_mode,
        "employment_type": job.employment_type,
        "tags": job.tags or [],
        "salary_text": salary_display["text"],
        "salary_min_converted": salary_display["min_converted"],
        "salary_max_converted": salary_display["max_converted"],
        "is_estimate": salary_display["is_estimate"],
        "pending": pending,
        "activity_label": job.activity_label,
    }


@router.get("/jobs/{job_id}/card")
def job_card_data(job_id: int, session: Session = Depends(get_session)):
    job = crud.get_job_posting(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    currency, period = _get_currency_prefs(session)
    return JSONResponse(_card_data(job, currency, period))


@router.get("/", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    jobs = crud.list_job_postings(session, include_archived=False)
    currency, period = _get_currency_prefs(session)
    cards = [_card_data(job, currency, period) for job in jobs]

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "cards": cards,
            "lang": lang,
            "t": load_page_strings("ui/dashboard_page", lang),
        },
    )


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail_page(
    job_id: int,
    request: Request,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    job = crud.get_job_posting(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    evaluations = crud.list_evaluations_for_job(session, job_id)
    latest_evaluation = evaluations[0] if evaluations else None

    checked = (latest_evaluation.checked_keywords or {}) if latest_evaluation else {}
    salary = checked.get("salary") or {}

    return templates.TemplateResponse(
        "job_detail.html",
        {
            "request": request,
            "job": job,
            "evaluation": latest_evaluation,
            "score": latest_evaluation.fit_score if latest_evaluation else None,
            "location": checked.get("location"),
            "work_mode": checked.get("work_mode"),
            "salary": salary,
            "matched_factors": checked.get("matched_factors") or [],
            "summary": checked.get("summary"),
            "pros": (latest_evaluation.fit_bullets or {}).get("pros", []) if latest_evaluation else [],
            "cons": (latest_evaluation.blocker_bullets or {}).get("cons", []) if latest_evaluation else [],
            "lang": lang,
            "t": load_page_strings("ui/dashboard_page", lang),
        },
    )


@router.get("/jobs/{job_id}/evaluation")
def job_evaluation_data(job_id: int, session: Session = Depends(get_session)):
    job = crud.get_job_posting(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    evaluations = crud.list_evaluations_for_job(session, job_id)
    latest_evaluation = evaluations[0] if evaluations else None
    if latest_evaluation is None:
        return JSONResponse({"ready": False})

    checked = latest_evaluation.checked_keywords or {}
    salary = checked.get("salary") or {}

    return JSONResponse(
        {
            "ready": True,
            "company": job.company,
            "role": job.title,
            "score": latest_evaluation.fit_score,
            "location": checked.get("location"),
            "work_mode": checked.get("work_mode"),
            "salary": salary,
            "matched_factors": checked.get("matched_factors") or [],
            "pros": (latest_evaluation.fit_bullets or {}).get("pros", []),
            "cons": (latest_evaluation.blocker_bullets or {}).get("cons", []),
            "summary": checked.get("summary"),
        }
    )


@router.post("/jobs/{job_id}/archive")
def archive_job(job_id: int, session: Session = Depends(get_session)):
    crud.archive_job_posting(session, job_id)
    return JSONResponse({"status": "ok", "id": job_id})


@router.get("/archive", response_class=HTMLResponse)
def archive_page(
    request: Request,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    jobs = [job for job in crud.list_job_postings(session, include_archived=True) if job.archived]
    currency, period = _get_currency_prefs(session)
    cards = [_card_data(job, currency, period) for job in jobs]

    return templates.TemplateResponse(
        "archive.html",
        {
            "request": request,
            "cards": cards,
            "lang": lang,
            "t": load_page_strings("ui/dashboard_page", lang),
        },
    )


@router.post("/jobs/{job_id}/unarchive")
def unarchive_job(job_id: int, session: Session = Depends(get_session)):
    job = crud.unarchive_job_posting(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse({"status": "ok", "id": job_id})


@router.post("/jobs/{job_id}/delete-forever")
def delete_job_forever(job_id: int, session: Session = Depends(get_session)):
    deleted = crud.delete_job_posting(session, job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse({"status": "ok", "id": job_id})


@router.post("/jobs/{job_id}/start-application")
def start_application(job_id: int, session: Session = Depends(get_session)):
    job = crud.get_job_posting(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    existing = [
        app for app in crud.list_applications(session) if app.job_posting_id == job_id
    ]
    if existing:
        application = existing[0]
    else:
        application = crud.create_application(session, job_posting_id=job_id)

    return JSONResponse({"application_id": application.id})