import logging
import re

import requests

from core.parsing.html_to_text import html_to_text

logger = logging.getLogger(__name__)

_GREENHOUSE_URL_RE = re.compile(r"(?:boards|job-boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)")
_LEVER_URL_RE = re.compile(r"jobs\.lever\.co/([^/]+)/([^/?#]+)")
_ASHBY_URL_RE = re.compile(r"jobs\.ashbyhq\.com/([^/]+)/([^/?#]+)")
_WORKABLE_URL_RE = re.compile(r"apply\.workable\.com/([^/]+)/j/([^/?#]+)")
_SMARTRECRUITERS_URL_RE = re.compile(r"(?:careers|jobs)\.smartrecruiters\.com/([^/]+)/(\d+)")


def detect_platform(url: str) -> str | None:
    if _GREENHOUSE_URL_RE.search(url):
        return "greenhouse"
    if _LEVER_URL_RE.search(url):
        return "lever"
    if _ASHBY_URL_RE.search(url):
        return "ashby"
    if _WORKABLE_URL_RE.search(url):
        return "workable"
    if _SMARTRECRUITERS_URL_RE.search(url):
        return "smartrecruiters"
    return None


def _extract_greenhouse(url: str) -> str | None:
    match = _GREENHOUSE_URL_RE.search(url)
    if not match:
        return None
    board_token, job_id = match.groups()

    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}"
    response = requests.get(api_url, params={"content": "true"}, timeout=20)
    if response.status_code != 200:
        return None

    data = response.json()
    title = data.get("title", "")
    location = (data.get("location") or {}).get("name", "")
    body_text = html_to_text(data.get("content", ""))

    return "\n\n".join(part for part in [title, location, body_text] if part)


def _extract_lever(url: str) -> str | None:
    match = _LEVER_URL_RE.search(url)
    if not match:
        return None
    site_slug, posting_id = match.groups()

    api_url = f"https://api.lever.co/v0/postings/{site_slug}/{posting_id}"
    response = requests.get(api_url, params={"mode": "json"}, timeout=20)
    if response.status_code != 200:
        return None

    data = response.json()
    title = data.get("text", "")

    categories = data.get("categories") or {}
    workplace_type = data.get("workplaceType") or categories.get("workplaceType")
    header_parts = [
        categories.get("location"),
        categories.get("team") or categories.get("department"),
        categories.get("commitment"),
        workplace_type,
    ]
    header_line = " / ".join(part for part in header_parts if part)

    description = data.get("descriptionPlain") or html_to_text(data.get("description", ""))

    lists_text = []
    for section in data.get("lists") or []:
        section_title = section.get("text", "")
        section_body = html_to_text(section.get("content", ""))
        section_combined = "\n".join(part for part in [section_title, section_body] if part)
        if section_combined:
            lists_text.append(section_combined)

    additional = data.get("additionalPlain") or html_to_text(data.get("additional", ""))

    parts = [title, header_line, description, *lists_text, additional]
    return "\n\n".join(part for part in parts if part)


def _extract_ashby(url: str) -> str | None:
    match = _ASHBY_URL_RE.search(url)
    if not match:
        return None
    org_slug, job_slug = match.groups()

    api_url = f"https://api.ashbyhq.com/posting-api/job-board/{org_slug}"
    response = requests.get(api_url, params={"includeCompensation": "false"}, timeout=20)
    if response.status_code != 200:
        return None

    data = response.json()
    postings = data.get("jobPostings") or []

    matching = next(
        (
            posting
            for posting in postings
            if posting.get("id") == job_slug or str(posting.get("jobUrl", "")).endswith(job_slug)
        ),
        None,
    )
    if matching is None:
        return None

    title = matching.get("title", "")
    location = matching.get("locationName") or matching.get("location", "")
    description = matching.get("descriptionPlain") or html_to_text(matching.get("descriptionHtml", ""))

    return "\n\n".join(part for part in [title, location, description] if part)


def _extract_workable(url: str) -> str | None:
    match = _WORKABLE_URL_RE.search(url)
    if not match:
        return None
    account_slug, shortcode = match.groups()

    api_url = f"https://apply.workable.com/api/v1/widget/accounts/{account_slug}"
    response = requests.get(api_url, params={"details": "true"}, timeout=20)
    if response.status_code != 200:
        return None

    data = response.json()
    jobs = data.get("jobs") or []

    matching = next(
        (
            job
            for job in jobs
            if job.get("shortcode") == shortcode or str(job.get("id")) == shortcode
        ),
        None,
    )
    if matching is None:
        return None

    title = matching.get("title", "")
    location = matching.get("location") or {}
    location_str = location.get("location_str") or ", ".join(
        part for part in [location.get("city"), location.get("country")] if part
    )

    body_text = "\n\n".join(
        html_to_text(part)
        for part in [
            matching.get("description", ""),
            matching.get("full_description", ""),
            matching.get("requirements", ""),
            matching.get("benefits", ""),
        ]
        if part
    )

    return "\n\n".join(part for part in [title, location_str, body_text] if part)


def _extract_smartrecruiters(url: str) -> str | None:
    match = _SMARTRECRUITERS_URL_RE.search(url)
    if not match:
        return None
    company_id, posting_id = match.groups()

    api_url = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings/{posting_id}"
    response = requests.get(api_url, timeout=20)
    if response.status_code != 200:
        return None

    data = response.json()
    title = data.get("name", "")

    location = data.get("location") or {}
    location_str = ", ".join(
        part for part in [location.get("city"), location.get("region"), location.get("country")] if part
    )

    sections = (data.get("jobAd") or {}).get("sections") or {}
    body_parts = []
    for section in sections.values():
        if isinstance(section, dict):
            text = html_to_text(section.get("text", ""))
            if text:
                body_parts.append(text)
    body_text = "\n\n".join(body_parts)

    return "\n\n".join(part for part in [title, location_str, body_text] if part)


_EXTRACTORS = {
    "greenhouse": _extract_greenhouse,
    "lever": _extract_lever,
    "ashby": _extract_ashby,
    "workable": _extract_workable,
    "smartrecruiters": _extract_smartrecruiters,
}


def extract_job_text(url: str) -> str | None:
    platform = detect_platform(url)
    if platform is None:
        logger.warning("extract_job_text: no ATS extractor for url=%s (unsupported platform)", url)
        return None

    extractor = _EXTRACTORS[platform]
    try:
        result = extractor(url)
        if result is None:
            logger.warning("extract_job_text: %s extractor returned None for url=%s (non-200 or no matching posting)", platform, url)
        else:
            logger.info("extract_job_text: %s extractor got %s chars for url=%s", platform, len(result), url)
        return result
    except requests.RequestException as error:
        logger.error("extract_job_text: network error for url=%s: %s", url, error)
        return None
    except (ValueError, KeyError, TypeError) as error:
        logger.error("extract_job_text: parse error for url=%s: %s", url, error)
        return None