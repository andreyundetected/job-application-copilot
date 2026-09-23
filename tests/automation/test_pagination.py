import pytest

from core.automation import pipeline
from core.db.crud import automation_runs as automation_runs_crud
from core.db.crud import automation_settings as automation_settings_crud


def _page_response(index: int, count: int, requested_num: int = 100):
    if count == 0:
        return {"results": [], "requested_num": requested_num, "returned_count": 0, "raw_response": {}}
    results = [
        {
            "title": f"Job {index}-{i}",
            "url": f"https://boards.greenhouse.io/a/jobs/{index}{i}",
            "snippet": "S",
        }
        for i in range(count)
    ]
    return {"results": results, "requested_num": requested_num, "returned_count": count, "raw_response": {}}


@pytest.mark.automation
def test_run_single_query_paginates_until_short_page(monkeypatch, db_session):
    run = automation_runs_crud.create_automation_run(db_session)
    settings = automation_settings_crud.upsert_automation_settings(
        db_session, serpent_num_per_query=100, max_pages_per_query=5
    )

    call_log = []

    class _FakeProvider:
        def search(self, query, num=None, date=None, page=1):
            call_log.append(page)
            if page < 3:
                return _page_response(page, 100)
            return _page_response(page, 40)

    monkeypatch.setattr(pipeline, "get_search_provider", lambda: _FakeProvider())

    created = pipeline._run_single_query(db_session, run, "sample query", settings)

    assert call_log == [1, 2, 3]
    assert len(created) == 240


@pytest.mark.automation
def test_run_single_query_stops_at_max_pages_safety_cap(monkeypatch, db_session):
    run = automation_runs_crud.create_automation_run(db_session)
    settings = automation_settings_crud.upsert_automation_settings(
        db_session, serpent_num_per_query=100, max_pages_per_query=3
    )

    call_log = []

    class _FakeProvider:
        def search(self, query, num=None, date=None, page=1):
            call_log.append(page)
            return _page_response(page, 100)

    monkeypatch.setattr(pipeline, "get_search_provider", lambda: _FakeProvider())

    pipeline._run_single_query(db_session, run, "sample query", settings)

    assert call_log == [1, 2, 3]


@pytest.mark.automation
def test_run_single_query_stops_early_when_capped(monkeypatch, db_session):
    from core.db.crud import jobs as jobs_crud
    from core.db.crud import search_results as search_results_crud

    run = automation_runs_crud.create_automation_run(db_session)
    settings = automation_settings_crud.upsert_automation_settings(
        db_session, serpent_num_per_query=100, max_pages_per_query=5
    )

    call_log = []

    class _FakeProvider:
        def search(self, query, num=None, date=None, page=1):
            call_log.append(page)
            return _page_response(page, 100)

    monkeypatch.setattr(pipeline, "get_search_provider", lambda: _FakeProvider())

    def fake_count_promoted_for_run(session, run_id):
        return 5

    monkeypatch.setattr("core.automation.pipeline.crud.count_promoted_for_run", fake_count_promoted_for_run)

    pipeline._run_single_query(db_session, run, "sample query", settings, is_capped=True, max_results_override=5)

    assert call_log == [1]