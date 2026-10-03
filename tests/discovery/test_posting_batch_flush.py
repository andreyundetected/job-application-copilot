import time

import pytest

import config
from core.discovery import posting_batch


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    posting_batch._pending_ids.clear()
    monkeypatch.setattr(posting_batch, "_consecutive_failures", 0)
    monkeypatch.setattr(posting_batch, "_retry_not_before", 0.0)
    monkeypatch.setattr(posting_batch, "_last_error", None)
    monkeypatch.setattr(config, "DISCOVERY_SCREEN_CHUNK_SIZE", 10)
    posting_batch._stop_event.clear()
    yield
    posting_batch._pending_ids.clear()
    posting_batch._stop_event.clear()


@pytest.mark.discovery
def test_flush_processes_in_chunks_and_empties_queue(monkeypatch):
    posting_batch._pending_ids.extend(range(30))
    sizes = []

    def fake_screen(ids):
        sizes.append(len(ids))
        return {"passed": len(ids), "skipped": 0}

    monkeypatch.setattr(posting_batch, "quick_screen_and_dispatch", fake_screen)

    posting_batch._flush()

    assert sizes == [10, 10, 10]
    assert posting_batch.pending_count() == 0


@pytest.mark.discovery
def test_flush_keeps_ids_when_screening_fails(monkeypatch):
    posting_batch._pending_ids.extend(range(30))

    def fake_screen(ids):
        raise RuntimeError("boom")

    monkeypatch.setattr(posting_batch, "quick_screen_and_dispatch", fake_screen)

    posting_batch._flush()

    assert posting_batch.pending_count() == 30
    assert posting_batch._retry_not_before > time.monotonic()
    assert "boom" in posting_batch._last_error


@pytest.mark.discovery
def test_flush_drops_poison_chunk_after_repeated_failures(monkeypatch):
    posting_batch._pending_ids.extend(range(30))

    def fake_screen(ids):
        raise RuntimeError("boom")

    monkeypatch.setattr(posting_batch, "quick_screen_and_dispatch", fake_screen)

    for _ in range(posting_batch.MAX_CHUNK_FAILURES):
        posting_batch._flush()

    assert posting_batch.pending_count() == 20


@pytest.mark.discovery
def test_flush_is_skipped_while_another_flush_holds_the_lock(monkeypatch):
    posting_batch._pending_ids.extend(range(5))
    calls = []
    monkeypatch.setattr(posting_batch, "quick_screen_and_dispatch", lambda ids: calls.append(ids))

    posting_batch._flush_lock.acquire()
    try:
        posting_batch._flush()
    finally:
        posting_batch._flush_lock.release()

    assert calls == []
    assert posting_batch.pending_count() == 5


@pytest.mark.discovery
def test_loop_survives_exception_in_iteration(monkeypatch):
    calls = []

    def fake_read_settings():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        posting_batch._stop_event.set()
        return {
            "enabled": False,
            "quick_batch_enabled": True,
            "initial_backlog_hours": 24,
            "batch_window_minutes": 15,
            "batch_force_flush_size": 25,
        }

    monkeypatch.setattr(posting_batch, "_read_settings", fake_read_settings)
    monkeypatch.setattr(posting_batch, "POLL_INTERVAL_SECONDS", 0.01)

    posting_batch._loop()

    assert len(calls) == 2