import re

import requests

from core.discovery.ats.base import BaseATSExtractor
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