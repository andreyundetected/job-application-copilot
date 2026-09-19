import pytest

from core.db.crud import api_usage_log as api_usage_log_crud
from core.db.crud import automation_runs as automation_runs_crud


@pytest.mark.db
def test_create_usage_log_for_llm_call(db_session):
    run = automation_runs_crud.create_automation_run(db_session)

    log = api_usage_log_crud.create_usage_log(
        db_session,
        provider="freellmapi",
        operation="evaluation",
        automation_run_id=run.id,
        model="gpt-test",
        input_tokens=100,
        output_tokens=40,
        reasoning_tokens=5,
        total_tokens=140,
        raw_usage={"prompt_tokens": 100, "completion_tokens": 40},
    )

    assert log.id is not None
    assert log.provider == "freellmapi"
    assert log.total_tokens == 140
    assert log.raw_usage["prompt_tokens"] == 100


@pytest.mark.db
def test_create_usage_log_for_search_call(db_session):
    run = automation_runs_crud.create_automation_run(db_session)

    log = api_usage_log_crud.create_usage_log(
        db_session,
        provider="serpent",
        operation="search_query",
        automation_run_id=run.id,
        requested_num=50,
        returned_count=42,
    )

    assert log.requested_num == 50
    assert log.returned_count == 42
    assert log.model is None


@pytest.mark.db
def test_list_usage_logs_for_run(db_session):
    run = automation_runs_crud.create_automation_run(db_session)
    other_run = automation_runs_crud.create_automation_run(db_session)

    api_usage_log_crud.create_usage_log(
        db_session, provider="serpent", operation="search_query", automation_run_id=run.id
    )
    api_usage_log_crud.create_usage_log(
        db_session, provider="freellmapi", operation="evaluation", automation_run_id=run.id
    )
    api_usage_log_crud.create_usage_log(
        db_session, provider="serpent", operation="search_query", automation_run_id=other_run.id
    )

    logs = api_usage_log_crud.list_usage_logs_for_run(db_session, run.id)

    assert len(logs) == 2


@pytest.mark.db
def test_sum_usage_for_run_aggregates_tokens_and_cost(db_session):
    run = automation_runs_crud.create_automation_run(db_session)

    api_usage_log_crud.create_usage_log(
        db_session,
        provider="freellmapi",
        operation="evaluation",
        automation_run_id=run.id,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        estimated_cost=0.01,
    )
    api_usage_log_crud.create_usage_log(
        db_session,
        provider="serpent",
        operation="search_query",
        automation_run_id=run.id,
        requested_num=50,
        returned_count=40,
        estimated_cost=0.002,
    )

    totals = api_usage_log_crud.sum_usage_for_run(db_session, run.id)

    assert totals["input_tokens"] == 100
    assert totals["output_tokens"] == 50
    assert totals["total_tokens"] == 150
    assert totals["requested_num"] == 50
    assert totals["returned_count"] == 40
    assert round(totals["estimated_cost"], 3) == 0.012
    assert totals["by_provider"] == {"freellmapi": 1, "serpent": 1}


@pytest.mark.db
def test_sum_usage_for_run_handles_no_logs(db_session):
    run = automation_runs_crud.create_automation_run(db_session)

    totals = api_usage_log_crud.sum_usage_for_run(db_session, run.id)

    assert totals["total_tokens"] == 0
    assert totals["estimated_cost"] == 0.0
    assert totals["by_provider"] == {}