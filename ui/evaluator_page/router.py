from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from core.automation.pipeline import maybe_auto_answer_base_questions, maybe_auto_tailor
from core.db import crud
from core.db.session import SessionLocal, get_session
from core.evaluator.pipeline import evaluate_job_posting, quick_extract_job_posting
from core.providers.factory import get_llm_provider
from core.tasks.runner import run_tracked_task

from jinja2 import ChoiceLoader, FileSystemLoader

from ui.common.i18n import get_language, load_page_strings

router = APIRouter(prefix="/evaluator")

_TAILORING_MATRIX = [
    ("soft", "title"),
    ("soft", "company_name"),
    ("soft", "skills"),
    ("medium", "summary"),
    ("medium", "bullet"),
]


def _tailoring_matrix_state(session: Session) -> list[dict]:
    return [
        {
            "level": level,
            "change_type": change_type,
            "auto_apply": crud.manual_assist_is_auto_apply(session, level, change_type),
        }
        for level, change_type in _TAILORING_MATRIX
    ]

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
    profile = crud.get_candidate_profile(session)

    return templates.TemplateResponse(
        "evaluator.html",
        {
            "request": request,
            "blockers": blockers,
            "scoring_factors": scoring_factors,
            "active_resume": active_resume,
            "active_linkedin": active_linkedin,
            "profile": profile,
            "tailoring_matrix": _tailoring_matrix_state(session),
            "base_questions": crud.list_manual_assist_base_questions(session),
            "manual_assist_min_score": (crud.get_app_settings(session) or crud.upsert_app_settings(session)).manual_assist_min_score,
            "result": None,
            "lang": lang,
            "t": load_page_strings("ui/evaluator_page", lang),
        },
    )


@router.post("/manual-assist/min-score")
def update_manual_assist_min_score(
    manual_assist_min_score: int = Form(...),
    session: Session = Depends(get_session),
):
    crud.upsert_app_settings(session, manual_assist_min_score=manual_assist_min_score)
    return JSONResponse({"status": "ok"})


@router.post("/manual-assist/tailoring-permissions")
def update_manual_assist_permission(
    level: str = Form(...),
    change_type: str = Form(...),
    auto_apply: bool = Form(False),
    session: Session = Depends(get_session),
):
    if (level, change_type) not in _TAILORING_MATRIX:
        raise HTTPException(status_code=400, detail="Unknown level/change_type combination")
    crud.set_manual_assist_tailoring_permission(session, level=level, change_type=change_type, auto_apply=auto_apply)
    return JSONResponse({"status": "ok"})


@router.post("/manual-assist/base-questions")
def add_manual_assist_base_question(question_text: str = Form(...), session: Session = Depends(get_session)):
    text = question_text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Question text cannot be empty")
    question = crud.create_manual_assist_base_question(session, question_text=text)
    return JSONResponse({"id": question.id, "question_text": question.question_text})


@router.post("/manual-assist/base-questions/{question_id}/delete")
def delete_manual_assist_base_question(question_id: int, session: Session = Depends(get_session)):
    crud.delete_manual_assist_base_question(session, question_id)
    return JSONResponse({"status": "ok", "id": question_id})


@router.post("")
def run_evaluation(
    job_posting_text: str = Form(...),
    extra_info: str = Form(""),
    source_url: str = Form(""),
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    job = crud.create_job_posting(session, raw_text=job_posting_text, source_url=source_url or None)
    crud.set_job_activity(session, job.id, "Evaluating fit...")

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
            location_country=quick_result["location_country"],
            location_state=quick_result["location_state"],
            location_city=quick_result["location_city"],
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
            location_country=result["location_country"],
            location_state=result["location_state"],
            location_city=result["location_city"],
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
        crud.ensure_draft_application(session, job_posting_id, source_platform="manual")

        crud.set_job_pending_task(session, job_posting_id, None)
        crud.set_job_activity(session, job_posting_id, None)

        app_settings = crud.get_app_settings(session)
        score = result["score"]
        if (
            app_settings
            and app_settings.pregenerate_enabled
            and score is not None
            and score >= app_settings.pregenerate_min_score
        ):
            from ui.tailoring_page.router import pregenerate_tailoring_context

            run_tracked_task("tailoring_pregenerate", pregenerate_tailoring_context, job_posting_id, lang)

        app_settings_for_threshold = crud.get_app_settings(session)
        manual_assist_min_score = app_settings_for_threshold.manual_assist_min_score if app_settings_for_threshold else 7
        if score is not None and score >= manual_assist_min_score:
            job = crud.get_job_posting(session, job_posting_id)
            if job is not None:
                maybe_auto_tailor(
                    session,
                    None,
                    job,
                    job_posting_text,
                    result,
                    level_has_auto_apply=crud.manual_assist_level_has_auto_apply,
                    is_auto_apply=crud.manual_assist_is_auto_apply,
                )
                maybe_auto_answer_base_questions(
                    session, None, job, job_posting_text, list_base_questions=crud.list_manual_assist_base_questions
                )

        return result
    finally:
        session.close()