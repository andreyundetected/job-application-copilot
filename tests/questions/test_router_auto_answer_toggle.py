import pytest

from core.db.crud import app_settings as app_settings_crud
from core.db.crud import applications as applications_crud
from core.db.crud import jobs as jobs_crud
from ui.questions_page.router import _run_split_only


@pytest.mark.questions
def test_run_split_only_skips_generation_when_auto_answer_disabled(monkeypatch, db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    application = applications_crud.create_application(db_session, job_posting_id=job.id)
    app_settings_crud.upsert_app_settings(db_session, auto_answer_questions_enabled=False)

    monkeypatch.setattr("ui.questions_page.router.SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    class _FakeProvider:
        def call(self, system_prompt, user_prompt):
            return '<question type="document">Tell us about yourself.</question>'

    monkeypatch.setattr("ui.questions_page.router.get_llm_provider", lambda: _FakeProvider())

    launched_tasks = []
    monkeypatch.setattr(
        "ui.questions_page.router.run_tracked_task",
        lambda *args, **kwargs: launched_tasks.append(args) or 999,
    )

    result = _run_split_only(application.id, "raw pasted form text")

    assert len(result["questions"]) == 1
    assert result["questions"][0]["answer_text"] is None
    assert result["questions"][0]["pending_task_id"] is None
    assert launched_tasks == []


@pytest.mark.questions
def test_run_split_only_launches_generation_when_auto_answer_enabled_default(monkeypatch, db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")
    application = applications_crud.create_application(db_session, job_posting_id=job.id)
    # No app_settings row at all - should default to enabled=True

    monkeypatch.setattr("ui.questions_page.router.SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    class _FakeProvider:
        def call(self, system_prompt, user_prompt):
            return '<question type="document">Tell us about yourself.</question>'

    monkeypatch.setattr("ui.questions_page.router.get_llm_provider", lambda: _FakeProvider())

    launched_tasks = []
    monkeypatch.setattr(
        "ui.questions_page.router.run_tracked_task",
        lambda *args, **kwargs: launched_tasks.append(args[0]) or 999,
    )

    result = _run_split_only(application.id, "raw pasted form text")

    assert len(launched_tasks) >= 1
    assert result["questions"][0]["pending_task_id"] == 999