from sqlalchemy.orm import Session

from core.db import crud
from core.parsing.html_blocks import normalize_elements, split_top_level
from core.providers.factory import get_llm_provider
from core.structuring.block_detection import detect_blocks


def ensure_resume_blocks(session: Session, resume, provider=None):
    html, blocks = normalize_elements(resume.content_html or "", resume.blocks)
    if resume.blocks is None:
        blocks = detect_blocks(provider or get_llm_provider(), html)
    if html != (resume.content_html or ""):
        crud.update_resume_content(session, resume.id, content_html=html)
    if blocks != resume.blocks:
        crud.set_resume_blocks(session, resume.id, blocks)
    return crud.get_resume_version(session, resume.id)


def ensure_session_blocks(session: Session, tailoring_session):
    if tailoring_session.blocks is not None:
        return tailoring_session

    resume = crud.get_resume_version(session, tailoring_session.resume_version_id)
    resume = ensure_resume_blocks(session, resume)
    blocks = resume.blocks or []
    working_html = tailoring_session.working_html or ""
    present = {element["eid"] for element in split_top_level(working_html)}

    if blocks and not any(eid in present for block in blocks for eid in block["element_ids"]):
        working_html = resume.content_html or ""
        crud.update_working_html(session, tailoring_session.id, working_html)
    else:
        normalized, blocks = normalize_elements(working_html, blocks)
        if normalized != working_html:
            crud.update_working_html(session, tailoring_session.id, normalized)

    crud.set_session_blocks(session, tailoring_session.id, blocks)
    return crud.get_tailoring_session(session, tailoring_session.id)