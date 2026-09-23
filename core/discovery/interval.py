import datetime
import random

_BUCKETS = [
    (datetime.timedelta(days=1), datetime.timedelta(minutes=15)),
    (datetime.timedelta(days=7), datetime.timedelta(hours=1)),
    (datetime.timedelta(days=30), datetime.timedelta(hours=6)),
    (datetime.timedelta(days=90), datetime.timedelta(hours=12)),
]
_DEFAULT_INTERVAL = datetime.timedelta(hours=24)
_DEFAULT_JITTER_MAX = datetime.timedelta(hours=6)


def compute_next_check_at(last_activity_at, now):
    if last_activity_at is None:
        age = datetime.timedelta(days=9999)
    else:
        age = now - last_activity_at

    for max_age, interval in _BUCKETS:
        if age <= max_age:
            return now + interval

    jitter_seconds = random.uniform(0, _DEFAULT_JITTER_MAX.total_seconds())
    return now + _DEFAULT_INTERVAL + datetime.timedelta(seconds=jitter_seconds)