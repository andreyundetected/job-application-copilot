import threading
import time

import config

_lock = threading.Lock()
_last_call_at: dict[str, float] = {}


def throttle(ats_name: str) -> None:
    min_interval = 1.0 / max(config.DISCOVERY_RATE_LIMIT_PER_SEC, 0.1)

    with _lock:
        now = time.monotonic()
        last = _last_call_at.get(ats_name, 0.0)
        wait_for = min_interval - (now - last)
        if wait_for > 0:
            _last_call_at[ats_name] = last + min_interval
        else:
            _last_call_at[ats_name] = now

    if wait_for > 0:
        time.sleep(wait_for)