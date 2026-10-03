import datetime
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import config
from core.discovery import run_control
from core.discovery.quick_screen import quick_screen_and_dispatch
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
SETTINGS_CACHE_SECONDS = 5
FAILURE_BACKOFF_SECONDS = 30
MAX_CHUNK_FAILURES = 3

_lock = threading.Lock()
_flush_lock = threading.Lock()
_pending_ids: list[int] = []
_stop_event = threading.Event()
_started = False
_thread: threading.Thread | None = None
_screen_executor: ThreadPoolExecutor | None = None

_last_flush_at: float = 0.0
_window_seconds: float = 900.0
_force_flush_size: int | None = None
_enabled = False
_flush_running = False
_last_error: str | None = None
_retry_not_before: float = 0.0
_consecutive_failures = 0

_settings_cache: dict = {"at": 0.0, "value": None}
_settings_cache_lock = threading.Lock()


def _read_settings() -> dict:
    now = time.monotonic()
    with _settings_cache_lock:
        cached = _settings_cache["value"]
        if cached is not None and now - _settings_cache["at"] < SETTINGS_CACHE_SECONDS:
            return cached

    session = DiscoverySessionLocal()
    try:
        settings = discovery_crud.get_or_create_settings(session)
        value = {
            "enabled": settings.enabled,
            "quick_batch_enabled": settings.quick_batch_enabled,
            "initial_backlog_hours": settings.initial_backlog_hours,
            "batch_window_minutes": settings.batch_window_minutes,
            "batch_force_flush_size": settings.batch_force_flush_size,
        }
    except Exception:
        logger.exception("[batch] could not read discovery settings")
        if cached is not None:
            return cached
        raise
    finally:
        session.close()

    with _settings_cache_lock:
        _settings_cache["at"] = time.monotonic()
        _settings_cache["value"] = value
    return value


def _get_screen_executor() -> ThreadPoolExecutor:
    global _screen_executor
    if _screen_executor is None:
        _screen_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="discovery-screen")
    return _screen_executor


def add_posting(posting_id: int, posted_at=None) -> None:
    try:
        settings = _read_settings()
    except Exception:
        with _lock:
            _pending_ids.append(posting_id)
        return

    quick_batch_enabled = settings["quick_batch_enabled"]
    backlog_hours = settings["initial_backlog_hours"]

    if posted_at is not None and backlog_hours and backlog_hours > 0:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=backlog_hours)
        if posted_at < cutoff:
            logger.info(
                "[batch] posting %s: older than backlog window (%sh), stored but not sent to screening",
                posting_id, backlog_hours,
            )
            return

    if not quick_batch_enabled:
        from core.discovery.eval_executor import submit_eval_task as _submit
        from core.discovery.pipeline import process_discovered_posting

        _submit(process_discovered_posting, posting_id)
        return

    with _lock:
        _pending_ids.append(posting_id)


def pending_count() -> int:
    with _lock:
        return len(_pending_ids)


def _peek_chunk(size: int) -> list[int]:
    with _lock:
        return _pending_ids[:size]


def _drop_processed(count: int) -> None:
    with _lock:
        del _pending_ids[:count]


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


def get_state() -> dict:
    pending = pending_count()
    if _flush_running or not _enabled:
        seconds = None
    elif _force_flush_size and _force_flush_size > 0 and pending >= _force_flush_size:
        seconds = 0
    else:
        seconds = max(0, round(_window_seconds - (time.monotonic() - _last_flush_at)))

    return {
        "loop_alive": _thread is not None and _thread.is_alive(),
        "flush_running": _flush_running,
        "seconds_until_flush": seconds,
        "last_error": _last_error,
    }


def _flush() -> None:
    global _flush_running, _last_flush_at, _last_error, _retry_not_before, _consecutive_failures

    if not _flush_lock.acquire(blocking=False):
        return

    _flush_running = True
    chunk: list[int] = []
    total = 0
    passed = 0
    skipped = 0

    try:
        run_control.set_batch_evaluating(True)
        chunk_size = max(1, config.DISCOVERY_SCREEN_CHUNK_SIZE)
        logger.info("[batch] flush started: %s pending postings", pending_count())

        while True:
            chunk = _peek_chunk(chunk_size)
            if not chunk:
                break
            result = quick_screen_and_dispatch(chunk)
            _drop_processed(len(chunk))
            total += len(chunk)
            passed += result["passed"]
            skipped += result["skipped"]
            chunk = []
            _consecutive_failures = 0
            _last_error = None

        logger.info("[batch] flush complete: %s screened, %s passed, %s skipped", total, passed, skipped)
    except Exception as error:
        _consecutive_failures += 1
        _last_error = f"{type(error).__name__}: {error}"
        logger.exception("[batch] flush failed, %s postings left in queue", pending_count())
        if _consecutive_failures >= MAX_CHUNK_FAILURES and chunk:
            _drop_processed(len(chunk))
            _consecutive_failures = 0
            logger.error(
                "[batch] dropping chunk of %s postings after %s failed attempts, they stay in the db unscreened",
                len(chunk), MAX_CHUNK_FAILURES,
            )
        else:
            _retry_not_before = time.monotonic() + FAILURE_BACKOFF_SECONDS
    finally:
        run_control.set_batch_evaluating(False)
        if total:
            run_control.set_last_batch_result(total, skipped, passed)
        _last_flush_at = time.monotonic()
        run_control.set_batch_last_flush_at(datetime.datetime.utcnow().isoformat())
        _flush_running = False
        _flush_lock.release()


def _submit_flush() -> None:
    if _flush_running or time.monotonic() < _retry_not_before:
        return
    _get_screen_executor().submit(_flush)


def _loop() -> None:
    global _last_flush_at, _window_seconds, _force_flush_size, _enabled
    was_enabled = False

    while not _stop_event.is_set():
        try:
            settings = _read_settings()
            enabled = settings["enabled"]
            _window_seconds = max(10, settings["batch_window_minutes"] * 60)
            _force_flush_size = settings["batch_force_flush_size"]
            _enabled = enabled

            action = decide_batch_action(
                enabled,
                was_enabled,
                time.monotonic() - _last_flush_at,
                _window_seconds,
                pending_count(),
                _force_flush_size,
            )
            was_enabled = enabled

            if action == "start":
                _last_flush_at = time.monotonic()
                run_control.set_batch_last_flush_at(datetime.datetime.utcnow().isoformat())
            elif action == "flush":
                _submit_flush()
            elif action == "drain":
                _submit_flush()
                run_control.set_batch_last_flush_at(None)
            elif action == "idle":
                run_control.set_batch_last_flush_at(None)
        except Exception:
            logger.exception("[batch] loop iteration failed")

        _stop_event.wait(POLL_INTERVAL_SECONDS)


def start_posting_batch_collector() -> None:
    global _started, _thread
    with _lock:
        if _started:
            return
        _started = True
    _thread = threading.Thread(target=_loop, daemon=True, name="discovery-batch-flush")
    _thread.start()


def flush_now() -> None:
    _flush()


def stop_posting_batch_collector() -> None:
    _stop_event.set()