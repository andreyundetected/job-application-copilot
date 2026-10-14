from concurrent.futures import ThreadPoolExecutor

import config

_executor: ThreadPoolExecutor | None = None


def get_post_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=config.DISCOVERY_POST_MAX_WORKERS, thread_name_prefix="discovery-post"
        )
    return _executor


def submit_post_task(func, *args, **kwargs):
    return get_post_executor().submit(func, *args, **kwargs)