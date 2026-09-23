import re
import xml.etree.ElementTree as ET

import requests

from core.discovery.ats.base import BaseATSExtractor, parse_iso_datetime
from core.parsing.html_to_text import html_to_text

_URL_RE = re.compile(r"([a-z0-9-]+)\.jobs\.personio\.(de|com)/job/(\d+)")


class PersonioExtractor(BaseATSExtractor):
    name = "personio"
    site_filter_domains = ["jobs.personio.de", "jobs.personio.com"]
    url_pattern = _URL_RE

    def extract(self, url: str) -> str | None:
        match = _URL_RE.search(url)
        if not match:
            return None
        subdomain, tld, job_id = match.groups()

        xml_url = f"https://{subdomain}.jobs.personio.{tld}/xml"

        def _fetch(params: dict):
            response = requests.get(xml_url, params=params, timeout=20)
            if response.status_code != 200:
                return None
            try:
                return ET.fromstring(response.content)
            except ET.ParseError:
                return None

        root = _fetch({"language": "en"})
        positions = root.findall("position") if root is not None else []

        if not positions:
            root = _fetch({})
            positions = root.findall("position") if root is not None else []

        if not positions:
            return None

        position = next((p for p in positions if (p.findtext("id") or "").strip() == job_id), None)
        if position is None:
            return None

        title = position.findtext("name") or ""

        header_parts = [
            position.findtext("office"),
            position.findtext("department"),
            position.findtext("employmentType"),
            position.findtext("seniority"),
            position.findtext("schedule"),
        ]
        header_line = " / ".join(part.strip() for part in header_parts if part and part.strip())

        description_parts = []
        for job_description in position.findall("./jobDescriptions/jobDescription"):
            section_name = (job_description.findtext("name") or "").strip()
            section_value = html_to_text(job_description.findtext("value") or "")
            section_combined = "\n".join(part for part in [section_name, section_value] if part)
            if section_combined:
                description_parts.append(section_combined)

        return "\n\n".join(part for part in [title, header_line, *description_parts] if part)

    def _slug_from_match(self, match) -> str:
        return f"{match.group(1)}.{match.group(2)}"

    def list_active_postings(self, slug: str) -> list[dict]:
        import xml.etree.ElementTree as ET

        if "." not in slug:
            return []
        subdomain, tld = slug.rsplit(".", 1)
        xml_url = f"https://{subdomain}.jobs.personio.{tld}/xml"

        def _fetch(params: dict):
            response = requests.get(xml_url, params=params, timeout=20)
            if response.status_code != 200:
                return None
            try:
                return ET.fromstring(response.content)
            except ET.ParseError:
                return None

        root = _fetch({"language": "en"})
        positions = root.findall("position") if root is not None else []
        if not positions:
            root = _fetch({})
            positions = root.findall("position") if root is not None else []

        results = []
        for position in positions:
            job_id = (position.findtext("id") or "").strip()
            if not job_id:
                continue
            url = f"https://{subdomain}.jobs.personio.{tld}/job/{job_id}"
            posted_at = parse_iso_datetime(position.findtext("createDate") or position.findtext("createdAt"))
            results.append(
                {"external_id": job_id, "url": url, "title": position.findtext("name") or "", "posted_at": posted_at}
            )
        return results