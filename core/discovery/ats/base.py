import re
from abc import ABC, abstractmethod


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