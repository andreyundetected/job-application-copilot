from concurrent.futures import ThreadPoolExecutor

import config
from core.discovery import run_control

_executor: ThreadPoolExecutor | None = None


def get_discovery_eval_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=config.DISCOVERY_EVAL_MAX_WORKERS)
    return _executor


def submit_eval_task(func, *args, **kwargs):
    run_control.flow_add("eval", "queued")

    def runner():
        run_control.flow_add("eval", "queued", -1)
        run_control.flow_add("eval", "active")
        try:
            return func(*args, **kwargs)
        finally:
            run_control.flow_add("eval", "active", -1)
            run_control.flow_add("eval", "done")

    return get_discovery_eval_executor().submit(runner)