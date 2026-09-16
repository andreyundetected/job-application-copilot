from sqlalchemy.orm import Session

from core.db.models import JobPosting


def create_job_posting(
    session: Session,
    raw_text: str,
    company: str | None = None,
    title: str | None = None,
    source_url: str | None = None,
) -> JobPosting:
    job = JobPosting(
        raw_text=raw_text, company=company, title=title, source_url=source_url
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def get_job_posting(session: Session, job_posting_id: int) -> JobPosting | None:
    return session.get(JobPosting, job_posting_id)


def list_job_postings(session: Session) -> list[JobPosting]:
    return session.query(JobPosting).order_by(JobPosting.created_at.desc()).all()


def delete_job_posting(session: Session, job_posting_id: int) -> bool:
    job = session.get(JobPosting, job_posting_id)
    if job is None:
        return False
    session.delete(job)
    session.commit()
    return True