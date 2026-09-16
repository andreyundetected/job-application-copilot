from concurrent.futures import ThreadPoolExecutor

import config

_executor: ThreadPoolExecutor | None = None


def get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=config.TASK_MAX_WORKERS)
    return _executor


def submit_task(func, *args, **kwargs):
    executor = get_executor()
    return executor.submit(func, *args, **kwargs)