import pytest

from core.db.crud import evaluations as evaluations_crud
from core.db.crud import jobs as jobs_crud
from core.db.crud import resumes as resumes_crud
from core.db.crud import tailoring_changes as tailoring_changes_crud


def _make_evaluation(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    resume = resumes_crud.create_resume_version(
        db_session, source_type="resume", raw_text="resume text"
    )
    return evaluations_crud.create_evaluation(
        db_session, job_posting_id=job.id, resume_version_id=resume.id, verdict=True
    )


@pytest.mark.db
def test_bulk_create_tailoring_changes(db_session):
    evaluation = _make_evaluation(db_session)

    changes = tailoring_changes_crud.bulk_create_tailoring_changes(
        db_session,
        evaluation.id,
        [
            {"level": "soft", "change_type": "title", "proposed_text": "New Title"},
            {"level": "soft", "change_type": "skills", "proposed_text": "Python, SQL"},
        ],
    )

    assert len(changes) == 2
    assert all(change.status == "pending" for change in changes)


@pytest.mark.db
def test_list_tailoring_changes_filtered_by_level(db_session):
    evaluation = _make_evaluation(db_session)
    tailoring_changes_crud.bulk_create_tailoring_changes(
        db_session,
        evaluation.id,
        [
            {"level": "soft", "change_type": "title", "proposed_text": "New Title"},
            {"level": "medium", "change_type": "summary", "proposed_text": "New Summary"},
        ],
    )

    soft_only = tailoring_changes_crud.list_tailoring_changes_for_evaluation(
        db_session, evaluation.id, level="soft"
    )

    assert len(soft_only) == 1
    assert soft_only[0].change_type == "title"


@pytest.mark.db
def test_resolve_tailoring_change_approve(db_session):
    evaluation = _make_evaluation(db_session)
    changes = tailoring_changes_crud.bulk_create_tailoring_changes(
        db_session,
        evaluation.id,
        [{"level": "soft", "change_type": "title", "proposed_text": "New Title"}],
    )

    resolved = tailoring_changes_crud.resolve_tailoring_change(
        db_session, changes[0].id, status="approved"
    )

    assert resolved.status == "approved"
    assert resolved.final_text == "New Title"


@pytest.mark.db
def test_resolve_tailoring_change_edited_uses_final_text(db_session):
    evaluation = _make_evaluation(db_session)
    changes = tailoring_changes_crud.bulk_create_tailoring_changes(
        db_session,
        evaluation.id,
        [{"level": "medium", "change_type": "summary", "proposed_text": "AI generated summary"}],
    )

    resolved = tailoring_changes_crud.resolve_tailoring_change(
        db_session, changes[0].id, status="edited", final_text="User edited summary"
    )

    assert resolved.status == "edited"
    assert resolved.final_text == "User edited summary"


@pytest.mark.db
def test_resolve_tailoring_change_reject(db_session):
    evaluation = _make_evaluation(db_session)
    changes = tailoring_changes_crud.bulk_create_tailoring_changes(
        db_session,
        evaluation.id,
        [{"level": "soft", "change_type": "skills", "proposed_text": "Python"}],
    )

    resolved = tailoring_changes_crud.resolve_tailoring_change(
        db_session, changes[0].id, status="rejected"
    )

    assert resolved.status == "rejected"