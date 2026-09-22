import re

import requests

from core.discovery.ats.base import BaseATSExtractor
from core.parsing.html_to_text import html_to_text

_URL_RE = re.compile(r"([a-z0-9-]+)\.recruitee\.com/o/([^/?#]+)")


class RecruiteeExtractor(BaseATSExtractor):
    name = "recruitee"
    site_filter_domains = ["recruitee.com"]
    url_pattern = _URL_RE

    def extract(self, url: str) -> str | None:
        match = _URL_RE.search(url)
        if not match:
            return None
        slug, offer_slug = match.groups()

        api_url = f"https://{slug}.recruitee.com/api/offers/{offer_slug}"
        response = requests.get(api_url, timeout=20)
        if response.status_code != 200:
            return None

        data = response.json()
        offer = data.get("offer", data) if isinstance(data, dict) else None
        if not offer:
            return None

        title = offer.get("title", "")

        arrangement = None
        if offer.get("remote"):
            arrangement = "remote"
        elif offer.get("hybrid"):
            arrangement = "hybrid"
        elif offer.get("on_site"):
            arrangement = "on-site"

        header_parts = [
            offer.get("department"),
            offer.get("city"),
            offer.get("country_code"),
            offer.get("employment_type_code"),
            arrangement,
        ]
        header_line = " / ".join(part for part in header_parts if part)

        description = html_to_text(offer.get("description", ""))
        requirements = html_to_text(offer.get("requirements", ""))

        return "\n\n".join(part for part in [title, header_line, description, requirements] if part)