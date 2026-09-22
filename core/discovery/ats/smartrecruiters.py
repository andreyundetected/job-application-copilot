import re

import requests

from core.discovery.ats.base import BaseATSExtractor
from core.parsing.html_to_text import html_to_text

_URL_RE = re.compile(r"(?:careers|jobs)\.smartrecruiters\.com/([^/]+)/(\d+)")


class SmartRecruitersExtractor(BaseATSExtractor):
    name = "smartrecruiters"
    site_filter_domains = ["careers.smartrecruiters.com"]
    url_pattern = _URL_RE

    def extract(self, url: str) -> str | None:
        match = _URL_RE.search(url)
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