import re

import requests

from core.parsing.html_to_text import html_to_text

_GREENHOUSE_URL_RE = re.compile(r"(?:boards|job-boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)")
_LEVER_URL_RE = re.compile(r"jobs\.lever\.co/([^/]+)/([^/?#]+)")
_ASHBY_URL_RE = re.compile(r"jobs\.ashbyhq\.com/([^/]+)/([^/?#]+)")


def detect_platform(url: str) -> str | None:
    if _GREENHOUSE_URL_RE.search(url):
        return "greenhouse"
    if _LEVER_URL_RE.search(url):
        return "lever"
    if _ASHBY_URL_RE.search(url):
        return "ashby"
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
    description = data.get("descriptionPlain") or html_to_text(data.get("description", ""))

    lists_text = []
    for section in data.get("lists") or []:
        section_title = section.get("text", "")
        section_body = html_to_text(section.get("content", ""))
        section_combined = "\n".join(part for part in [section_title, section_body] if part)
        if section_combined:
            lists_text.append(section_combined)

    additional = data.get("additionalPlain") or html_to_text(data.get("additional", ""))

    parts = [title, description, *lists_text, additional]
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


_EXTRACTORS = {
    "greenhouse": _extract_greenhouse,
    "lever": _extract_lever,
    "ashby": _extract_ashby,
}


def extract_job_text(url: str) -> str | None:
    platform = detect_platform(url)
    if platform is None:
        return None

    extractor = _EXTRACTORS[platform]
    try:
        return extractor(url)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None