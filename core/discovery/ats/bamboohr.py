import re

import requests

from core.discovery.ats.base import BaseATSExtractor, parse_iso_datetime
from core.parsing.html_to_text import html_to_text

_URL_RE = re.compile(r"([a-z0-9-]+)\.bamboohr\.com/careers/(\d+)")


class BambooHRExtractor(BaseATSExtractor):
    name = "bamboohr"
    site_filter_domains = ["bamboohr.com"]
    url_pattern = _URL_RE
    supports_posted_at_lookup = True

    def _fetch_opening(self, slug: str, job_id: str) -> dict | None:
        api_url = f"https://{slug}.bamboohr.com/careers/{job_id}/detail"
        response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=20)
        if response.status_code != 200:
            return None

        data = response.json()
        result = data.get("result", data) if isinstance(data, dict) else None
        if not isinstance(result, dict):
            return None

        opening = result.get("jobOpening")
        if isinstance(opening, dict):
            return opening
        return result

    def extract(self, url: str) -> str | None:
        match = _URL_RE.search(url)
        if not match:
            return None
        slug, job_id = match.groups()

        opening = self._fetch_opening(slug, job_id)
        if not opening:
            return None

        title = opening.get("jobOpeningName") or ""

        description = html_to_text(opening.get("description") or "")
        if not description.strip():
            return None

        location = opening.get("location")
        if not isinstance(location, dict):
            location = {}
        location_str = ", ".join(
            part for part in [location.get("city"), location.get("state"), location.get("addressCountry")] if part
        )

        header_parts = [
            opening.get("departmentLabel"),
            location_str,
            opening.get("employmentStatusLabel"),
        ]
        header_line = " / ".join(part for part in header_parts if part)

        return "\n\n".join(part for part in [title, header_line, description] if part)

    def fetch_posted_at(self, slug: str, external_id: str):
        opening = self._fetch_opening(slug, external_id)
        if not opening:
            return None
        return parse_iso_datetime(opening.get("datePosted"))

    def list_active_postings(self, slug: str) -> list[dict] | None:
        api_url = f"https://{slug}.bamboohr.com/careers/list"
        response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=20)
        if response.status_code in (404, 410):
            return None
        if response.status_code != 200:
            return []

        try:
            data = response.json()
        except ValueError:
            return []

        raw_list = data.get("result", data) if isinstance(data, dict) else data
        if not isinstance(raw_list, list):
            return []

        results = []
        for job in raw_list:
            job_id = job.get("id")
            if job_id is None:
                continue
            url = f"https://{slug}.bamboohr.com/careers/{job_id}"
            results.append(
                {
                    "external_id": str(job_id),
                    "url": url,
                    "title": job.get("jobOpeningName", ""),
                    "posted_at": None,
                }
            )
        return results