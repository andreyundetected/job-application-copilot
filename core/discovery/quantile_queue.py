import logging

from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)

LIVE_QUANTILE_COUNT = 7
EMPTY_GROUP_INDEX = LIVE_QUANTILE_COUNT

_step_counter = 0


def pick_next_quantile() -> int:
    global _step_counter
    _step_counter += 1

    n = _step_counter
    trailing_zeros = 0
    while n % 2 == 0:
        trailing_zeros += 1
        n //= 2

    return min(trailing_zeros, LIVE_QUANTILE_COUNT - 1)


def interleave_by_ats(companies: list) -> list:
    buckets: dict[str, list] = {}
    for company in companies:
        buckets.setdefault(company.ats_name, []).append(company)

    result = []
    while any(buckets.values()):
        for ats_name in list(buckets.keys()):
            if buckets[ats_name]:
                result.append(buckets[ats_name].pop(0))
            if not buckets[ats_name]:
                del buckets[ats_name]
    return result


def fetch_quantile_companies(quantile_index: int, batch_size: int) -> list:
    session = DiscoverySessionLocal()
    try:
        companies = discovery_crud.list_companies_in_rank_quantile(
            session, quantile_index, LIVE_QUANTILE_COUNT, batch_size
        )
    finally:
        session.close()

    return interleave_by_ats(companies)


def fetch_empty_group_companies(batch_size: int) -> list:
    session = DiscoverySessionLocal()
    try:
        companies = discovery_crud.list_companies_without_postings(session, batch_size)
    finally:
        session.close()

    return interleave_by_ats(companies)


def reset_swrr_state() -> None:
    global _step_counter
    _step_counter = 0