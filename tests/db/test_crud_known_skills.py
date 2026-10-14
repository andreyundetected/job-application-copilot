import pytest

from core.db.crud import gap_items as gap_items_crud
from core.db.crud import jobs as jobs_crud
from core.db.crud import known_skills as known_skills_crud
from core.db.crud import resumes as resumes_crud
from core.db.crud import tailoring_sessions as tailoring_sessions_crud


def _make_session(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job")
    resume = resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume")
    return tailoring_sessions_crud.create_tailoring_session(
        db_session, job_posting_id=job.id, resume_version_id=resume.id, working_content={}
    )


@pytest.mark.db
def test_add_known_skills_dedupes_by_normalized_text(db_session):
    created = known_skills_crud.add_known_skills(db_session, ["Docker", "docker ", "Node.js"])

    assert created == 2
    assert [skill.text for skill in known_skills_crud.list_known_skills(db_session)] == ["Docker", "Node.js"]


@pytest.mark.db
def test_delete_known_skill(db_session):
    known_skills_crud.add_known_skills(db_session, ["Docker"])
    skill = known_skills_crud.list_known_skills(db_session)[0]

    assert known_skills_crud.delete_known_skill(db_session, skill.id) is True
    assert known_skills_crud.list_known_skills(db_session) == []


@pytest.mark.db
def test_promote_unknown_gap_items_switches_status_to_can_add(db_session):
    session = _make_session(db_session)
    gap_items_crud.bulk_create_gap_items(
        db_session,
        session.id,
        [{"text": "Docker", "status": "unknown"}, {"text": "Rust", "status": "unknown"}],
    )

    updated = known_skills_crud.promote_unknown_gap_items(db_session, session.id, ["docker"])

    assert [item.text for item in updated] == ["Docker"]
    assert updated[0].status == "can_add"


@pytest.mark.db
def test_promote_gap_items_rewords_and_promotes(db_session):
    session = _make_session(db_session)
    created = gap_items_crud.bulk_create_gap_items(
        db_session, session.id, [{"text": "K8s", "status": "unknown"}]
    )

    updated = known_skills_crud.promote_gap_items(
        db_session, session.id, [{"id": created[0].id, "text": "  Kubernetes "}]
    )

    assert [item.text for item in updated] == ["Kubernetes"]
    assert updated[0].status == "can_add"


@pytest.mark.db
def test_promote_gap_items_keeps_text_when_wording_is_blank(db_session):
    session = _make_session(db_session)
    created = gap_items_crud.bulk_create_gap_items(
        db_session, session.id, [{"text": "Docker", "status": "unknown"}]
    )

    updated = known_skills_crud.promote_gap_items(db_session, session.id, [{"id": created[0].id, "text": "   "}])

    assert updated[0].text == "Docker"
    assert updated[0].status == "can_add"


@pytest.mark.db
def test_promote_gap_items_ignores_items_of_other_sessions(db_session):
    first = _make_session(db_session)
    second = _make_session(db_session)
    created = gap_items_crud.bulk_create_gap_items(
        db_session, second.id, [{"text": "Docker", "status": "unknown"}]
    )

    updated = known_skills_crud.promote_gap_items(
        db_session, first.id, [{"id": created[0].id, "text": "Docker"}]
    )

    assert updated == []
    assert gap_items_crud.list_gap_items_for_session(db_session, second.id)[0].status == "unknown"


@pytest.mark.db
def test_promote_gap_items_skips_exact_items(db_session):
    session = _make_session(db_session)
    created = gap_items_crud.bulk_create_gap_items(
        db_session, session.id, [{"text": "Python", "status": "exact"}]
    )

    updated = known_skills_crud.promote_gap_items(
        db_session, session.id, [{"id": created[0].id, "text": "Python 3"}]
    )

    assert updated == []
    assert gap_items_crud.list_gap_items_for_session(db_session, session.id)[0].text == "Python"