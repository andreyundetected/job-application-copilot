import re

import requests

from core.discovery.ats.base import BaseATSExtractor, parse_iso_datetime
from core.parsing.html_to_text import html_to_text

_URL_RE = re.compile(r"(?:boards|job-boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)")


class GreenhouseExtractor(BaseATSExtractor):
    name = "greenhouse"
    site_filter_domains = ["boards.greenhouse.io"]
    url_pattern = _URL_RE

    def extract(self, url: str) -> str | None:
        match = _URL_RE.search(url)
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

    def list_active_postings(self, slug: str) -> list[dict] | None:
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        response = requests.get(api_url, params={"content": "false"}, timeout=20)
        if response.status_code in (404, 410):
            return None
        if response.status_code != 200:
            return []

        data = response.json()
        jobs = data.get("jobs") or []

        results = []
        for job in jobs:
            job_id = job.get("id")
            url = job.get("absolute_url", "")
            if not job_id or not url:
                continue
            posted_at = parse_iso_datetime(job.get("updated_at"))
            results.append(
                {"external_id": str(job_id), "url": url, "title": job.get("title", ""), "posted_at": posted_at}
            )
        return results