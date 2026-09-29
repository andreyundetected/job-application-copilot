import pytest
import requests

from core.discovery import ats
from core.discovery.ats.lever import LeverExtractor
from core.discovery.ats.lever_eu import LeverEUExtractor

_UUID = "ca05955d-d75f-455e-ae06-0123456789ab"


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}

    def json(self):
        return self._json_data


@pytest.mark.discovery
def test_eu_url_is_detected_as_lever_eu_only():
    url = f"https://jobs.eu.lever.co/examplecorp/{_UUID}"

    assert ats.detect_platform(url) == "lever_eu"
    assert not LeverExtractor().matches(url)


@pytest.mark.discovery
def test_regular_lever_url_is_not_detected_as_eu():
    assert ats.detect_platform("https://jobs.lever.co/examplecorp/abc") == "lever"
    assert not LeverEUExtractor().matches("https://jobs.lever.co/examplecorp/abc")


@pytest.mark.discovery
def test_eu_pattern_ignores_service_paths():
    extractor = LeverEUExtractor()

    assert not extractor.matches("https://jobs.eu.lever.co/.well-known/security.txt")
    assert not extractor.matches("https://jobs.eu.lever.co/.well-known/ai-plugin.json")
    assert not extractor.matches("https://jobs.eu.lever.co/")


@pytest.mark.discovery
def test_eu_slug_extracted_from_wayback_url():
    extractor = LeverEUExtractor()
    match = extractor.url_pattern.search(f"https://jobs.eu.lever.co/examplecorp/{_UUID}")

    assert extractor._slug_from_match(match) == "examplecorp"


@pytest.mark.discovery
def test_eu_extract_uses_eu_api_host(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        return _FakeResponse(200, {"text": "Sample Role", "descriptionPlain": "Sample description."})

    monkeypatch.setattr(requests, "get", fake_get)

    result = LeverEUExtractor().extract(f"https://jobs.eu.lever.co/examplecorp/{_UUID}")

    assert calls == [f"https://api.eu.lever.co/v0/postings/examplecorp/{_UUID}"]
    assert "Sample Role" in result


@pytest.mark.discovery
def test_eu_list_uses_eu_api_host(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        return _FakeResponse(200, [])

    monkeypatch.setattr(requests, "get", fake_get)

    LeverEUExtractor().list_active_postings("examplecorp")

    assert calls == ["https://api.eu.lever.co/v0/postings/examplecorp"]


@pytest.mark.discovery
def test_regular_lever_still_uses_main_api_host(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        return _FakeResponse(200, [])

    monkeypatch.setattr(requests, "get", fake_get)

    LeverExtractor().list_active_postings("examplecorp")

    assert calls == ["https://api.lever.co/v0/postings/examplecorp"]