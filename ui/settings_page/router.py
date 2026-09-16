import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader
from sqlalchemy.orm import Session

from core.db import crud
from core.db.session import get_session
from core.parsing.file_extraction import extract_text
from core.providers.factory import get_llm_provider
from core.structuring.pipeline import structure_linkedin_text, structure_resume_text
import config

router = APIRouter(prefix="/settings")

templates = Jinja2Templates(directory="ui/settings_page/templates")
templates.env.loader = ChoiceLoader(
    [
        FileSystemLoader("ui/settings_page/templates"),
        FileSystemLoader("ui/common/templates"),
    ]
)

UPLOADS_DIR = config.DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)


def _save_upload(upload: UploadFile) -> str:
    destination = UPLOADS_DIR / upload.filename
    with open(destination, "wb") as file:
        shutil.copyfileobj(upload.file, file)
    return str(destination)


def _page_context(session: Session, request: Request) -> dict:
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
    }


@router.get("", response_class=HTMLResponse)
def settings_page(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse("settings.html", _page_context(session, request))


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

    return RedirectResponse(url="/settings", status_code=303)


@router.post("/resume")
def upload_resume(resume_file: UploadFile, session: Session = Depends(get_session)):
    file_path = _save_upload(resume_file)
    raw_text = extract_text(file_path)

    provider = get_llm_provider()
    structured_content = structure_resume_text(provider, raw_text)

    crud.create_resume_version(
        session,
        source_type="resume",
        raw_text=raw_text,
        structured_content=structured_content,
        label=resume_file.filename,
        is_active=True,
    )

    return RedirectResponse(url="/settings", status_code=303)


@router.post("/linkedin")
def submit_linkedin(linkedin_text: str = Form(...), session: Session = Depends(get_session)):
    provider = get_llm_provider()
    structured_content = structure_linkedin_text(provider, linkedin_text)

    crud.create_resume_version(
        session,
        source_type="linkedin",
        raw_text=linkedin_text,
        structured_content=structured_content,
        label="LinkedIn experience",
        is_active=True,
    )

    return RedirectResponse(url="/settings", status_code=303)


@router.post("/blockers")
def add_blocker(text: str = Form(...), session: Session = Depends(get_session)):
    existing = crud.list_blocker_rules(session)
    crud.create_blocker_rule(session, text=text, order=len(existing))
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/blockers/{blocker_id}/delete")
def delete_blocker(blocker_id: int, session: Session = Depends(get_session)):
    crud.delete_blocker_rule(session, blocker_id)
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/scoring-factors")
def add_scoring_factor(
    text: str = Form(...),
    direction: str = Form(...),
    weight: int = Form(...),
    session: Session = Depends(get_session),
):
    existing = crud.list_scoring_factors(session)
    crud.create_scoring_factor(
        session, text=text, direction=direction, weight=weight, order=len(existing)
    )
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/scoring-factors/{factor_id}/delete")
def delete_scoring_factor(factor_id: int, session: Session = Depends(get_session)):
    crud.delete_scoring_factor(session, factor_id)
    return RedirectResponse(url="/settings", status_code=303)