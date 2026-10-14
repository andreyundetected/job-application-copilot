import pytest

import config
from core.discovery import eval_executor, posting_batch, run_control


class _SyncExecutor:
    def submit(self, func):
        func()


@pytest.mark.discovery
def test_flow_add_and_reset():
    run_control.reset_run()

    run_control.flow_add("screen", "active", 25)
    run_control.flow_add("screen", "active", -40)
    run_control.flow_add("eval", "queued", 3)

    flow = run_control.get_flow()
    assert flow["screen"]["active"] == 0
    assert flow["eval"]["queued"] == 3

    run_control.reset_run()
    assert run_control.get_flow()["eval"]["queued"] == 0


@pytest.mark.discovery
def test_submit_eval_task_moves_through_queue_to_done(monkeypatch):
    run_control.reset_run()
    monkeypatch.setattr(eval_executor, "get_discovery_eval_executor", lambda: _SyncExecutor())
    seen = []

    def work():
        seen.append(dict(run_control.get_flow()["eval"]))

    eval_executor.submit_eval_task(work)

    assert seen[0]["queued"] == 0
    assert seen[0]["active"] == 1
    flow = run_control.get_flow()["eval"]
    assert flow["queued"] == 0
    assert flow["active"] == 0
    assert flow["done"] == 1


@pytest.mark.discovery
def test_flush_takes_whole_wave_across_workers(monkeypatch):
    posting_batch._pending_ids.clear()
    monkeypatch.setattr(config, "DISCOVERY_SCREEN_CHUNK_SIZE", 10)
    monkeypatch.setattr(config, "DISCOVERY_SCREEN_WORKERS", 3)
    monkeypatch.setattr(posting_batch, "_consecutive_failures", 0)
    monkeypatch.setattr(posting_batch, "_retry_not_before", 0.0)
    monkeypatch.setattr(posting_batch, "_last_error", None)
    posting_batch._pending_ids.extend(range(70))
    sizes = []

    def fake_screen(ids):
        sizes.append(len(ids))
        return {"passed": len(ids), "skipped": 0}

    monkeypatch.setattr(posting_batch, "quick_screen_and_dispatch", fake_screen)

    posting_batch._flush()

    assert sizes == [30, 30, 10]
    assert posting_batch.pending_count() == 0