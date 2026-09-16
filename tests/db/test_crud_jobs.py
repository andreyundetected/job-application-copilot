import pytest

from core.db.crud import jobs as jobs_crud


@pytest.mark.db
def test_create_and_get_job_posting(db_session):
    job = jobs_crud.create_job_posting(
        db_session, raw_text="job text", company="Example Corp", title="Engineer"
    )

    fetched = jobs_crud.get_job_posting(db_session, job.id)

    assert fetched is not None
    assert fetched.company == "Example Corp"


@pytest.mark.db
def test_list_job_postings_order(db_session):
    jobs_crud.create_job_posting(db_session, raw_text="first")
    jobs_crud.create_job_posting(db_session, raw_text="second")

    jobs = jobs_crud.list_job_postings(db_session)

    assert len(jobs) == 2
    assert jobs[0].raw_text == "second"


@pytest.mark.db
def test_delete_job_posting(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="to delete")

    deleted = jobs_crud.delete_job_posting(db_session, job.id)
    missing = jobs_crud.get_job_posting(db_session, job.id)

    assert deleted is True
    assert missing is None


@pytest.mark.db
def test_delete_job_posting_not_found(db_session):
    deleted = jobs_crud.delete_job_posting(db_session, 999)
    assert deleted is False