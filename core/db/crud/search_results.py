from sqlalchemy.orm import Session

from core.db.models import SearchResult


def create_search_result(
    session: Session,
    automation_run_id: int,
    query_text: str,
    url: str,
    url_normalized: str,
    source_platform: str | None = None,
    title: str | None = None,
    snippet: str | None = None,
) -> SearchResult:
    result = SearchResult(
        automation_run_id=automation_run_id,
        query_text=query_text,
        url=url,
        url_normalized=url_normalized,
        source_platform=source_platform,
        title=title,
        snippet=snippet,
    )
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


def get_search_result(session: Session, search_result_id: int) -> SearchResult | None:
    return session.get(SearchResult, search_result_id)


def get_search_result_by_url(session: Session, url_normalized: str) -> SearchResult | None:
    return (
        session.query(SearchResult)
        .filter(SearchResult.url_normalized == url_normalized)
        .first()
    )


def bulk_create_search_results(
    session: Session, automation_run_id: int, results: list[dict]
) -> tuple[list[SearchResult], dict]:
    created = []
    seen_in_batch: set[str] = set()
    skipped_intra_batch = 0
    skipped_already_known = 0

    for item in results:
        url_normalized = item["url_normalized"]
        if url_normalized in seen_in_batch:
            skipped_intra_batch += 1
            continue
        if get_search_result_by_url(session, url_normalized) is not None:
            skipped_already_known += 1
            continue

        seen_in_batch.add(url_normalized)
        row = SearchResult(
            automation_run_id=automation_run_id,
            query_text=item["query_text"],
            url=item["url"],
            url_normalized=url_normalized,
            source_platform=item.get("source_platform"),
            title=item.get("title"),
            snippet=item.get("snippet"),
        )
        session.add(row)
        created.append(row)

    session.commit()
    for row in created:
        session.refresh(row)

    return created, {
        "skipped_intra_batch": skipped_intra_batch,
        "skipped_already_known": skipped_already_known,
    }


def list_search_results_for_run(
    session: Session, automation_run_id: int, quick_filter_verdict: str | None = None
) -> list[SearchResult]:
    query = session.query(SearchResult).filter(
        SearchResult.automation_run_id == automation_run_id
    )
    if quick_filter_verdict is not None:
        query = query.filter(SearchResult.quick_filter_verdict == quick_filter_verdict)
    return query.order_by(SearchResult.created_at.asc()).all()


def set_quick_filter_verdict(
    session: Session, search_result_id: int, verdict: str
) -> SearchResult | None:
    result = session.get(SearchResult, search_result_id)
    if result is None:
        return None
    result.quick_filter_verdict = verdict
    session.commit()
    session.refresh(result)
    return result


def set_promoted_job_posting(
    session: Session, search_result_id: int, job_posting_id: int
) -> SearchResult | None:
    result = session.get(SearchResult, search_result_id)
    if result is None:
        return None
    result.promoted_job_posting_id = job_posting_id
    session.commit()
    session.refresh(result)
    return result


def count_promoted_for_run(session: Session, automation_run_id: int) -> int:
    return (
        session.query(SearchResult)
        .filter(
            SearchResult.automation_run_id == automation_run_id,
            SearchResult.promoted_job_posting_id.isnot(None),
        )
        .count()
    )