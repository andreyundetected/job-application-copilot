import pytest

from core.db.crud import evaluations as evaluations_crud
from core.db.crud import jobs as jobs_crud
from core.db.crud import resumes as resumes_crud


@pytest.mark.db
def test_create_evaluation(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    resume = resumes_crud.create_resume_version(
        db_session, source_type="resume", raw_text="resume text"
    )

    evaluation = evaluations_crud.create_evaluation(
        db_session,
        job_posting_id=job.id,
        resume_version_id=resume.id,
        verdict=True,
        blocker_bullets={"passed": ["years_ok"]},
        fit_score=7,
    )

    assert evaluation.id is not None
    assert evaluation.verdict is True


@pytest.mark.db
def test_list_evaluations_for_job(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    resume = resumes_crud.create_resume_version(
        db_session, source_type="resume", raw_text="resume text"
    )
    evaluations_crud.create_evaluation(
        db_session, job_posting_id=job.id, resume_version_id=resume.id, verdict=False
    )

    results = evaluations_crud.list_evaluations_for_job(db_session, job.id)

    assert len(results) == 1
    assert results[0].verdict is False


@pytest.mark.db
def test_list_passed_evaluations(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    resume = resumes_crud.create_resume_version(
        db_session, source_type="resume", raw_text="resume text"
    )
    evaluations_crud.create_evaluation(
        db_session, job_posting_id=job.id, resume_version_id=resume.id, verdict=True
    )
    evaluations_crud.create_evaluation(
        db_session, job_posting_id=job.id, resume_version_id=resume.id, verdict=False
    )

    passed = evaluations_crud.list_passed_evaluations(db_session)

    assert len(passed) == 1
    assert passed[0].verdict is True