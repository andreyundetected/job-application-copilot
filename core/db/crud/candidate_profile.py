from sqlalchemy.orm import Session

from core.db.models import CandidateProfile


def get_candidate_profile(session: Session) -> CandidateProfile | None:
    return session.query(CandidateProfile).first()


def upsert_candidate_profile(
    session: Session,
    email: str | None = None,
    github_url: str | None = None,
    linkedin_url: str | None = None,
    extra_links: list | None = None,
    extra_info: str | None = None,
) -> CandidateProfile:
    profile = session.query(CandidateProfile).first()

    if profile is None:
        profile = CandidateProfile()
        session.add(profile)

    profile.email = email
    profile.github_url = github_url
    profile.linkedin_url = linkedin_url
    profile.extra_links = extra_links or []
    profile.extra_info = extra_info

    session.commit()
    session.refresh(profile)
    return profile