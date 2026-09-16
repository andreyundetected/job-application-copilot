import pytest

from core.db.crud import evaluations as evaluations_crud
from core.db.crud import jobs as jobs_crud
from core.db.crud import resumes as resumes_crud
from core.db.crud import tailored_resumes as tailored_crud


def _make_evaluation(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    resume = resumes_crud.create_resume_version(
        db_session, source_type="resume", raw_text="resume text"
    )
    return evaluations_crud.create_evaluation(
        db_session, job_posting_id=job.id, resume_version_id=resume.id, verdict=True
    )


@pytest.mark.db
def test_create_tailored_resume(db_session):
    evaluation = _make_evaluation(db_session)
    content = [{"type": "summary", "text": "Sample summary."}]

    tailored = tailored_crud.create_tailored_resume(
        db_session, evaluation_id=evaluation.id, content=content
    )

    assert tailored.id is not None
    assert tailored.content[0]["type"] == "summary"


@pytest.mark.db
def test_update_tailored_resume_docx_path(db_session):
    evaluation = _make_evaluation(db_session)
    tailored = tailored_crud.create_tailored_resume(
        db_session, evaluation_id=evaluation.id, content=[]
    )

    updated = tailored_crud.update_tailored_resume_docx_path(
        db_session, tailored.id, "output/sample.docx"
    )

    assert updated.docx_path == "output/sample.docx"


@pytest.mark.db
def test_list_tailored_resumes_for_evaluation(db_session):
    evaluation = _make_evaluation(db_session)
    tailored_crud.create_tailored_resume(
        db_session, evaluation_id=evaluation.id, content=[]
    )
    tailored_crud.create_tailored_resume(
        db_session, evaluation_id=evaluation.id, content=[]
    )

    results = tailored_crud.list_tailored_resumes_for_evaluation(
        db_session, evaluation.id
    )

    assert len(results) == 2