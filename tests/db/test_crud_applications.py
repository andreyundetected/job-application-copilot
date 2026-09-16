import pytest

from core.db.crud import applications as applications_crud
from core.db.crud import jobs as jobs_crud


@pytest.mark.db
def test_create_application_without_resume(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")

    application = applications_crud.create_application(
        db_session, job_posting_id=job.id
    )

    assert application.id is not None
    assert application.tailored_resume_id is None
    assert application.status == "draft"


@pytest.mark.db
def test_update_application_status_marks_applied_at(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    application = applications_crud.create_application(
        db_session, job_posting_id=job.id
    )

    updated = applications_crud.update_application_status(
        db_session, application.id, status="applied", mark_applied_now=True
    )

    assert updated.status == "applied"
    assert updated.applied_at is not None


@pytest.mark.db
def test_list_applications_filtered_by_status(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    applications_crud.create_application(db_session, job_posting_id=job.id, status="draft")
    applications_crud.create_application(
        db_session, job_posting_id=job.id, status="applied"
    )

    applied_only = applications_crud.list_applications(db_session, status="applied")

    assert len(applied_only) == 1
    assert applied_only[0].status == "applied"


@pytest.mark.db
def test_update_application_notes(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    application = applications_crud.create_application(
        db_session, job_posting_id=job.id
    )

    updated = applications_crud.update_application_notes(
        db_session, application.id, "Sample note."
    )

    assert updated.notes == "Sample note."