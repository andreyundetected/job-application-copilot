from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.db import crud
from core.db.session import SessionLocal, get_session
from core.evaluator.pipeline import evaluate_job_posting, quick_extract_job_posting
from core.providers.factory import get_llm_provider
from core.tasks.runner import run_tracked_task

from jinja2 import ChoiceLoader, FileSystemLoader

from ui.common.i18n import get_language, load_page_strings

router = APIRouter(prefix="/evaluator")

templates = Jinja2Templates(directory="ui/evaluator_page/templates")
templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader("ui/evaluator_page/templates"),
        FileSystemLoader("ui/common/templates"),
    ]
)


@router.get("", response_class=HTMLResponse)
def evaluator_page(
    request: Request,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    blockers = crud.list_blocker_rules(session)
    scoring_factors = crud.list_scoring_factors(session)
    active_resume = crud.get_active_resume_version(session, "resume")
    active_linkedin = crud.get_active_resume_version(session, "linkedin")

    return templates.TemplateResponse(
        "evaluator.html",
        {
            "request": request,
            "blockers": blockers,
            "scoring_factors": scoring_factors,
            "active_resume": active_resume,
            "active_linkedin": active_linkedin,
            "result": None,
            "lang": lang,
            "t": load_page_strings("ui/evaluator_page", lang),
        },
    )


@router.post("")
def run_evaluation(
    job_posting_text: str = Form(...),
    extra_info: str = Form(""),
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    job = crud.create_job_posting(session, raw_text=job_posting_text)

    task_id = run_tracked_task(
        "job_quick_extract", _quick_extract_and_save, job.id, job_posting_text, extra_info or None, lang
    )
    crud.set_job_pending_task(session, job.id, task_id)

    return JSONResponse({"status": "processing", "task_id": task_id, "job_id": job.id})


def _quick_extract_and_save(
    job_posting_id: int, job_posting_text: str, extra_info: str | None, lang: str = "en"
) -> dict:
    session = SessionLocal()
    try:
        provider = get_llm_provider()
        quick_result = quick_extract_job_posting(provider, job_posting_text)

        crud.update_job_quick_meta(
            session,
            job_posting_id,
            company=quick_result["company"],
            title=quick_result["role"],
            location=quick_result["location"],
            work_mode=quick_result["work_mode"],
            employment_type=quick_result["employment_type"],
            tags=quick_result["tags"],
        )

        full_task_id = run_tracked_task(
            "job_full_evaluation",
            _evaluate_and_save,
            job_posting_id,
            job_posting_text,
            extra_info,
            lang,
        )
        crud.set_job_pending_task(session, job_posting_id, full_task_id)

        return quick_result
    finally:
        session.close()


def _evaluate_and_save(
    job_posting_id: int, job_posting_text: str, extra_info: str | None, lang: str = "en"
) -> dict:
    session = SessionLocal()
    try:
        blockers = crud.list_blocker_rules(session)
        scoring_factors = crud.list_scoring_factors(session)
        resume = crud.get_active_resume_version(session, "resume")
        linkedin = crud.get_active_resume_version(session, "linkedin")

        provider = get_llm_provider()

        result = evaluate_job_posting(
            provider,
            job_posting_text=job_posting_text,
            resume_text=resume.raw_text,
            linkedin_text=linkedin.raw_text,
            blockers=[rule.text for rule in blockers],
            scoring_factors=[
                {
                    "id": factor.id,
                    "text": factor.text,
                    "direction": factor.direction,
                    "weight": factor.weight,
                }
                for factor in scoring_factors
            ],
            extra_info=extra_info,
            language=lang,
        )

        crud.update_job_quick_meta(
            session,
            job_posting_id,
            company=result["company"],
            title=result["role"],
            location=result["location"],
            work_mode=result["work_mode"],
        )

        crud.create_evaluation(
            session,
            job_posting_id=job_posting_id,
            resume_version_id=resume.id,
            verdict=result["verdict"],
            blocker_bullets={"cons": result["cons"]},
            fit_score=result["score"],
            fit_bullets={"pros": result["pros"]},
            checked_keywords={
                "location": result["location"],
                "work_mode": result["work_mode"],
                "salary": result["salary"],
                "matched_factors": result["matched_factors"],
                "summary": result["summary"],
            },
        )

        crud.set_job_pending_task(session, job_posting_id, None)

        return result
    finally:
        session.close()