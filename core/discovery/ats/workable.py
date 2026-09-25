import re

import requests

from core.discovery.ats.base import BaseATSExtractor, parse_iso_datetime
from core.parsing.html_to_text import html_to_text

_URL_RE = re.compile(r"apply\.workable\.com/([^/]+)/j/([^/?#]+)")


class WorkableExtractor(BaseATSExtractor):
    name = "workable"
    site_filter_domains = ["apply.workable.com"]
    url_pattern = _URL_RE

    def extract(self, url: str) -> str | None:
        match = _URL_RE.search(url)
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

    def list_active_postings(self, slug: str) -> list[dict] | None:
        api_url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
        response = requests.get(api_url, params={"details": "false"}, timeout=20)
        if response.status_code in (404, 410):
            return None
        if response.status_code != 200:
            return []

        data = response.json()
        jobs = data.get("jobs") or []

        results = []
        for job in jobs:
            shortcode = job.get("shortcode")
            if not shortcode:
                continue
            url = f"https://apply.workable.com/{slug}/j/{shortcode}"
            posted_at = parse_iso_datetime(job.get("published_on") or job.get("created_at"))
            results.append(
                {"external_id": shortcode, "url": url, "title": job.get("title", ""), "posted_at": posted_at}
            )
        return results