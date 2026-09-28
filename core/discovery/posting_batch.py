import datetime
import logging
import threading
import time

from core.discovery import run_control
from core.discovery.quick_screen import quick_screen_and_dispatch
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5

_lock = threading.Lock()
_pending_ids: list[int] = []
_stop_event = threading.Event()
_started = False
_last_flush_at: float = 0.0


def add_posting(posting_id: int, posted_at=None) -> None:
    session = DiscoverySessionLocal()
    try:
        settings = discovery_crud.get_or_create_settings(session)
        quick_batch_enabled = settings.quick_batch_enabled
        backlog_hours = settings.initial_backlog_hours
    finally:
        session.close()

    if posted_at is not None and backlog_hours and backlog_hours > 0:
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


def decide_batch_action(
    enabled: bool,
    was_enabled: bool,
    elapsed_seconds: float,
    window_seconds: float,
    pending: int,
    force_flush_size: int | None,
) -> str:
    if not enabled:
        return "drain" if was_enabled and pending > 0 else "idle"
    if not was_enabled:
        return "start"
    size_triggered = bool(force_flush_size) and force_flush_size > 0 and pending >= force_flush_size
    if elapsed_seconds >= window_seconds or size_triggered:
        return "flush"
    return "wait"


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


def _loop() -> None:
    global _last_flush_at
    was_enabled = False

    while not _stop_event.is_set():
        session = DiscoverySessionLocal()
        try:
            settings = discovery_crud.get_or_create_settings(session)
            enabled = settings.enabled
            minutes = settings.batch_window_minutes
            force_flush_size = settings.batch_force_flush_size
        finally:
            session.close()

        action = decide_batch_action(
            enabled,
            was_enabled,
            time.monotonic() - _last_flush_at,
            max(10, minutes * 60),
            pending_count(),
            force_flush_size,
        )
        was_enabled = enabled

        if action == "start":
            _last_flush_at = time.monotonic()
            run_control.set_batch_last_flush_at(datetime.datetime.utcnow().isoformat())
        elif action == "flush":
            from core.discovery.eval_executor import submit_eval_task

            submit_eval_task(_flush)
            _last_flush_at = time.monotonic()
            run_control.set_batch_last_flush_at(datetime.datetime.utcnow().isoformat())
        elif action == "drain":
            from core.discovery.eval_executor import submit_eval_task

            submit_eval_task(_flush)
            run_control.set_batch_last_flush_at(None)
        elif action == "idle":
            run_control.set_batch_last_flush_at(None)

        _stop_event.wait(POLL_INTERVAL_SECONDS)


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