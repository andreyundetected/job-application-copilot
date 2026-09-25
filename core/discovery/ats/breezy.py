import re

import requests

from core.discovery.ats.base import BaseATSExtractor, parse_iso_datetime
from core.parsing.html_to_text import html_to_text

_URL_RE = re.compile(r"([a-z0-9-]+)\.breezy\.hr/p/([^/?#]+)")


class BreezyExtractor(BaseATSExtractor):
    name = "breezy"
    site_filter_domains = ["breezy.hr"]
    url_pattern = _URL_RE

    def extract(self, url: str) -> str | None:
        match = _URL_RE.search(url)
        if not match:
            return None
        slug, position_slug = match.groups()

        list_url = f"https://{slug}.breezy.hr/json"
        response = requests.get(list_url, params={"verbose": "true"}, timeout=20)
        if response.status_code != 200:
            return None

        jobs = response.json()
        if not isinstance(jobs, list):
            return None

        normalized_target = url.split("?")[0].rstrip("/")

        matching = next(
            (job for job in jobs if (job.get("url") or "").split("?")[0].rstrip("/") == normalized_target),
            None,
        )
        if matching is None:
            matching = next(
                (job for job in jobs if str(job.get("id", "")) and str(job.get("id")) in position_slug),
                None,
            )

        if matching is None:
            return None

        title = matching.get("name", "")

        location = matching.get("location") or {}
        header_parts = [
            matching.get("department"),
            location.get("name"),
            "remote" if location.get("is_remote") else None,
            (matching.get("type") or {}).get("name"),
        ]
        header_line = " / ".join(part for part in header_parts if part)

        description = html_to_text(matching.get("description", ""))

        return "\n\n".join(part for part in [title, header_line, description] if part)

    def list_active_postings(self, slug: str) -> list[dict] | None:
        list_url = f"https://{slug}.breezy.hr/json"
        response = requests.get(list_url, params={"verbose": "true"}, timeout=20)
        if response.status_code in (404, 410):
            return None
        if response.status_code != 200:
            return []

        jobs = response.json()
        if not isinstance(jobs, list):
            return []

        results = []
        for job in jobs:
            job_id = job.get("id")
            url = job.get("url", "")
            if not job_id or not url:
                continue
            posted_at = parse_iso_datetime(job.get("published_date") or job.get("created_date"))
            results.append(
                {"external_id": str(job_id), "url": url, "title": job.get("name", ""), "posted_at": posted_at}
            )
        return results