import datetime as _dt
import re
from abc import ABC, abstractmethod

from core.discovery.wayback import fetch_cdx_urls


def parse_iso_datetime(value) -> "_dt.datetime | None":
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            if value > 10**12:
                value = value / 1000
            return _dt.datetime.utcfromtimestamp(value)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return parse_iso_datetime(int(text))
        try:
            return _dt.datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


class BaseATSExtractor(ABC):
    """One subclass per ATS platform. To add a new ATS: create a new file in
    this package, subclass this, fill in the four attributes/methods below -
    nothing else needs to change anywhere in the codebase. The registry in
    __init__.py auto-discovers every subclass in every file in this folder."""

    #: short machine name, e.g. "greenhouse" - used as the dict key everywhere
    name: str

    #: domains to pass to Google's site: filter when building search queries,
    #: e.g. ["boards.greenhouse.io"]. Several entries if the ATS uses more
    #: than one public domain (e.g. Personio's .de and .com).
    site_filter_domains: list[str]

    #: compiled regex that matches a single job posting URL on this platform
    #: and captures whatever identifiers extract() needs (board token, job id...)
    url_pattern: re.Pattern

    def matches(self, url: str) -> bool:
        return bool(self.url_pattern.search(url))

    @abstractmethod
    def extract(self, url: str) -> str | None:
        """Fetch and return the plain-text job posting for this URL, or None
        if the posting is gone/unreachable. Never raises for expected failure
        modes (404, empty board) - only lets real bugs (bad JSON shape) bubble
        up as ValueError/KeyError/TypeError, which the caller logs and swallows."""
        raise NotImplementedError

    def _slug_from_match(self, match: re.Match) -> str:
        return match.group(1)

    def list_wayback_slugs(self, is_cancelled=None) -> list[str]:
        slugs: set[str] = set()
        for domain in self.site_filter_domains:
            if is_cancelled is not None and is_cancelled():
                break
            for url in fetch_cdx_urls(domain, is_cancelled=is_cancelled):
                match = self.url_pattern.search(url)
                if match:
                    slugs.add(self._slug_from_match(match))
        return sorted(slugs)

    @abstractmethod
    def list_active_postings(self, slug: str) -> list[dict] | None:
        raise NotImplementedError