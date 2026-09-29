import re

from core.discovery.ats.lever import LeverExtractor

_URL_RE = re.compile(
    r"jobs\.eu\.lever\.co/([a-zA-Z0-9][^/?#]*)/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)


class LeverEUExtractor(LeverExtractor):
    name = "lever_eu"
    site_filter_domains = ["jobs.eu.lever.co"]
    url_pattern = _URL_RE
    api_base = "https://api.eu.lever.co/v0/postings"