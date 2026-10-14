import pytest

import config
from core.discovery import pipeline, posting_batch, run_control


class _FakeSession:
    def close(self):
        pass

    def rollback(self):
        pass


@pytest.fixture()
def post_env(monkeypatch):
    run_control.reset_run()
    monkeypatch.setattr(pipeline, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(pipeline.crud, "get_job_posting", lambda session, job_id: object())
    monkeypatch.setattr(pipeline.crud, "set_job_activity", lambda session, job_id, label: None)


@pytest.mark.discovery
def test_post_processing_moves_both_stages_from_queue_to_done(monkeypatch, post_env):
    run_control.flow_add("tailor", "queued")
    run_control.flow_add("answers", "queued")
    order = []
    monkeypatch.setattr(pipeline, "maybe_auto_tailor", lambda *args, **kwargs: order.append("tailor"))
    monkeypatch.setattr(pipeline, "maybe_auto_answer_base_questions", lambda *args, **kwargs: order.append("answers"))

    pipeline._run_post_processing(1, "text", {}, True, True)

    flow = run_control.get_flow()
    assert order == ["tailor", "answers"]
    assert flow["tailor"] == {"queued": 0, "active": 0, "done": 1}
    assert flow["answers"] == {"queued": 0, "active": 0, "done": 1}


@pytest.mark.discovery
def test_post_processing_failure_does_not_block_next_stage(monkeypatch, post_env):
    run_control.flow_add("tailor", "queued")
    run_control.flow_add("answers", "queued")
    order = []

    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "maybe_auto_tailor", broken)
    monkeypatch.setattr(pipeline, "maybe_auto_answer_base_questions", lambda *args, **kwargs: order.append("answers"))

    pipeline._run_post_processing(1, "text", {}, True, True)

    flow = run_control.get_flow()
    assert order == ["answers"]
    assert flow["tailor"]["active"] == 0
    assert flow["tailor"]["done"] == 1
    assert flow["answers"]["done"] == 1


@pytest.mark.discovery
def test_post_processing_skips_disabled_stage(monkeypatch, post_env):
    run_control.flow_add("answers", "queued")
    called = []
    monkeypatch.setattr(pipeline, "maybe_auto_tailor", lambda *args, **kwargs: called.append("tailor"))
    monkeypatch.setattr(pipeline, "maybe_auto_answer_base_questions", lambda *args, **kwargs: called.append("answers"))

    pipeline._run_post_processing(1, "text", {}, False, True)

    flow = run_control.get_flow()
    assert called == ["answers"]
    assert flow["tailor"]["done"] == 0
    assert flow["answers"]["done"] == 1


@pytest.mark.discovery
def test_clear_pending_empties_queue(monkeypatch):
    posting_batch._pending_ids.clear()
    posting_batch._pending_ids.extend(range(5))
    monkeypatch.setattr(posting_batch, "_flush_running", False)

    assert posting_batch.clear_pending() == 5
    assert posting_batch.pending_count() == 0


@pytest.mark.discovery
def test_clear_pending_is_skipped_while_flush_runs(monkeypatch):
    posting_batch._pending_ids.clear()
    posting_batch._pending_ids.extend(range(5))
    monkeypatch.setattr(posting_batch, "_flush_running", True)

    assert posting_batch.clear_pending() == 0
    assert posting_batch.pending_count() == 5
    posting_batch._pending_ids.clear()