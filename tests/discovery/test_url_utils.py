import pytest

from core.discovery.url_utils import normalize_url


@pytest.mark.discovery
def test_normalize_url_strips_scheme_and_www():
    assert normalize_url("https://www.example.com/jobs/1") == "example.com/jobs/1"


@pytest.mark.discovery
def test_normalize_url_strips_trailing_slash():
    assert normalize_url("https://example.com/jobs/1/") == "example.com/jobs/1"


@pytest.mark.discovery
def test_normalize_url_strips_query_string():
    assert normalize_url("https://example.com/jobs/1?utm_source=x") == "example.com/jobs/1"


@pytest.mark.discovery
def test_normalize_url_lowercases_host():
    assert normalize_url("https://Example.COM/jobs/1") == "example.com/jobs/1"


@pytest.mark.discovery
def test_normalize_url_without_www_unaffected():
    assert (
        normalize_url("https://boards.greenhouse.io/example/jobs/123")
        == "boards.greenhouse.io/example/jobs/123"
    )