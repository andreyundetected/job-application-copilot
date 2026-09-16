import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

from core.db import crud
from core.db.session import SessionLocal, get_session
from core.parsing.file_extraction import extract_text
from core.providers.factory import get_llm_provider
from core.structuring.pipeline import structure_linkedin_text, structure_resume_text
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

    return {
        "request": request,
        "profile": profile,
        "active_resume": active_resume,
        "active_linkedin": active_linkedin,
        "blockers": blockers,
        "scoring_factors": scoring_factors,
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
    email: str = Form(""),
    github_url: str = Form(""),
    linkedin_url: str = Form(""),
    extra_links_text: str = Form(""),
    extra_info: str = Form(""),
    session: Session = Depends(get_session),
):
    extra_links = [line.strip() for line in extra_links_text.splitlines() if line.strip()]

    crud.upsert_candidate_profile(
        session,
        email=email or None,
        github_url=github_url or None,
        linkedin_url=linkedin_url or None,
        extra_links=extra_links,
        extra_info=extra_info or None,
    )

    return JSONResponse({"status": "ok"})


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
        structured_content = structure_resume_text(provider, raw_text, language=lang)

        resume = crud.create_resume_version(
            session,
            source_type="resume",
            raw_text=raw_text,
            structured_content=structured_content,
            label=filename,
            is_active=True,
        )
        return {"resume_version_id": resume.id, "structured_content": structured_content}
    finally:
        session.close()


@router.post("/linkedin")
def submit_linkedin(
    linkedin_text: str = Form(...),
    session: Session = Depends(get_session),
    lang: str = Depends(get_language),
):
    task_id = run_tracked_task(
        "linkedin_structuring", _structure_and_save_linkedin, linkedin_text, lang
    )
    return JSONResponse({"status": "processing", "task_id": task_id})


def _structure_and_save_linkedin(linkedin_text: str, lang: str = "en") -> dict:
    session = SessionLocal()
    try:
        provider = get_llm_provider()
        structured_content = structure_linkedin_text(provider, linkedin_text, language=lang)

        resume = crud.create_resume_version(
            session,
            source_type="linkedin",
            raw_text=linkedin_text,
            structured_content=structured_content,
            label="LinkedIn experience",
            is_active=True,
        )
        return {"resume_version_id": resume.id, "structured_content": structured_content}
    finally:
        session.close()


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