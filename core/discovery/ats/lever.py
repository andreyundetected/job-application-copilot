import re

import requests

from core.discovery.ats.base import BaseATSExtractor, parse_iso_datetime
from core.parsing.html_to_text import html_to_text

_URL_RE = re.compile(r"jobs\.lever\.co/([^/]+)/([^/?#]+)")


class LeverExtractor(BaseATSExtractor):
    name = "lever"
    site_filter_domains = ["jobs.lever.co"]
    url_pattern = _URL_RE

    def extract(self, url: str) -> str | None:
        match = _URL_RE.search(url)
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

    def list_active_postings(self, slug: str) -> list[dict] | None:
        api_url = f"https://api.lever.co/v0/postings/{slug}"
        response = requests.get(api_url, params={"mode": "json"}, timeout=20)
        if response.status_code in (404, 410):
            return None
        if response.status_code != 200:
            return []

        postings = response.json()
        if not isinstance(postings, list):
            return []

        results = []
        for posting in postings:
            posting_id = posting.get("id")
            url = posting.get("hostedUrl", "")
            if not posting_id or not url:
                continue
            posted_at = parse_iso_datetime(posting.get("createdAt"))
            results.append(
                {"external_id": str(posting_id), "url": url, "title": posting.get("text", ""), "posted_at": posted_at}
            )
        return results