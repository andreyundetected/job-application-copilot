import logging
import threading

from core.discovery import run_control
from core.discovery.quick_screen import quick_screen_and_dispatch
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_pending_ids: list[int] = []
_stop_event = threading.Event()
_started = False


def add_posting(posting_id: int, posted_at=None) -> None:
    session = DiscoverySessionLocal()
    try:
        settings = discovery_crud.get_or_create_settings(session)
        quick_batch_enabled = settings.quick_batch_enabled
        backlog_hours = settings.initial_backlog_hours
    finally:
        session.close()

    if posted_at is not None and backlog_hours and backlog_hours > 0:
        import datetime

        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=backlog_hours)
        if posted_at < cutoff:
            logger.info(
                "[batch] posting %s: older than backlog window (%sh), stored but not sent to screening",
                posting_id, backlog_hours,
            )
            return

    if not quick_batch_enabled:
        from core.discovery.pipeline import process_discovered_posting
        from core.discovery.eval_executor import submit_eval_task as _submit

        _submit(process_discovered_posting, posting_id)
        return

    with _lock:
        _pending_ids.append(posting_id)


def pending_count() -> int:
    with _lock:
        return len(_pending_ids)


def _flush() -> None:
    with _lock:
        ids = _pending_ids[:]
        _pending_ids.clear()

    logger.info("[batch] flush check: %s pending postings", len(ids))

    if not ids:
        return

    logger.info("[batch] flushing %s postings for quick screen", len(ids))
    run_control.set_batch_evaluating(True)
    try:
        result = quick_screen_and_dispatch(ids)
    finally:
        run_control.set_batch_evaluating(False)
    run_control.set_last_batch_result(len(ids), result["skipped"], result["passed"])
    logger.info("[batch] flush complete")


_last_flush_at: float = 0.0


def _loop() -> None:
    global _last_flush_at
    import datetime
    import time

    _last_flush_at = time.monotonic()
    run_control.set_batch_last_flush_at(datetime.datetime.utcnow().isoformat())
    poll_interval_seconds = 5

    while not _stop_event.is_set():
        session = DiscoverySessionLocal()
        try:
            settings = discovery_crud.get_or_create_settings(session)
            minutes = settings.batch_window_minutes
            force_flush_size = settings.batch_force_flush_size
        finally:
            session.close()

        window_seconds = max(10, minutes * 60)
        elapsed = time.monotonic() - _last_flush_at
        size_triggered = force_flush_size and force_flush_size > 0 and pending_count() >= force_flush_size

        if elapsed >= window_seconds or size_triggered:
            from core.discovery.eval_executor import submit_eval_task

            submit_eval_task(_flush)
            _last_flush_at = time.monotonic()
            run_control.set_batch_last_flush_at(datetime.datetime.utcnow().isoformat())
        else:
            _stop_event.wait(poll_interval_seconds)


def start_posting_batch_collector() -> None:
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, daemon=True, name="discovery-batch-flush").start()


def flush_now() -> None:
    _flush()


def stop_posting_batch_collector() -> None:
    _stop_event.set()
    flush_now()