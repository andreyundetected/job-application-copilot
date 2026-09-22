import re

import requests

from core.discovery.ats.base import BaseATSExtractor
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