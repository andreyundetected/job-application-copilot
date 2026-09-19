import pytest

from core.db.crud import automation_runs as automation_runs_crud
from core.db.crud import jobs as jobs_crud
from core.db.crud import search_results as search_results_crud


def _make_run(db_session):
    return automation_runs_crud.create_automation_run(db_session)


@pytest.mark.db
def test_create_search_result(db_session):
    run = _make_run(db_session)

    result = search_results_crud.create_search_result(
        db_session,
        automation_run_id=run.id,
        query_text="sample query",
        url="https://boards.greenhouse.io/example/jobs/123",
        url_normalized="greenhouse.io/example/jobs/123",
        source_platform="greenhouse",
        title="Sample Role",
        snippet="Sample snippet text.",
    )

    assert result.id is not None
    assert result.quick_filter_verdict is None
    assert result.promoted_job_posting_id is None


@pytest.mark.db
def test_bulk_create_search_results_skips_intra_batch_duplicates(db_session):
    run = _make_run(db_session)

    created = search_results_crud.bulk_create_search_results(
        db_session,
        run.id,
        [
            {
                "query_text": "query a",
                "url": "https://boards.greenhouse.io/example/jobs/1",
                "url_normalized": "greenhouse.io/example/jobs/1",
            },
            {
                "query_text": "query b",
                "url": "https://boards.greenhouse.io/example/jobs/1?utm=x",
                "url_normalized": "greenhouse.io/example/jobs/1",
            },
        ],
    )

    assert len(created) == 1


@pytest.mark.db
def test_bulk_create_search_results_skips_cross_call_duplicates(db_session):
    run = _make_run(db_session)

    first_batch = search_results_crud.bulk_create_search_results(
        db_session,
        run.id,
        [
            {
                "query_text": "query a",
                "url": "https://jobs.lever.co/example/1",
                "url_normalized": "lever.co/example/1",
            }
        ],
    )
    second_batch = search_results_crud.bulk_create_search_results(
        db_session,
        run.id,
        [
            {
                "query_text": "query b",
                "url": "https://jobs.lever.co/example/1",
                "url_normalized": "lever.co/example/1",
            }
        ],
    )

    assert len(first_batch) == 1
    assert len(second_batch) == 0


@pytest.mark.db
def test_list_search_results_for_run_filters_by_verdict(db_session):
    run = _make_run(db_session)
    search_results_crud.bulk_create_search_results(
        db_session,
        run.id,
        [
            {
                "query_text": "q",
                "url": "https://jobs.ashbyhq.com/example/1",
                "url_normalized": "ashbyhq.com/example/1",
            },
            {
                "query_text": "q",
                "url": "https://jobs.ashbyhq.com/example/2",
                "url_normalized": "ashbyhq.com/example/2",
            },
        ],
    )
    results = search_results_crud.list_search_results_for_run(db_session, run.id)
    search_results_crud.set_quick_filter_verdict(db_session, results[0].id, "proceed")
    search_results_crud.set_quick_filter_verdict(db_session, results[1].id, "skip")

    proceeding = search_results_crud.list_search_results_for_run(
        db_session, run.id, quick_filter_verdict="proceed"
    )

    assert len(proceeding) == 1
    assert proceeding[0].id == results[0].id


@pytest.mark.db
def test_set_promoted_job_posting_and_count(db_session):
    run = _make_run(db_session)
    job = jobs_crud.create_job_posting(db_session, raw_text="job text")

    results = search_results_crud.bulk_create_search_results(
        db_session,
        run.id,
        [
            {
                "query_text": "q",
                "url": "https://jobs.ashbyhq.com/example/3",
                "url_normalized": "ashbyhq.com/example/3",
            }
        ],
    )

    assert search_results_crud.count_promoted_for_run(db_session, run.id) == 0

    search_results_crud.set_promoted_job_posting(db_session, results[0].id, job.id)

    assert search_results_crud.count_promoted_for_run(db_session, run.id) == 1