import logging
import time

import requests

logger = logging.getLogger(__name__)

CDX_BASE_URL = "http://web.archive.org/cdx/search/cdx"
_PAGE_LIMIT = 20000
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 2
_REQUEST_TIMEOUT_SECONDS = 30


def fetch_cdx_urls(domain: str, is_cancelled=None) -> list[str]:
    logger.info("[cdx] fetching urls for domain=%s (this can take up to a minute)", domain)

    all_urls: list[str] = []
    resume_key: str | None = None
    page = 0

    while True:
        if is_cancelled is not None and is_cancelled():
            logger.info("[cdx] domain=%s: cancelled, stopping pagination early", domain)
            break
        params = {
            "url": domain,
            "matchType": "domain",
            "collapse": "urlkey",
            "output": "json",
            "filter": "statuscode:200",
            "fl": "original",
            "limit": _PAGE_LIMIT,
            "showResumeKey": "true",
        }
        if resume_key:
            params["resumeKey"] = resume_key

        data = _get_with_backoff(params)
        if not data:
            if page == 0:
                logger.warning("[cdx] domain=%s: no data returned", domain)
            break

        rows = data[1:] if data and data[0] == ["original"] else data

        next_resume_key = None
        if rows and rows[-1] and len(rows[-1]) == 1 and not rows[-1][0].startswith(("http://", "https://")):
            next_resume_key = rows[-1][0]
            rows = rows[:-1]

        page_urls = [row[0] for row in rows if row]
        all_urls.extend(page_urls)
        page += 1

        logger.info("[cdx] domain=%s: page %s got %s urls (total %s so far)", domain, page, len(page_urls), len(all_urls))

        if not next_resume_key:
            break
        resume_key = next_resume_key

    logger.info("[cdx] domain=%s: done, %s total urls across %s pages", domain, len(all_urls), page)
    return all_urls


def _get_with_backoff(params: dict) -> list | None:
    for attempt in range(_MAX_RETRIES):
        try:
            response = requests.get(CDX_BASE_URL, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as error:
            logger.warning("Wayback CDX request failed (attempt %s): %s", attempt + 1, error)
            time.sleep(_BASE_BACKOFF_SECONDS * (2**attempt))
            continue

        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                logger.warning("Wayback CDX returned non-JSON body for domain=%s", params.get("url"))
                return None

        if response.status_code in (429, 503):
            logger.warning(
                "Wayback CDX rate-limited (status=%s) for domain=%s, backing off",
                response.status_code, params.get("url"),
            )
            time.sleep(_BASE_BACKOFF_SECONDS * (2**attempt))
            continue

        logger.error("Wayback CDX request failed: status=%s domain=%s", response.status_code, params.get("url"))
        return None

    return None