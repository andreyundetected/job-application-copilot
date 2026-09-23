import re

import requests

from core.discovery.ats.base import BaseATSExtractor, parse_iso_datetime
from core.parsing.html_to_text import html_to_text

_URL_RE = re.compile(r"([a-z0-9-]+)\.bamboohr\.com/careers/(\d+)")


class BambooHRExtractor(BaseATSExtractor):
    name = "bamboohr"
    site_filter_domains = ["bamboohr.com"]
    url_pattern = _URL_RE

    def extract(self, url: str) -> str | None:
        match = _URL_RE.search(url)
        if not match:
            return None
        slug, job_id = match.groups()

        api_url = f"https://{slug}.bamboohr.com/careers/{job_id}/detail"
        response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=20)
        if response.status_code != 200:
            return None

        data = response.json()
        result = data.get("result", data) if isinstance(data, dict) else None
        if not result:
            return None

        title = result.get("jobOpeningName", "")

        header_parts = [
            result.get("departmentLabel"),
            result.get("locationLabel") or result.get("location", {}).get("city"),
            result.get("employmentStatusLabel"),
        ]
        header_line = " / ".join(part for part in header_parts if part)

        description = html_to_text(result.get("description", ""))

        return "\n\n".join(part for part in [title, header_line, description] if part)

    def list_active_postings(self, slug: str) -> list[dict]:
        api_url = f"https://{slug}.bamboohr.com/careers/list"
        response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=20)
        if response.status_code != 200:
            return []

        data = response.json()
        raw_list = data.get("result", data) if isinstance(data, dict) else data
        if not isinstance(raw_list, list):
            return []

        results = []
        for job in raw_list:
            job_id = job.get("id")
            if job_id is None:
                continue
            url = f"https://{slug}.bamboohr.com/careers/{job_id}"
            posted_at = parse_iso_datetime(job.get("postingDate") or job.get("posted"))
            results.append(
                {
                    "external_id": str(job_id),
                    "url": url,
                    "title": job.get("jobOpeningName", ""),
                    "posted_at": posted_at,
                }
            )
        return results