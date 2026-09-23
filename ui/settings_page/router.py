import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

from core.currency.converter import SUPPORTED_CURRENCIES
from core.db import crud
from core.db.session import SessionLocal, get_session
from core.parsing.file_extraction import extract_text
from core.parsing.html_sanitize import sanitize_html
from core.parsing.html_to_text import html_to_text
from core.providers.factory import get_llm_provider
from core.structuring.html_pipeline import structure_resume_to_html
from core.tasks.runner import run_tracked_task
from ui.common.i18n import get_language, load_page_strings
import config

router = APIRouter(prefix="/settings")

templates = Jinja2Templates(directory="ui/settings_page/templates")
templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader("ui/settings_page/templates"),
        FileSystemLoader("ui/common/templates"),
    ]
)


def _save_upload(upload: UploadFile) -> str:
    destination = config.UPLOADS_DIR / upload.filename
    with open(destination, "wb") as file:
        shutil.copyfileobj(upload.file, file)
    return str(destination)


def _page_context(session: Session, request: Request, lang: str) -> dict:
    profile = crud.get_candidate_profile(session)
    active_resume = crud.get_active_resume_version(session, "resume")
    active_linkedin = crud.get_active_resume_version(session, "linkedin")
    blockers = crud.list_blocker_rules(session)
    scoring_factors = crud.list_scoring_factors(session)
    app_settings = crud.get_app_settings(session)

    return {
        "request": request,
        "profile": profile,
        "active_resume": active_resume,
        "active_linkedin": active_linkedin,
        "blockers": blockers,
        "scoring_factors": scoring_factors,
        "pregenerate_enabled": app_settings.pregenerate_enabled if app_settings else False,
        "pregenerate_min_score": app_settings.pregenerate_min_score if app_settings else 7,
        "auto_answer_questions_enabled": app_settings.auto_answer_questions_enabled if app_settings else True,
        "preferred_currency": app_settings.preferred_currency if app_settings else "USD",
        "preferred_salary_period": app_settings.preferred_salary_period if app_settings else "year",
        "supported_currencies": SUPPORTED_CURRENCIES,
        "lang": lang,
        "t": load_page_strings("ui/settings_page", lang),
    }


@router.get("", response_class=HTMLResponse)
def settings_page(
    request: Request,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    return templates.TemplateResponse("settings.html", _page_context(session, request, lang))


@router.post("/profile")
def update_profile(
    full_name: str = Form(""),
    email: str = Form(""),
    github_url: str = Form(""),
    linkedin_url: str = Form(""),
    extra_info: str = Form(""),
    session: Session = Depends(get_session),
):
    crud.upsert_candidate_profile(
        session,
        full_name=full_name or None,
        email=email or None,
        github_url=github_url or None,
        linkedin_url=linkedin_url or None,
        extra_info=extra_info or None,
    )

    return JSONResponse({"status": "ok"})


@router.post("/profile/writing-preferences")
def update_writing_preferences(writing_preferences: str = Form(""), session: Session = Depends(get_session)):
    crud.update_writing_preferences(session, writing_preferences)
    return JSONResponse({"status": "ok"})


@router.post("/profile/links")
def add_profile_link(link: str = Form(...), session: Session = Depends(get_session)):
    text = link.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Link cannot be empty")
    profile = crud.add_extra_link(session, text)
    return JSONResponse({"extra_links": profile.extra_links})


@router.post("/profile/links/{index}/delete")
def delete_profile_link(index: int, session: Session = Depends(get_session)):
    profile = crud.remove_extra_link(session, index)
    if profile is None:
        raise HTTPException(status_code=404, detail="Link not found")
    return JSONResponse({"extra_links": profile.extra_links})


@router.post("/resume")
def upload_resume(
    resume_file: UploadFile,
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    file_path = _save_upload(resume_file)
    raw_text = extract_text(file_path)

    task_id = run_tracked_task(
        "resume_structuring",
        _structure_and_save_resume,
        raw_text,
        resume_file.filename,
        lang,
    )

    return JSONResponse({"status": "processing", "task_id": task_id})


def _structure_and_save_resume(raw_text: str, filename: str, lang: str = "en") -> dict:
    session = SessionLocal()
    try:
        provider = get_llm_provider()
        content_html = structure_resume_to_html(provider, raw_text)

        resume = crud.create_resume_version(
            session,
            source_type="resume",
            raw_text=raw_text,
            content_html=content_html,
            label=filename,
            is_active=True,
        )
        return {"resume_version_id": resume.id, "content_html": content_html}
    finally:
        session.close()


@router.post("/resume/{resume_version_id}/edit-html")
def edit_resume_html(
    resume_version_id: int,
    html_content: str = Form(...),
    session: Session = Depends(get_session),
):
    cleaned = sanitize_html(html_content)
    plain_text = html_to_text(cleaned)
    resume = crud.update_resume_content(session, resume_version_id, content_html=cleaned, raw_text=plain_text)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    return JSONResponse({"status": "ok"})


@router.post("/linkedin/{resume_version_id}/edit-text")
def edit_linkedin_text(
    resume_version_id: int,
    raw_text: str = Form(...),
    session: Session = Depends(get_session),
):
    resume = crud.update_resume_content(session, resume_version_id, raw_text=raw_text)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    return JSONResponse({"status": "ok"})


@router.post("/linkedin")
def submit_linkedin(
    linkedin_text: str = Form(...),
    session: Session = Depends(get_session),
):
    resume = crud.create_resume_version(
        session,
        source_type="linkedin",
        raw_text=linkedin_text,
        label="LinkedIn experience",
        is_active=True,
    )
    return JSONResponse({"resume_version_id": resume.id})


@router.post("/blockers")
def add_blocker(text: str = Form(...), session: Session = Depends(get_session)):
    existing = crud.list_blocker_rules(session)
    blocker = crud.create_blocker_rule(session, text=text, order=len(existing))
    return JSONResponse({"id": blocker.id, "text": blocker.text})


@router.post("/blockers/{blocker_id}/delete")
def delete_blocker(blocker_id: int, session: Session = Depends(get_session)):
    crud.delete_blocker_rule(session, blocker_id)
    return JSONResponse({"status": "ok", "id": blocker_id})


@router.post("/scoring-factors")
def add_scoring_factor(
    text: str = Form(...),
    direction: str = Form(...),
    weight: int = Form(...),
    session: Session = Depends(get_session),
):
    existing = crud.list_scoring_factors(session)
    factor = crud.create_scoring_factor(
        session, text=text, direction=direction, weight=weight, order=len(existing)
    )
    return JSONResponse(
        {"id": factor.id, "text": factor.text, "direction": factor.direction, "weight": factor.weight}
    )


@router.post("/scoring-factors/{factor_id}/delete")
def delete_scoring_factor(factor_id: int, session: Session = Depends(get_session)):
    crud.delete_scoring_factor(session, factor_id)
    return JSONResponse({"status": "ok", "id": factor_id})


@router.post("/pregenerate")
def update_pregenerate_settings(
    pregenerate_enabled: bool = Form(False),
    pregenerate_min_score: int = Form(7),
    session: Session = Depends(get_session),
):
    crud.upsert_app_settings(
        session,
        pregenerate_enabled=pregenerate_enabled,
        pregenerate_min_score=pregenerate_min_score,
    )
    return JSONResponse({"status": "ok"})


@router.post("/auto-answer")
def update_auto_answer_settings(
    auto_answer_questions_enabled: bool = Form(False),
    session: Session = Depends(get_session),
):
    crud.upsert_app_settings(
        session,
        auto_answer_questions_enabled=auto_answer_questions_enabled,
    )
    return JSONResponse({"status": "ok"})


@router.post("/salary-preferences")
def update_salary_preferences(
    preferred_currency: str = Form(...),
    preferred_salary_period: str = Form(...),
    session: Session = Depends(get_session),
):
    if preferred_currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(status_code=400, detail="Unsupported currency")
    if preferred_salary_period not in ("hour", "month", "year"):
        raise HTTPException(status_code=400, detail="Invalid period")

    crud.upsert_app_settings(
        session,
        preferred_currency=preferred_currency,
        preferred_salary_period=preferred_salary_period,
    )
    return JSONResponse({"status": "ok"})