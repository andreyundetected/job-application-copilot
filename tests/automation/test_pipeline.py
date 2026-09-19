from concurrent.futures import Future

import pytest

from core.automation import pipeline, stages
from core.db.crud import api_usage_log as api_usage_log_crud
from core.db.crud import automation_runs as automation_runs_crud
from core.db.crud import automation_settings as automation_settings_crud
from core.db.crud import jobs as jobs_crud
from core.db.crud import resumes as resumes_crud
from core.db.crud import search_results as search_results_crud
from core.db.crud import tailoring_changes as tailoring_changes_crud
from core.db.crud import tailoring_permissions as tailoring_permissions_crud
from core.db.crud import tailoring_sessions as tailoring_sessions_crud


_SAMPLE_EVAL_RESULT = {
    "company": "Acme",
    "role": "Engineer",
    "location": "Remote",
    "work_mode": "remote",
    "salary": {},
    "matched_factors": [],
    "cons": [],
    "pros": [],
    "summary": "Summary",
    "raw_response": "",
}


class _FakeLLMProvider:
    def __init__(self):
        self.last_usage = {
            "model": "test-model",
            "input_tokens": 10,
            "output_tokens": 5,
            "reasoning_tokens": None,
            "total_tokens": 15,
        }

    def call(self, system_prompt, user_prompt):
        return ""


def _eval_result(score: int, verdict: bool = True) -> dict:
    return {**_SAMPLE_EVAL_RESULT, "score": score, "verdict": verdict}


def _make_run_and_search_result(db_session, url="https://boards.greenhouse.io/a/jobs/1"):
    run = automation_runs_crud.create_automation_run(db_session)
    created = search_results_crud.bulk_create_search_results(
        db_session, run.id, [{"query_text": "q", "url": url, "url_normalized": url}]
    )
    return run, created[0]


@pytest.mark.automation
def test_decide_stage_archives_low_score():
    assert (
        pipeline._decide_stage(2, min_score_to_proceed=6, max_score_to_archive=3) == stages.ARCHIVED_AUTO
    )


@pytest.mark.automation
def test_decide_stage_passes_high_score():
    assert pipeline._decide_stage(8, min_score_to_proceed=6, max_score_to_archive=3) == stages.PASSED


@pytest.mark.automation
def test_decide_stage_needs_review_in_gray_zone():
    assert (
        pipeline._decide_stage(4, min_score_to_proceed=6, max_score_to_archive=3) == stages.NEEDS_REVIEW
    )


@pytest.mark.automation
def test_decide_stage_none_score_needs_review():
    assert (
        pipeline._decide_stage(None, min_score_to_proceed=6, max_score_to_archive=3) == stages.NEEDS_REVIEW
    )


@pytest.mark.automation
def test_decide_stage_boundary_values_are_inclusive():
    assert pipeline._decide_stage(3, min_score_to_proceed=6, max_score_to_archive=3) == stages.ARCHIVED_AUTO
    assert pipeline._decide_stage(6, min_score_to_proceed=6, max_score_to_archive=3) == stages.PASSED


@pytest.mark.automation
def test_run_single_query_creates_search_results_and_logs_usage(monkeypatch, db_session):
    run = automation_runs_crud.create_automation_run(db_session)
    settings = automation_settings_crud.upsert_automation_settings(db_session)

    fake_response = {
        "results": [
            {"title": "Sample Job", "url": "https://boards.greenhouse.io/a/jobs/1", "snippet": "Snippet"},
        ],
        "requested_num": 30,
        "returned_count": 1,
        "raw_response": {"organic_results": [{}]},
    }

    class _FakeProvider:
        def __init__(self):
            pass

        def search(self, query, num=None, date=None):
            return fake_response

    monkeypatch.setattr(pipeline, "SerpentSearchProvider", _FakeProvider)

    created = pipeline._run_single_query(db_session, run, "sample query", settings)

    assert len(created) == 1
    assert created[0]["url"] == "https://boards.greenhouse.io/a/jobs/1"

    stored = search_results_crud.list_search_results_for_run(db_session, run.id)
    assert len(stored) == 1
    assert stored[0].source_platform == "greenhouse"

    usage_logs = api_usage_log_crud.list_usage_logs_for_run(db_session, run.id)
    assert len(usage_logs) == 1
    assert usage_logs[0].provider == "serpent"
    assert usage_logs[0].returned_count == 1

    refreshed_run = automation_runs_crud.get_automation_run(db_session, run.id)
    assert refreshed_run.found_count == 1


@pytest.mark.automation
def test_run_single_query_handles_search_error_gracefully(monkeypatch, db_session):
    run = automation_runs_crud.create_automation_run(db_session)
    settings = automation_settings_crud.upsert_automation_settings(db_session)

    class _FakeProvider:
        def __init__(self):
            pass

        def search(self, query, num=None, date=None):
            raise pipeline.SerpentSearchError("boom")

    monkeypatch.setattr(pipeline, "SerpentSearchProvider", _FakeProvider)

    created = pipeline._run_single_query(db_session, run, "sample query", settings)

    assert created == []

    refreshed_run = automation_runs_crud.get_automation_run(db_session, run.id)
    assert "sample query" in refreshed_run.error
    assert "boom" in refreshed_run.error


@pytest.mark.automation
def test_process_search_result_records_warning_on_unexpected_error(monkeypatch, db_session):
    resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume text", is_active=True)
    run, search_result = _make_run_and_search_result(db_session)

    def _boom(url):
        raise RuntimeError("extraction exploded")

    monkeypatch.setattr(pipeline, "extract_job_text", _boom)

    promoted = pipeline._process_search_result(
        db_session, run.id, search_result.id, "resume", "linkedin", [], [], None
    )

    assert promoted is False
    refreshed_run = automation_runs_crud.get_automation_run(db_session, run.id)
    assert "extraction exploded" in refreshed_run.error


@pytest.mark.automation
def test_process_search_result_creates_job_and_passes(monkeypatch, db_session):
    resumes_crud.create_resume_version(
        db_session, source_type="resume", raw_text="resume text", content_html="<p>Resume</p>", is_active=True
    )
    automation_settings_crud.upsert_automation_settings(
        db_session, min_score_to_proceed=6, max_score_to_archive=3
    )
    run, search_result = _make_run_and_search_result(db_session)

    monkeypatch.setattr(pipeline, "extract_job_text", lambda url: "Sample job text")
    monkeypatch.setattr(pipeline, "get_llm_provider", lambda: _FakeLLMProvider())
    monkeypatch.setattr(pipeline, "evaluate_job_posting", lambda *a, **k: _eval_result(8))

    promoted = pipeline._process_search_result(
        db_session, run.id, search_result.id, "resume text", "linkedin text", [], [], None
    )

    assert promoted is True

    refreshed = search_results_crud.get_search_result(db_session, search_result.id)
    assert refreshed.promoted_job_posting_id is not None

    job = jobs_crud.get_job_posting(db_session, refreshed.promoted_job_posting_id)
    assert job.pipeline_stage == stages.PASSED
    assert job.source == "automation"

    refreshed_run = automation_runs_crud.get_automation_run(db_session, run.id)
    assert refreshed_run.scraped_count == 1
    assert refreshed_run.evaluated_count == 1
    assert refreshed_run.passed_count == 1

    usage_logs = api_usage_log_crud.list_usage_logs_for_run(db_session, run.id)
    assert any(log.operation == "evaluation" for log in usage_logs)


@pytest.mark.automation
def test_process_search_result_archives_low_score_when_auto_archive_enabled(monkeypatch, db_session):
    resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume text", is_active=True)
    automation_settings_crud.upsert_automation_settings(
        db_session, min_score_to_proceed=6, max_score_to_archive=3, auto_archive_enabled=True
    )
    run, search_result = _make_run_and_search_result(db_session)

    monkeypatch.setattr(pipeline, "extract_job_text", lambda url: "Sample job text")
    monkeypatch.setattr(pipeline, "get_llm_provider", lambda: _FakeLLMProvider())
    monkeypatch.setattr(pipeline, "evaluate_job_posting", lambda *a, **k: _eval_result(1, verdict=False))

    pipeline._process_search_result(db_session, run.id, search_result.id, "resume", "linkedin", [], [], None)

    refreshed = search_results_crud.get_search_result(db_session, search_result.id)
    job = jobs_crud.get_job_posting(db_session, refreshed.promoted_job_posting_id)

    assert job.pipeline_stage == stages.ARCHIVED_AUTO
    assert job.archived is True

    refreshed_run = automation_runs_crud.get_automation_run(db_session, run.id)
    assert refreshed_run.archived_count == 1


@pytest.mark.automation
def test_process_search_result_needs_review_in_gray_zone(monkeypatch, db_session):
    resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume text", is_active=True)
    automation_settings_crud.upsert_automation_settings(
        db_session, min_score_to_proceed=6, max_score_to_archive=3
    )
    run, search_result = _make_run_and_search_result(db_session)

    monkeypatch.setattr(pipeline, "extract_job_text", lambda url: "Sample job text")
    monkeypatch.setattr(pipeline, "get_llm_provider", lambda: _FakeLLMProvider())
    monkeypatch.setattr(pipeline, "evaluate_job_posting", lambda *a, **k: _eval_result(4))

    pipeline._process_search_result(db_session, run.id, search_result.id, "resume", "linkedin", [], [], None)

    refreshed = search_results_crud.get_search_result(db_session, search_result.id)
    job = jobs_crud.get_job_posting(db_session, refreshed.promoted_job_posting_id)

    assert job.pipeline_stage == stages.NEEDS_REVIEW
    assert job.archived is False


@pytest.mark.automation
def test_process_search_result_returns_false_when_scrape_fails(monkeypatch, db_session):
    resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume text", is_active=True)
    run, search_result = _make_run_and_search_result(db_session)

    monkeypatch.setattr(pipeline, "extract_job_text", lambda url: None)

    promoted = pipeline._process_search_result(
        db_session, run.id, search_result.id, "resume", "linkedin", [], [], None
    )

    assert promoted is False
    refreshed = search_results_crud.get_search_result(db_session, search_result.id)
    assert refreshed.promoted_job_posting_id is None


@pytest.mark.automation
def test_process_search_result_returns_false_when_no_active_resume(db_session):
    run, search_result = _make_run_and_search_result(db_session)

    promoted = pipeline._process_search_result(
        db_session, run.id, search_result.id, "resume", "linkedin", [], [], None
    )

    assert promoted is False


@pytest.mark.automation
def test_process_search_result_auto_applies_permitted_soft_changes(monkeypatch, db_session):
    resumes_crud.create_resume_version(
        db_session,
        source_type="resume",
        raw_text="resume text",
        content_html="<p>Old Skills Line</p>",
        is_active=True,
    )
    automation_settings_crud.upsert_automation_settings(
        db_session, min_score_to_proceed=6, max_score_to_archive=3, auto_tailor_soft_enabled=True
    )
    tailoring_permissions_crud.set_tailoring_permission(
        db_session, level="soft", change_type="skills", auto_apply=True
    )
    run, search_result = _make_run_and_search_result(db_session)

    monkeypatch.setattr(pipeline, "extract_job_text", lambda url: "Sample job text")
    monkeypatch.setattr(pipeline, "get_llm_provider", lambda: _FakeLLMProvider())
    monkeypatch.setattr(pipeline, "evaluate_job_posting", lambda *a, **k: _eval_result(9))
    monkeypatch.setattr(
        pipeline,
        "propose_soft_fragment_changes",
        lambda *a, **k: [
            {
                "level": "soft",
                "change_type": "skills",
                "field_path": None,
                "target_ref": None,
                "original_text": "Old Skills Line",
                "proposed_text": "New Skills Line",
                "proposed_content": None,
            }
        ],
    )

    pipeline._process_search_result(db_session, run.id, search_result.id, "resume", "linkedin", [], [], None)

    refreshed = search_results_crud.get_search_result(db_session, search_result.id)
    job = jobs_crud.get_job_posting(db_session, refreshed.promoted_job_posting_id)
    assert job.pipeline_stage == stages.TAILORED

    tailoring_session = tailoring_sessions_crud.get_tailoring_session_for_job(db_session, job.id)
    assert "New Skills Line" in tailoring_session.working_html

    changes = tailoring_changes_crud.list_tailoring_changes_for_session(db_session, tailoring_session.id)
    assert len(changes) == 1
    assert changes[0].status == "approved"


@pytest.mark.automation
def test_process_search_result_leaves_non_permitted_soft_changes_pending(monkeypatch, db_session):
    resumes_crud.create_resume_version(
        db_session,
        source_type="resume",
        raw_text="resume text",
        content_html="<p>Old Skills Line</p>",
        is_active=True,
    )
    automation_settings_crud.upsert_automation_settings(
        db_session, min_score_to_proceed=6, max_score_to_archive=3, auto_tailor_soft_enabled=True
    )
    run, search_result = _make_run_and_search_result(db_session)

    monkeypatch.setattr(pipeline, "extract_job_text", lambda url: "Sample job text")
    monkeypatch.setattr(pipeline, "get_llm_provider", lambda: _FakeLLMProvider())
    monkeypatch.setattr(pipeline, "evaluate_job_posting", lambda *a, **k: _eval_result(9))
    monkeypatch.setattr(
        pipeline,
        "propose_soft_fragment_changes",
        lambda *a, **k: [
            {
                "level": "soft",
                "change_type": "title",
                "field_path": None,
                "target_ref": None,
                "original_text": "Old Skills Line",
                "proposed_text": "New Title Line",
                "proposed_content": None,
            }
        ],
    )

    pipeline._process_search_result(db_session, run.id, search_result.id, "resume", "linkedin", [], [], None)

    refreshed = search_results_crud.get_search_result(db_session, search_result.id)
    tailoring_session = tailoring_sessions_crud.get_tailoring_session_for_job(
        db_session, refreshed.promoted_job_posting_id
    )

    assert "New Title Line" not in tailoring_session.working_html

    changes = tailoring_changes_crud.list_tailoring_changes_for_session(db_session, tailoring_session.id)
    assert len(changes) == 1
    assert changes[0].status == "pending"


@pytest.mark.automation
def test_run_automation_pipeline_stops_early_at_results_cap(monkeypatch, db_session):
    resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume text", is_active=True)
    automation_settings_crud.upsert_automation_settings(
        db_session, min_score_to_proceed=6, max_score_to_archive=3, quick_filter_enabled=False
    )

    run = automation_runs_crud.create_automation_run(
        db_session, queries_planned=["query one", "query two"], max_results_override=1
    )

    search_call_count = {"count": 0}

    class _FakeProvider:
        def __init__(self):
            search_call_count["count"] += 1
            self._index = search_call_count["count"]

        def search(self, query, num=None, date=None):
            return {
                "results": [
                    {
                        "title": "Job",
                        "url": f"https://boards.greenhouse.io/a/jobs/{self._index}0",
                        "snippet": "Snippet",
                    },
                    {
                        "title": "Job 2",
                        "url": f"https://boards.greenhouse.io/a/jobs/{self._index}1",
                        "snippet": "Snippet 2",
                    },
                ],
                "requested_num": 30,
                "returned_count": 2,
                "raw_response": {},
            }

    monkeypatch.setattr(pipeline, "SerpentSearchProvider", _FakeProvider)
    monkeypatch.setattr(pipeline, "extract_job_text", lambda url: "Sample job text")
    monkeypatch.setattr(pipeline, "get_llm_provider", lambda: _FakeLLMProvider())
    monkeypatch.setattr(pipeline, "evaluate_job_posting", lambda *a, **k: _eval_result(9))

    pipeline.run_automation_pipeline(db_session, run.id)

    assert search_call_count["count"] == 1

    refreshed_run = automation_runs_crud.get_automation_run(db_session, run.id)
    assert refreshed_run.status == "done"
    assert refreshed_run.passed_count == 1
    assert len(jobs_crud.list_job_postings(db_session)) == 1


@pytest.mark.automation
def test_run_automation_pipeline_processes_multiple_results_when_uncapped(monkeypatch, db_session):
    resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume text", is_active=True)
    automation_settings_crud.upsert_automation_settings(
        db_session, min_score_to_proceed=6, max_score_to_archive=3, quick_filter_enabled=False
    )

    run = automation_runs_crud.create_automation_run(db_session, queries_planned=["query one"])

    class _FakeProvider:
        def __init__(self):
            pass

        def search(self, query, num=None, date=None):
            return {
                "results": [
                    {"title": "Job A", "url": "https://boards.greenhouse.io/a/jobs/1", "snippet": "S"},
                    {"title": "Job B", "url": "https://boards.greenhouse.io/a/jobs/2", "snippet": "S"},
                ],
                "requested_num": 30,
                "returned_count": 2,
                "raw_response": {},
            }

    def _sync_submit(func, *args, **kwargs):
        future = Future()
        future.set_result(func(*args, **kwargs))
        return future

    monkeypatch.setattr(pipeline, "SerpentSearchProvider", _FakeProvider)
    monkeypatch.setattr(pipeline, "extract_job_text", lambda url: "Sample job text")
    monkeypatch.setattr(pipeline, "get_llm_provider", lambda: _FakeLLMProvider())
    monkeypatch.setattr(pipeline, "evaluate_job_posting", lambda *a, **k: _eval_result(9))
    monkeypatch.setattr(pipeline, "submit_automation_task", _sync_submit)
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    pipeline.run_automation_pipeline(db_session, run.id)

    refreshed_run = automation_runs_crud.get_automation_run(db_session, run.id)
    assert refreshed_run.status == "done"
    assert refreshed_run.passed_count == 2


@pytest.mark.automation
def test_run_automation_pipeline_marks_run_failed_on_unexpected_error(monkeypatch, db_session):
    run = automation_runs_crud.create_automation_run(db_session, queries_planned=["query one"])

    def _boom(*args, **kwargs):
        raise RuntimeError("unexpected failure")

    monkeypatch.setattr(pipeline, "_run_search_and_process", _boom)

    with pytest.raises(RuntimeError):
        pipeline.run_automation_pipeline(db_session, run.id)

    refreshed_run = automation_runs_crud.get_automation_run(db_session, run.id)
    assert refreshed_run.status == "failed"
    assert refreshed_run.error == "unexpected failure"


@pytest.mark.automation
def test_run_automation_pipeline_noop_for_missing_run(db_session):
    pipeline.run_automation_pipeline(db_session, 999)