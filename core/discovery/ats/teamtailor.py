import re

import requests

from core.discovery.ats.base import BaseATSExtractor
from core.parsing.html_to_text import html_to_text

_URL_RE = re.compile(r"([a-z0-9-]+)\.teamtailor\.com/jobs/(\d+)-([^/?#]+)")


class TeamtailorExtractor(BaseATSExtractor):
    name = "teamtailor"
    site_filter_domains = ["teamtailor.com"]
    url_pattern = _URL_RE

    def extract(self, url: str) -> str | None:
        match = _URL_RE.search(url)
        if not match:
            return None
        slug, job_id, _job_slug = match.groups()

        api_url = f"https://{slug}.teamtailor.com/api/v1/jobs/{job_id}"
        response = requests.get(api_url, headers={"Accept": "application/vnd.api+json"}, timeout=20)
        if response.status_code != 200:
            return None

        data = response.json()
        job = data.get("data") if isinstance(data, dict) else None
        if not job:
            return None

        attributes = job.get("attributes") or {}
        title = attributes.get("title", "")

        header_parts = [
            attributes.get("department-name") or attributes.get("department"),
            attributes.get("location") or attributes.get("city"),
            attributes.get("employment-type") or attributes.get("employment_type"),
            "remote" if attributes.get("remote-status") == "remote" else None,
        ]
        header_line = " / ".join(part for part in header_parts if part)

        body = attributes.get("body") or attributes.get("description") or ""
        description = html_to_text(body)

        return "\n\n".join(part for part in [title, header_line, description] if part)