import re

import requests

from core.discovery.ats.base import BaseATSExtractor
from core.parsing.html_to_text import html_to_text

_URL_RE = re.compile(r"jobs\.ashbyhq\.com/([^/]+)/([^/?#]+)")


class AshbyExtractor(BaseATSExtractor):
    name = "ashby"
    site_filter_domains = ["jobs.ashbyhq.com"]
    url_pattern = _URL_RE

    def extract(self, url: str) -> str | None:
        match = _URL_RE.search(url)
        if not match:
            return None
        org_slug, job_slug = match.groups()

        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{org_slug}"
        response = requests.get(api_url, params={"includeCompensation": "false"}, timeout=20)
        if response.status_code != 200:
            return None

        data = response.json()
        postings = data.get("jobs") or []

        matching = next(
            (
                posting
                for posting in postings
                if posting.get("id") == job_slug
                or str(posting.get("jobUrl", "")).rstrip("/").endswith(job_slug)
            ),
            None,
        )
        if matching is None:
            return None

        title = matching.get("title", "")

        header_parts = [
            matching.get("location"),
            matching.get("department"),
            matching.get("team"),
            matching.get("employmentType"),
            matching.get("workplaceType"),
        ]
        header_line = " / ".join(part for part in header_parts if part)

        description = matching.get("descriptionPlain") or html_to_text(matching.get("descriptionHtml", ""))

        return "\n\n".join(part for part in [title, header_line, description] if part)