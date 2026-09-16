from sqlalchemy.orm import Session

from core.db.models import Evaluation


def create_evaluation(
    session: Session,
    job_posting_id: int,
    resume_version_id: int,
    verdict: bool,
    blocker_bullets: dict | None = None,
    fit_score: int | None = None,
    fit_bullets: dict | None = None,
    checked_keywords: dict | None = None,
) -> Evaluation:
    evaluation = Evaluation(
        job_posting_id=job_posting_id,
        resume_version_id=resume_version_id,
        verdict=verdict,
        blocker_bullets=blocker_bullets,
        fit_score=fit_score,
        fit_bullets=fit_bullets,
        checked_keywords=checked_keywords,
    )
    session.add(evaluation)
    session.commit()
    session.refresh(evaluation)
    return evaluation


def get_evaluation(session: Session, evaluation_id: int) -> Evaluation | None:
    return session.get(Evaluation, evaluation_id)


def list_evaluations_for_job(
    session: Session, job_posting_id: int
) -> list[Evaluation]:
    return (
        session.query(Evaluation)
        .filter(Evaluation.job_posting_id == job_posting_id)
        .order_by(Evaluation.created_at.desc())
        .all()
    )


def list_passed_evaluations(session: Session) -> list[Evaluation]:
    return (
        session.query(Evaluation)
        .filter(Evaluation.verdict.is_(True))
        .order_by(Evaluation.created_at.desc())
        .all()
    )