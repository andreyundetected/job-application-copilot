import logging
import threading

from core.discovery import run_control
from core.discovery.posting_batch import start_posting_batch_collector, stop_posting_batch_collector
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)

_started = False
_started_lock = threading.Lock()


def start_discovery_schedulers() -> None:
    """No longer runs its own polling loop - the entire wayback -> initial
    collection -> backlog -> listening sequence lives inside the task
    submitted by /automation/discovery/start (see ui/automation_page/router.py
    _run_discovery_bootstrap). This function only recovers from an unclean
    shutdown: if discovery was left enabled when the process died, it resumes
    automatically so an overnight crash doesn't silently stop collection."""
    global _started
    with _started_lock:
        if _started:
            return
        _started = True

    logger.info("[scheduler] starting posting batch collector thread")
    start_posting_batch_collector()

    discovery_session = DiscoverySessionLocal()
    try:
        settings = discovery_crud.get_or_create_settings(discovery_session)
        was_enabled = settings.enabled
        backlog_hours = settings.initial_backlog_hours
    finally:
        discovery_session.close()

    if was_enabled:
        logger.info("[scheduler] discovery was left enabled, resuming bootstrap (respecting wayback interval)")
        from core.tasks.executor import submit_task
        from ui.automation_page.router import _run_discovery_bootstrap

        run_control.reset_run()
        run_control.request_skip_wayback_if_recent()
        submit_task(_run_discovery_bootstrap, backlog_hours)
    else:
        logger.info("[scheduler] discovery is disabled, idling")


def stop_discovery_schedulers() -> None:
    run_control.cancel_run()
    stop_posting_batch_collector()