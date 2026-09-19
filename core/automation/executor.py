from concurrent.futures import ThreadPoolExecutor

import config

_executor: ThreadPoolExecutor | None = None


def get_automation_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=config.AUTOMATION_MAX_WORKERS)
    return _executor


def submit_automation_task(func, *args, **kwargs):
    executor = get_automation_executor()
    return executor.submit(func, *args, **kwargs)