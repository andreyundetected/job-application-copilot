import datetime
import logging
import threading

import config
from core.discovery.poll_cycle import run_poll_tick
from core.discovery.wayback_scan import run_wayback_scan_cycle
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)

_started = False
_started_lock = threading.Lock()
_stop_event = threading.Event()


def _settings_enabled() -> bool:
    session = DiscoverySessionLocal()
    try:
        return discovery_crud.get_or_create_settings(session).enabled
    finally:
        session.close()


def _wayback_loop() -> None:
    check_interval_seconds = 600
    while not _stop_event.is_set():
        try:
            if _settings_enabled():
                session = DiscoverySessionLocal()
                try:
                    settings = discovery_crud.get_or_create_settings(session)
                finally:
                    session.close()

                due = (
                    settings.last_wayback_run_at is None
                    or datetime.datetime.utcnow() - settings.last_wayback_run_at
                    >= datetime.timedelta(hours=settings.wayback_interval_hours)
                )
                if due:
                    run_wayback_scan_cycle()
        except Exception as error:
            logger.error("[scheduler] wayback loop error: %s", error)

        _stop_event.wait(check_interval_seconds)


def _poll_loop() -> None:
    while not _stop_event.is_set():
        try:
            if _settings_enabled():
                run_poll_tick()
        except Exception as error:
            logger.error("[scheduler] poll loop error: %s", error)

        _stop_event.wait(config.DISCOVERY_POLL_TICK_SECONDS)


def start_discovery_schedulers() -> None:
    global _started
    with _started_lock:
        if _started:
            return
        _started = True

    threading.Thread(target=_wayback_loop, daemon=True, name="discovery-wayback").start()
    threading.Thread(target=_poll_loop, daemon=True, name="discovery-poll").start()
    logger.info("[scheduler] discovery schedulers started")


def stop_discovery_schedulers() -> None:
    _stop_event.set()