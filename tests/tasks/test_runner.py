import time

import pytest

from core.db.crud import task_statuses as task_statuses_crud
from core.tasks.runner import run_tracked_task


def _sample_task(value):
    time.sleep(0.05)
    return {"echo": value}


def _failing_task():
    raise ValueError("Sample failure")


@pytest.mark.tasks
def test_run_tracked_task_completes_successfully(db_session, monkeypatch):
    monkeypatch.setattr("core.tasks.runner.SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    task_id = run_tracked_task("sample", _sample_task, "hello")

    deadline = time.time() + 5
    while time.time() < deadline:
        task = task_statuses_crud.get_task_status(db_session, task_id)
        if task.status == "done":
            break
        time.sleep(0.02)

    task = task_statuses_crud.get_task_status(db_session, task_id)
    assert task.status == "done"
    assert task.result == {"echo": "hello"}


@pytest.mark.tasks
def test_run_tracked_task_records_failure(db_session, monkeypatch):
    monkeypatch.setattr("core.tasks.runner.SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    task_id = run_tracked_task("sample", _failing_task)

    deadline = time.time() + 5
    while time.time() < deadline:
        task = task_statuses_crud.get_task_status(db_session, task_id)
        if task.status == "failed":
            break
        time.sleep(0.02)

    task = task_statuses_crud.get_task_status(db_session, task_id)
    assert task.status == "failed"
    assert "Sample failure" in task.error