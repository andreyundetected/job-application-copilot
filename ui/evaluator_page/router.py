from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.db import crud
from core.db.session import get_session
from core.evaluator.pipeline import evaluate_job_posting
from core.providers.factory import get_llm_provider

from jinja2 import ChoiceLoader, FileSystemLoader

router = APIRouter(prefix="/evaluator")

templates = Jinja2Templates(directory="ui/evaluator_page/templates")
templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader("ui/evaluator_page/templates"),
        FileSystemLoader("ui/common/templates"),
    ]
)


@router.get("", response_class=HTMLResponse)
def evaluator_page(request: Request, session: Session = Depends(get_session)):
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
        },
    )


@router.post("", response_class=HTMLResponse)
def run_evaluation(
    request: Request,
    job_posting_text: str = Form(...),
    extra_info: str = Form(""),
    session: Session = Depends(get_session),
):
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
        extra_info=extra_info or None,
    )

    job = crud.create_job_posting(
        session,
        raw_text=job_posting_text,
        company=result["company"],
        title=result["role"],
    )

    crud.create_evaluation(
        session,
        job_posting_id=job.id,
        resume_version_id=resume.id,
        verdict=result["verdict"],
        blocker_bullets={"cons": result["cons"]},
        fit_score=result["score"],
        fit_bullets={"pros": result["pros"]},
        checked_keywords={
            "location": result["location"],
            "work_mode": result["work_mode"],
            "salary": result["salary"],
        },
    )

    return templates.TemplateResponse(
        "evaluator.html",
        {
            "request": request,
            "blockers": blockers,
            "scoring_factors": scoring_factors,
            "active_resume": resume,
            "active_linkedin": linkedin,
            "result": result,
            "job_posting_text": job_posting_text,
        },
    )