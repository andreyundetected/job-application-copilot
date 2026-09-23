from concurrent.futures import ThreadPoolExecutor

import config

_executor: ThreadPoolExecutor | None = None


def get_discovery_eval_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=config.DISCOVERY_EVAL_MAX_WORKERS)
    return _executor


def submit_eval_task(func, *args, **kwargs):
    executor = get_discovery_eval_executor()
    return executor.submit(func, *args, **kwargs)