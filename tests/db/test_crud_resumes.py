import pytest

from core.db.crud import resumes as resumes_crud


@pytest.mark.db
def test_create_resume_version(db_session):
    resume = resumes_crud.create_resume_version(
        db_session, source_type="resume", raw_text="resume text", label="base"
    )

    assert resume.id is not None
    assert resume.label == "base"


@pytest.mark.db
def test_list_resume_versions_filtered(db_session):
    resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="r1")
    resumes_crud.create_resume_version(db_session, source_type="linkedin", raw_text="l1")

    only_resumes = resumes_crud.list_resume_versions(db_session, source_type="resume")

    assert len(only_resumes) == 1
    assert only_resumes[0].source_type == "resume"


@pytest.mark.db
def test_get_latest_resume_version(db_session):
    resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="old")
    newest = resumes_crud.create_resume_version(
        db_session, source_type="resume", raw_text="new"
    )

    latest = resumes_crud.get_latest_resume_version(db_session, "resume")

    assert latest.id == newest.id