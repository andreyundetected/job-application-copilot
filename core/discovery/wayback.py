import logging
import time

import requests

logger = logging.getLogger(__name__)

CDX_BASE_URL = "http://web.archive.org/cdx/search/cdx"
_PAGE_LIMIT = 100000
_MAX_RETRIES = 3
_BASE_BACKOFF_SECONDS = 2
_REQUEST_TIMEOUT_SECONDS = 30


def fetch_cdx_urls(domain: str) -> list[str]:
    params = {
        "url": domain,
        "matchType": "domain",
        "collapse": "urlkey",
        "output": "json",
        "filter": "statuscode:200",
        "fl": "original",
        "limit": _PAGE_LIMIT,
    }

    data = _get_with_backoff(params)
    if not data:
        return []

    rows = data[1:] if data[0] == ["original"] else data
    return [row[0] for row in rows if row]


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