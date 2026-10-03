import hashlib
from pathlib import Path

from sqlalchemy.orm import Session

from core.db import crud

_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "evaluator_prompt.jinja"


def _prompt_fingerprint() -> str:
    try:
        return hashlib.sha1(_TEMPLATE_PATH.read_bytes()).hexdigest()[:10]
    except OSError:
        return "unknown"


def apply_quick_meta(session: Session, job_posting_id: int, quick: dict) -> None:
    crud.update_job_quick_meta(
        session,
        job_posting_id,
        company=quick.get("company"),
        title=quick.get("role"),
        location=quick.get("location"),
        location_country=quick.get("location_country"),
        location_state=quick.get("location_state"),
        location_city=quick.get("location_city"),
        work_mode=quick.get("work_mode"),
        employment_type=quick.get("employment_type"),
        tags=quick.get("tags"),
    )


def build_checked_keywords(quick: dict, result: dict) -> dict:
    return {
        "location": quick.get("location"),
        "work_mode": quick.get("work_mode"),
        "salary": quick.get("salary") or {},
        "matched_factors": result["matched_factors"],
        "summary": quick.get("summary"),
        "raw_response": result.get("raw_response"),
        "prompt_hash": _prompt_fingerprint(),
    }


def store_evaluation(session: Session, job_posting_id: int, resume_version_id: int, quick: dict, result: dict):
    return crud.create_evaluation(
        session,
        job_posting_id=job_posting_id,
        resume_version_id=resume_version_id,
        verdict=result["verdict"],
        blocker_bullets={"cons": result["cons"]},
        fit_score=result["score"],
        fit_bullets={"pros": result["pros"]},
        checked_keywords=build_checked_keywords(quick, result),
        triggered_blockers=result.get("triggered_blockers") or [],
    )