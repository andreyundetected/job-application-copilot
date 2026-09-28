import pytest

from core.db.crud import applications as applications_crud
from core.db.crud import jobs as jobs_crud


@pytest.mark.db
def test_set_job_applied_moves_draft_to_applied(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    applications_crud.create_application(db_session, job_posting_id=job.id)

    application = applications_crud.set_job_applied(db_session, job.id, True)

    assert application.status == "applied"
    assert application.applied_at is not None
    assert applications_crud.is_job_applied(db_session, job.id) is True


@pytest.mark.db
def test_set_job_applied_keeps_later_status(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    applications_crud.create_application(db_session, job_posting_id=job.id, status="interviewing")

    application = applications_crud.set_job_applied(db_session, job.id, True)

    assert application.status == "interviewing"


@pytest.mark.db
def test_set_job_applied_false_returns_all_applied_statuses_to_draft(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    first = applications_crud.create_application(db_session, job_posting_id=job.id, status="offer")
    second = applications_crud.create_application(db_session, job_posting_id=job.id, status="applied")

    applications_crud.set_job_applied(db_session, job.id, False)

    db_session.refresh(first)
    db_session.refresh(second)
    assert first.status == "draft"
    assert second.status == "draft"
    assert first.applied_at is None
    assert applications_crud.is_job_applied(db_session, job.id) is False


@pytest.mark.db
def test_set_job_applied_creates_application_when_missing(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")

    application = applications_crud.set_job_applied(db_session, job.id, True)

    assert application.job_posting_id == job.id
    assert application.status == "applied"


@pytest.mark.db
def test_is_job_applied_false_for_rejected_moved_to_draft_via_tracker(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    application = applications_crud.create_application(db_session, job_posting_id=job.id, status="rejected")
    assert applications_crud.is_job_applied(db_session, job.id) is True

    applications_crud.move_application_status(db_session, application.id, "draft")

    assert applications_crud.is_job_applied(db_session, job.id) is False