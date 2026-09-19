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


@pytest.mark.db
def test_archive_job_posting(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")

    archived = jobs_crud.archive_job_posting(db_session, job.id)

    assert archived.archived is True


@pytest.mark.db
def test_list_job_postings_excludes_archived(db_session):
    active = jobs_crud.create_job_posting(db_session, raw_text="active job")
    archived_job = jobs_crud.create_job_posting(db_session, raw_text="archived job")
    jobs_crud.archive_job_posting(db_session, archived_job.id)

    results = jobs_crud.list_job_postings(db_session, include_archived=False)

    assert len(results) == 1
    assert results[0].id == active.id


@pytest.mark.db
def test_unarchive_job_posting(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    jobs_crud.archive_job_posting(db_session, job.id)

    restored = jobs_crud.unarchive_job_posting(db_session, job.id)

    assert restored.archived is False


@pytest.mark.db
def test_create_job_posting_defaults_source_to_manual(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")

    assert job.source == "manual"
    assert job.pipeline_stage is None


@pytest.mark.db
def test_create_job_posting_with_automation_source(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text", source="automation")

    assert job.source == "automation"


@pytest.mark.db
def test_update_job_pipeline_stage(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text", source="automation")

    updated = jobs_crud.update_job_pipeline_stage(db_session, job.id, "evaluated")

    assert updated.pipeline_stage == "evaluated"


@pytest.mark.db
def test_update_job_pipeline_stage_not_found(db_session):
    result = jobs_crud.update_job_pipeline_stage(db_session, 999, "evaluated")

    assert result is None