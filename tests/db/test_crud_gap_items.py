import pytest

from core.db.crud import gap_items as gap_items_crud
from core.db.crud import jobs as jobs_crud
from core.db.crud import resumes as resumes_crud
from core.db.crud import tailoring_sessions as tailoring_sessions_crud


def _make_session(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    resume = resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume text")
    return tailoring_sessions_crud.create_tailoring_session(
        db_session, job_posting_id=job.id, resume_version_id=resume.id, working_content={}
    )


@pytest.mark.db
def test_bulk_create_and_list_gap_items(db_session):
    tailoring_session = _make_session(db_session)

    created = gap_items_crud.bulk_create_gap_items(
        db_session,
        tailoring_session.id,
        [
            {"text": "Python", "status": "match", "category": "skill"},
            {"text": "Rust", "status": "miss", "category": "skill"},
        ],
    )

    assert len(created) == 2
    listed = gap_items_crud.list_gap_items_for_session(db_session, tailoring_session.id)
    assert len(listed) == 2


@pytest.mark.db
def test_bulk_create_gap_items_defaults_included_by_status(db_session):
    tailoring_session = _make_session(db_session)

    created = gap_items_crud.bulk_create_gap_items(
        db_session,
        tailoring_session.id,
        [
            {"text": "Python", "status": "match", "suggested_field_paths": ["skills"]},
            {"text": "Rust", "status": "miss"},
            {"text": "COBOL", "status": "over", "recommend_keep": True},
        ],
    )

    included_map = {item.text: item.included for item in created}
    assert included_map["Python"] is True
    assert included_map["Rust"] is False
    assert included_map["COBOL"] is False


@pytest.mark.db
def test_toggle_gap_item_location_adds_and_removes(db_session):
    tailoring_session = _make_session(db_session)
    created = gap_items_crud.bulk_create_gap_items(
        db_session, tailoring_session.id, [{"text": "Python", "status": "can_add"}]
    )

    added = gap_items_crud.toggle_gap_item_location(db_session, created[0].id, "summary")
    assert added.assigned_field_paths == ["summary"]
    assert added.included is True

    added_two = gap_items_crud.toggle_gap_item_location(db_session, created[0].id, "skills")
    assert set(added_two.assigned_field_paths) == {"summary", "skills"}

    removed = gap_items_crud.toggle_gap_item_location(db_session, created[0].id, "summary")
    assert removed.assigned_field_paths == ["skills"]
    assert removed.included is True

    removed_last = gap_items_crud.toggle_gap_item_location(db_session, created[0].id, "skills")
    assert removed_last.assigned_field_paths == []
    assert removed_last.included is False


@pytest.mark.db
def test_clear_gap_items_for_session(db_session):
    tailoring_session = _make_session(db_session)
    gap_items_crud.bulk_create_gap_items(
        db_session, tailoring_session.id, [{"text": "Python", "status": "match"}]
    )

    gap_items_crud.clear_gap_items_for_session(db_session, tailoring_session.id)

    assert gap_items_crud.list_gap_items_for_session(db_session, tailoring_session.id) == []


@pytest.mark.db
def test_set_and_persist_block_comment(db_session):
    tailoring_session = _make_session(db_session)

    gap_items_crud.set_block_comment(db_session, tailoring_session.id, "summary", "use docker constantly")

    refreshed = tailoring_sessions_crud.get_tailoring_session(db_session, tailoring_session.id)
    assert refreshed.block_comments == {"summary": "use docker constantly"}


@pytest.mark.db
def test_set_block_comment_empty_removes_it(db_session):
    tailoring_session = _make_session(db_session)
    gap_items_crud.set_block_comment(db_session, tailoring_session.id, "summary", "note")

    gap_items_crud.set_block_comment(db_session, tailoring_session.id, "summary", "")

    refreshed = tailoring_sessions_crud.get_tailoring_session(db_session, tailoring_session.id)
    assert refreshed.block_comments == {}


@pytest.mark.db
def test_mark_gap_analysis_ready(db_session):
    tailoring_session = _make_session(db_session)

    gap_items_crud.mark_gap_analysis_ready(db_session, tailoring_session.id)

    refreshed = tailoring_sessions_crud.get_tailoring_session(db_session, tailoring_session.id)
    assert refreshed.gap_analysis_ready is True