import threading

_lock = threading.Lock()
_cancel_event = threading.Event()
_skip_wayback_event = threading.Event()


def wait_or_cancel(seconds: float) -> bool:
    return _cancel_event.wait(seconds)


def request_skip_wayback() -> None:
    _skip_wayback_event.set()


def request_skip_wayback_if_recent() -> None:
    import datetime

    from core.discovery_db import crud as discovery_crud
    from core.discovery_db.session import DiscoverySessionLocal

    session = DiscoverySessionLocal()
    try:
        settings = discovery_crud.get_or_create_settings(session)
    finally:
        session.close()

    if settings.last_wayback_run_at is None:
        return

    due = datetime.datetime.utcnow() - settings.last_wayback_run_at >= datetime.timedelta(hours=settings.wayback_interval_hours)
    if not due:
        _skip_wayback_event.set()


def should_skip_wayback() -> bool:
    return _skip_wayback_event.is_set()


def clear_skip_wayback() -> None:
    _skip_wayback_event.clear()

_stats = {
    "phase": "idle",
    "new_companies_this_run": 0,
    "new_postings_this_run": 0,
    "wayback_ats_done": 0,
    "wayback_ats_total": 0,
    "collection_checked": 0,
    "collection_total": 0,
    "collection_done": False,
    "screening_checked": 0,
    "screening_total": 0,
    "screening_done": False,
    "last_pass_duration_seconds": None,
    "collection_started_at": None,
}

_tier_deltas: dict[int, list[float]] = {}
_TIER_DELTA_WINDOW = 200


_batch_stats = {
    "last_batch_size": 0,
    "last_batch_skipped": 0,
    "last_batch_proceeded": 0,
    "evaluating_batch": False,
    "last_flush_at": None,
}


def set_batch_evaluating(value: bool) -> None:
    with _lock:
        _batch_stats["evaluating_batch"] = value


def set_batch_last_flush_at(value) -> None:
    with _lock:
        _batch_stats["last_flush_at"] = value


def set_last_batch_result(size: int, skipped: int, proceeded: int) -> None:
    with _lock:
        _batch_stats.update({"last_batch_size": size, "last_batch_skipped": skipped, "last_batch_proceeded": proceeded})


def get_batch_stats() -> dict:
    with _lock:
        return dict(_batch_stats)


_eval_stats = {"evaluated_count": 0, "passed_count": 0, "archived_count": 0, "in_flight": 0}


def eval_start() -> None:
    with _lock:
        _eval_stats["in_flight"] += 1


def eval_finish(passed: bool, archived: bool) -> None:
    with _lock:
        _eval_stats["in_flight"] = max(0, _eval_stats["in_flight"] - 1)
        _eval_stats["evaluated_count"] += 1
        if passed:
            _eval_stats["passed_count"] += 1
        if archived:
            _eval_stats["archived_count"] += 1


def get_eval_stats() -> dict:
    with _lock:
        return dict(_eval_stats)


def reset_run():
    _cancel_event.clear()
    _skip_wayback_event.clear()
    with _lock:
        _ats_checked_counts.clear()
        _batch_stats.update(
            {"last_batch_size": 0, "last_batch_skipped": 0, "last_batch_proceeded": 0, "evaluating_batch": False}
        )
        _eval_stats.update({"evaluated_count": 0, "passed_count": 0, "archived_count": 0, "in_flight": 0})
        _stats.update(
            {
                "phase": "wayback",
                "new_companies_this_run": 0,
                "new_postings_this_run": 0,
                "wayback_ats_done": 0,
                "wayback_ats_total": 0,
                "collection_checked": 0,
                "collection_total": 0,
                "collection_done": False,
                "screening_checked": 0,
                "screening_total": 0,
                "screening_done": False,
                "last_pass_duration_seconds": None,
                "collection_started_at": None,
            }
        )
        _tier_deltas.clear()
        global _current_tier
        _current_tier = None
        _tier_found_counts.clear()

    from core.discovery.quantile_queue import reset_swrr_state
    reset_swrr_state()


def cancel_run():
    _cancel_event.set()
    with _lock:
        _stats["phase"] = "idle"


def is_cancelled() -> bool:
    return _cancel_event.is_set()


def set_phase(phase: str) -> None:
    with _lock:
        _stats["phase"] = phase


def add_new_companies(count: int) -> None:
    if not count:
        return
    with _lock:
        _stats["new_companies_this_run"] += count


def add_new_postings(count: int) -> None:
    if not count:
        return
    with _lock:
        _stats["new_postings_this_run"] += count


def set_wayback_total(total: int) -> None:
    with _lock:
        _stats["wayback_ats_total"] = total


def increment_wayback_done() -> None:
    with _lock:
        _stats["wayback_ats_done"] += 1


def set_collection_total(total: int) -> None:
    with _lock:
        _stats["collection_total"] = total


def add_collection_checked(count: int) -> None:
    if not count:
        return
    with _lock:
        _stats["collection_checked"] += count


_ats_checked_counts: dict[str, int] = {}


def add_ats_checked(ats_name: str, count: int = 1) -> None:
    with _lock:
        _ats_checked_counts[ats_name] = _ats_checked_counts.get(ats_name, 0) + count


def get_ats_checked_counts() -> dict[str, int]:
    with _lock:
        return dict(_ats_checked_counts)


def mark_collection_done() -> None:
    with _lock:
        _stats["collection_done"] = True


def set_screening_total(total: int) -> None:
    with _lock:
        _stats["screening_total"] = total


def add_screening_checked(count: int) -> None:
    if not count:
        return
    with _lock:
        _stats["screening_checked"] += count


def mark_screening_done() -> None:
    with _lock:
        _stats["screening_done"] = True


def record_check_delta(tier_index: int, delta_seconds: float) -> None:
    with _lock:
        bucket = _tier_deltas.setdefault(tier_index, [])
        bucket.append(delta_seconds)
        if len(bucket) > _TIER_DELTA_WINDOW:
            bucket.pop(0)


def get_tier_delta_averages() -> dict[int, float]:
    with _lock:
        return {tier: sum(values) / len(values) for tier, values in _tier_deltas.items() if values}


def set_last_pass_duration(seconds: float) -> None:
    with _lock:
        _stats["last_pass_duration_seconds"] = seconds


_current_tier: int | None = None
_tier_found_counts: dict[int, int] = {}


def set_current_tier(tier_index: int | None) -> None:
    global _current_tier
    with _lock:
        _current_tier = tier_index


def reset_tier_found(tier_index: int) -> None:
    with _lock:
        _tier_found_counts[tier_index] = 0


def add_tier_found(tier_index: int, count: int) -> None:
    if not count:
        return
    with _lock:
        _tier_found_counts[tier_index] = _tier_found_counts.get(tier_index, 0) + count


_tier_processed_counts: dict[int, int] = {}


def add_tier_processed(tier_index: int, count: int) -> None:
    with _lock:
        _tier_processed_counts[tier_index] = _tier_processed_counts.get(tier_index, 0) + count


def reset_tier_processed(tier_index: int) -> None:
    with _lock:
        _tier_processed_counts[tier_index] = 0


def get_tier_processed_counts() -> dict[int, int]:
    with _lock:
        return dict(_tier_processed_counts)


def get_current_tier() -> int | None:
    with _lock:
        return _current_tier


def get_tier_found_counts() -> dict[int, int]:
    with _lock:
        return dict(_tier_found_counts)


_pass_started_at_by_quantile: dict[int, float] = {}
_quantile_durations: dict[int, list[float]] = {}
_QUANTILE_DURATION_WINDOW = 20


def record_quantile_pass_duration(quantile_index: int, seconds: float) -> None:
    with _lock:
        bucket = _quantile_durations.setdefault(quantile_index, [])
        bucket.append(seconds)
        if len(bucket) > _QUANTILE_DURATION_WINDOW:
            bucket.pop(0)


def get_quantile_duration_averages() -> dict[int, float]:
    with _lock:
        return {q: sum(v) / len(v) for q, v in _quantile_durations.items() if v}


def set_collection_started_at(value) -> None:
    with _lock:
        _stats["collection_started_at"] = value


def get_stats() -> dict:
    with _lock:
        return dict(_stats)