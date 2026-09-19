import pytest

from core.db.crud import automation_runs as automation_runs_crud


@pytest.mark.db
def test_create_automation_run_defaults(db_session):
    run = automation_runs_crud.create_automation_run(db_session)

    assert run.id is not None
    assert run.status == "pending"
    assert run.found_count == 0
    assert run.max_results_override is None
    assert run.max_queries_override is None


@pytest.mark.db
def test_create_automation_run_with_overrides(db_session):
    run = automation_runs_crud.create_automation_run(
        db_session,
        queries_planned=["query one", "query two"],
        max_results_override=5,
        max_queries_override=1,
    )

    assert run.queries_planned == ["query one", "query two"]
    assert run.max_results_override == 5
    assert run.max_queries_override == 1


@pytest.mark.db
def test_mark_run_started_and_finished(db_session):
    run = automation_runs_crud.create_automation_run(db_session)

    started = automation_runs_crud.mark_run_started(db_session, run.id)
    assert started.status == "running"
    assert started.started_at is not None

    finished = automation_runs_crud.mark_run_finished(db_session, run.id, status="done")
    assert finished.status == "done"
    assert finished.finished_at is not None


@pytest.mark.db
def test_mark_run_failed_records_error(db_session):
    run = automation_runs_crud.create_automation_run(db_session)

    failed = automation_runs_crud.mark_run_failed(db_session, run.id, error="Sample failure")

    assert failed.status == "failed"
    assert failed.error == "Sample failure"
    assert failed.finished_at is not None


@pytest.mark.db
def test_increment_run_counters(db_session):
    run = automation_runs_crud.create_automation_run(db_session)

    automation_runs_crud.increment_run_counters(db_session, run.id, found_count=5, scraped_count=2)
    updated = automation_runs_crud.increment_run_counters(db_session, run.id, found_count=3)

    assert updated.found_count == 8
    assert updated.scraped_count == 2


@pytest.mark.db
def test_increment_run_counters_rejects_unknown_field(db_session):
    run = automation_runs_crud.create_automation_run(db_session)

    with pytest.raises(ValueError):
        automation_runs_crud.increment_run_counters(db_session, run.id, not_a_real_field=1)


@pytest.mark.db
def test_list_automation_runs_order(db_session):
    automation_runs_crud.create_automation_run(db_session, queries_planned=["first"])
    automation_runs_crud.create_automation_run(db_session, queries_planned=["second"])

    runs = automation_runs_crud.list_automation_runs(db_session)

    assert len(runs) == 2
    assert runs[0].queries_planned == ["second"]