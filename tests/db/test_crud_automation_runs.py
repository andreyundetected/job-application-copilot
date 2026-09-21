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
def test_append_run_warning_sets_error_when_empty(db_session):
    run = automation_runs_crud.create_automation_run(db_session)

    updated = automation_runs_crud.append_run_warning(db_session, run.id, "Sample warning")

    assert updated.error == "Sample warning"
    assert updated.status == "pending"


@pytest.mark.db
def test_append_run_warning_accumulates_messages(db_session):
    run = automation_runs_crud.create_automation_run(db_session)

    automation_runs_crud.append_run_warning(db_session, run.id, "First warning")
    updated = automation_runs_crud.append_run_warning(db_session, run.id, "Second warning")

    assert updated.error == "First warning\nSecond warning"


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


@pytest.mark.db
def test_increment_run_counters_no_lost_update_under_concurrency(tmp_path):
    """Regression test for a real bug: with the old Python-side read-modify-write,
    concurrent increments from separate sessions/threads could silently lose
    updates. This spins up real OS threads against a file-based sqlite database
    (each thread gets its own pooled connection - never a single raw connection
    object shared across threads, which is what causes CPython's sqlite3 module
    to crash rather than just misbehave) and verifies every increment survives."""
    import threading

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.db.models import Base

    db_path = tmp_path / "concurrency_test.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 30}
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    setup_session = session_factory()
    run = automation_runs_crud.create_automation_run(setup_session)
    run_id = run.id
    setup_session.close()

    increments_per_thread = 20
    thread_count = 8

    def worker():
        session = session_factory()
        try:
            for _ in range(increments_per_thread):
                automation_runs_crud.increment_run_counters(session, run_id, scraped_count=1)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(thread_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    verify_session = session_factory()
    final = automation_runs_crud.get_automation_run(verify_session, run_id)
    verify_session.close()

    engine.dispose()

    assert final.scraped_count == increments_per_thread * thread_count