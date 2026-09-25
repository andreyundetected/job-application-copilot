import datetime
import logging
from concurrent.futures import ThreadPoolExecutor

import config
from core.discovery import run_control
from core.discovery.ats import all_extractors
from core.discovery.interval import TIER_INTERVALS, bucket_index_for_age
from core.discovery.posting_batch import add_posting
from core.discovery.rate_limiter import throttle
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal

logger = logging.getLogger(__name__)

_EXTRACTORS_BY_NAME = {extractor.name: extractor for extractor in all_extractors()}

PASS_GAP_SECONDS = 30


def _check_one_company(company_id: int, ats_name: str, slug: str) -> list[int]:
    if run_control.is_cancelled():
        return []

    session = DiscoverySessionLocal()
    try:
        extractor = _EXTRACTORS_BY_NAME.get(ats_name)
        if extractor is None:
            logger.warning("[poll] no extractor for ats_name=%s (company_id=%s)", ats_name, company_id)
            return []

        now = datetime.datetime.utcnow()
        failed = False
        is_deleted = False
        had_new_activity = False
        new_ids: list[int] = []
        new_postings: list[dict] = []

        try:
            throttle(ats_name)
            postings = extractor.list_active_postings(slug)
        except Exception as error:
            logger.warning("[poll] %s/%s: list_active_postings failed: %s", ats_name, slug, error)
            failed = True
            postings = []

        if postings is None:
            is_deleted = True
            logger.info("[poll] %s/%s: board gone (404/410), marking deleted", ats_name, slug)
            postings = []

        has_postings = len(postings) > 0

        if postings:
            existing_ids = discovery_crud.get_existing_external_ids(session, company_id)
            new_postings = [p for p in postings if p["external_id"] not in existing_ids]

            for posting in new_postings:
                created = discovery_crud.create_discovered_posting(session, company_id, posting)
                if created is None:
                    continue
                had_new_activity = True
                new_ids.append(created.id)
                add_posting(created.id, posted_at=posting.get("posted_at"))

            if new_postings:
                logger.info("[poll] %s/%s: %s new postings found", ats_name, slug, len(new_postings))

        company = discovery_crud.get_company(session, company_id)
        last_activity_at = company.last_activity_at if company else None

        if had_new_activity:
            posting_dates = [p["posted_at"] for p in new_postings if p.get("posted_at")]
            if posting_dates:
                candidate_activity_at = max(posting_dates)
                if last_activity_at is None or candidate_activity_at > last_activity_at:
                    last_activity_at = candidate_activity_at

        if new_ids:
            run_control.add_new_postings(len(new_ids))

        prior_checked_at = company.last_checked_at if company else None

        if last_activity_at is not None:
            tier_index = bucket_index_for_age(now - last_activity_at)
        else:
            tier_index = company.assigned_tier if company and company.assigned_tier is not None else len(TIER_INTERVALS) - 1
        next_check_at = now + TIER_INTERVALS[tier_index]

        if prior_checked_at is not None:
            run_control.record_check_delta(tier_index, (now - prior_checked_at).total_seconds())

        discovery_crud.mark_company_checked(
            session,
            company_id,
            next_check_at=next_check_at,
            had_new_activity=had_new_activity,
            failed=failed,
            has_postings=has_postings,
            is_deleted=is_deleted,
            last_activity_at=last_activity_at,
        )
        run_control.add_ats_checked(ats_name)
        return new_ids
    finally:
        session.close()


def _run_batch(batch: list[tuple]) -> list[int]:
    all_new_ids: list[int] = []
    with ThreadPoolExecutor(max_workers=config.DISCOVERY_POLL_MAX_WORKERS) as executor:
        futures = {executor.submit(_check_one_company, *item): item for item in batch}
        for future in futures:
            try:
                all_new_ids.extend(future.result())
            except Exception as error:
                company_id, ats_name, slug = futures[future]
                logger.error("[poll] %s/%s (company_id=%s) check raised unexpectedly: %s", ats_name, slug, company_id, error)
    return all_new_ids


def _company_tuples(companies) -> list[tuple]:
    return [(c.id, c.ats_name, c.slug) for c in companies]


def run_initial_collection() -> int:
    ats_names = list(_EXTRACTORS_BY_NAME.keys())

    session = DiscoverySessionLocal()
    try:
        total_unchecked = discovery_crud.count_unchecked_companies(session)
        total_all = discovery_crud.count_all_active_companies(session)
    finally:
        session.close()

    already_checked = max(0, total_all - total_unchecked)

    run_control.set_collection_total(total_all)
    run_control.add_collection_checked(already_checked)
    run_control.set_collection_started_at(datetime.datetime.utcnow().isoformat())
    logger.info(
        "[collection] initial collection: %s companies never checked (%s already done out of %s total)",
        total_unchecked, already_checked, total_all,
    )

    run_control.set_phase("collecting")

    if total_unchecked == 0:
        run_control.mark_collection_done()
        return 0

    all_new_ids: list[int] = []
    batches_processed = 0

    while not run_control.is_cancelled():
        session = DiscoverySessionLocal()
        try:
            batch_companies = discovery_crud.list_unchecked_companies_balanced(
                session, config.DISCOVERY_POLL_BATCH_SIZE, ats_names
            )
            batch = _company_tuples(batch_companies)
        finally:
            session.close()

        if not batch:
            logger.info("[collection] no unchecked companies left")
            break

        batches_processed += 1
        new_ids = _run_batch(batch)
        all_new_ids.extend(new_ids)
        run_control.add_collection_checked(len(batch))

        logger.info(
            "[collection] batch %s: checked %s companies, %s new postings (total new so far: %s)",
            batches_processed, len(batch), len(new_ids), len(all_new_ids),
        )

    if not run_control.is_cancelled():
        run_control.mark_collection_done()
        discovery_session = DiscoverySessionLocal()
        try:
            discovery_crud.update_settings(discovery_session, initial_collection_done_at=datetime.datetime.utcnow())
        finally:
            discovery_session.close()
        logger.info("[collection] initial collection complete: %s total new postings", len(all_new_ids))

    return len(all_new_ids)


def run_one_live_quantile_cycle() -> int:
    from core.discovery.quantile_queue import LIVE_QUANTILE_COUNT, fetch_quantile_companies, pick_next_quantile

    run_control.set_phase("listening")
    cycle_started_at = datetime.datetime.utcnow()
    all_new_ids: list[int] = []
    steps_processed = 0
    empty_since = {i: None for i in range(LIVE_QUANTILE_COUNT)}
    quantile_step_started_at: dict[int, datetime.datetime] = {}

    while not run_control.is_cancelled():
        if all(empty_since.get(i) is not None for i in range(LIVE_QUANTILE_COUNT)):
            break

        quantile_index = pick_next_quantile()
        if empty_since.get(quantile_index) is not None:
            continue

        run_control.set_current_tier(quantile_index)
        if quantile_index not in quantile_step_started_at:
            run_control.reset_tier_found(quantile_index)
            run_control.reset_tier_processed(quantile_index)
            quantile_step_started_at[quantile_index] = datetime.datetime.utcnow()

        batch_companies = fetch_quantile_companies(quantile_index, config.DISCOVERY_POLL_BATCH_SIZE)
        if not batch_companies:
            empty_since[quantile_index] = datetime.datetime.utcnow()
            started = quantile_step_started_at.pop(quantile_index, None)
            if started:
                run_control.record_quantile_pass_duration(quantile_index, (datetime.datetime.utcnow() - started).total_seconds())
            logger.info("[poll] quantile %s fully drained", quantile_index)
            continue

        batch = _company_tuples(batch_companies)
        steps_processed += 1
        new_ids = _run_batch(batch)
        all_new_ids.extend(new_ids)
        run_control.add_tier_found(quantile_index, len(new_ids))
        run_control.add_tier_processed(quantile_index, len(batch))

    cycle_duration = (datetime.datetime.utcnow() - cycle_started_at).total_seconds()
    run_control.set_last_pass_duration(cycle_duration)

    if steps_processed:
        logger.info(
            "[poll] live quantile cycle done: %s queue steps, %s new postings, took %.1fs",
            steps_processed, len(all_new_ids), cycle_duration,
        )

    return len(all_new_ids)


def run_empty_group_sweep() -> int:
    from core.discovery.quantile_queue import EMPTY_GROUP_INDEX, fetch_empty_group_companies

    run_control.set_current_tier(EMPTY_GROUP_INDEX)
    run_control.reset_tier_found(EMPTY_GROUP_INDEX)
    started = datetime.datetime.utcnow()
    all_new_ids: list[int] = []

    while not run_control.is_cancelled():
        batch_companies = fetch_empty_group_companies(config.DISCOVERY_POLL_BATCH_SIZE)
        if not batch_companies:
            break

        batch = _company_tuples(batch_companies)
        new_ids = _run_batch(batch)
        all_new_ids.extend(new_ids)
        run_control.add_tier_found(EMPTY_GROUP_INDEX, len(new_ids))

    run_control.record_quantile_pass_duration(EMPTY_GROUP_INDEX, (datetime.datetime.utcnow() - started).total_seconds())
    logger.info("[poll] empty-group sweep done: %s new postings", len(all_new_ids))
    return len(all_new_ids)