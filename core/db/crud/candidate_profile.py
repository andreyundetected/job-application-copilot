from sqlalchemy.orm import Session

from core.db.models import CandidateProfile


def get_candidate_profile(session: Session) -> CandidateProfile | None:
    return session.query(CandidateProfile).first()


def upsert_candidate_profile(
    session: Session,
    full_name: str | None = None,
    email: str | None = None,
    github_url: str | None = None,
    linkedin_url: str | None = None,
    extra_info: str | None = None,
) -> CandidateProfile:
    profile = session.query(CandidateProfile).first()

    if profile is None:
        profile = CandidateProfile()
        session.add(profile)

    profile.full_name = full_name
    profile.email = email
    profile.github_url = github_url
    profile.linkedin_url = linkedin_url
    profile.extra_info = extra_info

    session.commit()
    session.refresh(profile)
    return profile


def add_extra_link(session: Session, link: str) -> CandidateProfile:
    profile = session.query(CandidateProfile).first()
    if profile is None:
        profile = CandidateProfile()
        session.add(profile)
        session.flush()

    links = list(profile.extra_links or [])
    links.append(link)
    profile.extra_links = links

    session.commit()
    session.refresh(profile)
    return profile


def remove_extra_link(session: Session, index: int) -> CandidateProfile | None:
    profile = session.query(CandidateProfile).first()
    if profile is None:
        return None

    links = list(profile.extra_links or [])
    if index < 0 or index >= len(links):
        return None

    links.pop(index)
    profile.extra_links = links

    session.commit()
    session.refresh(profile)
    return profile