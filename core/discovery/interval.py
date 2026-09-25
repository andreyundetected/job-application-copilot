import datetime

TIER_MAX_AGES = [
    datetime.timedelta(hours=1),
    datetime.timedelta(days=1),
    datetime.timedelta(days=7),
    datetime.timedelta(days=30),
    datetime.timedelta(days=90),
]

TIER_INTERVALS = [
    datetime.timedelta(minutes=0),
    datetime.timedelta(minutes=15),
    datetime.timedelta(hours=1),
    datetime.timedelta(hours=6),
    datetime.timedelta(hours=12),
    datetime.timedelta(hours=24),
]


def bucket_index_for_age(age: datetime.timedelta) -> int:
    for index, max_age in enumerate(TIER_MAX_AGES):
        if age <= max_age:
            return index
    return len(TIER_INTERVALS) - 1


def compute_next_check_at(last_activity_at: datetime.datetime, now: datetime.datetime) -> datetime.datetime:
    index = bucket_index_for_age(now - last_activity_at)
    return now + TIER_INTERVALS[index]


def tier_bounds(tier_index: int, now: datetime.datetime):
    upper = now - (TIER_MAX_AGES[tier_index - 1] if tier_index > 0 else datetime.timedelta(0))
    lower = now - TIER_MAX_AGES[tier_index] if tier_index < len(TIER_MAX_AGES) else None
    return lower, upper