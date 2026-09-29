import datetime

import pytest
import requests

from core.discovery import ats
from core.discovery.ats.bamboohr import BambooHRExtractor


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}

    def json(self):
        return self._json_data


def _detail_payload(description="<p>Sample job description.</p>", date_posted="2026-07-15"):
    return {
        "meta": {},
        "result": {
            "jobOpening": {
                "jobOpeningName": "Sample Backend Engineer",
                "departmentLabel": "Engineering",
                "employmentStatusLabel": "Full-Time",
                "location": {"city": "Berlin", "state": None, "addressCountry": "Germany"},
                "description": description,
                "datePosted": date_posted,
            },
            "formFields": {},
        },
    }


@pytest.mark.discovery
def test_extract_reads_nested_job_opening(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, headers=None, timeout=None: _FakeResponse(200, _detail_payload()))

    result = BambooHRExtractor().extract("https://examplecorp.bamboohr.com/careers/42")

    assert "Sample Backend Engineer" in result
    assert "Engineering" in result
    assert "Berlin" in result
    assert "Germany" in result
    assert "Sample job description." in result


@pytest.mark.discovery
def test_extract_returns_none_when_description_is_blank(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda url, headers=None, timeout=None: _FakeResponse(200, _detail_payload(description=""))
    )

    assert BambooHRExtractor().extract("https://examplecorp.bamboohr.com/careers/42") is None


@pytest.mark.discovery
def test_fetch_posted_at_parses_date_posted(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, headers=None, timeout=None: _FakeResponse(200, _detail_payload()))

    result = BambooHRExtractor().fetch_posted_at("examplecorp", "42")

    assert result == datetime.datetime(2026, 7, 15)


@pytest.mark.discovery
def test_fetch_posted_at_returns_none_on_non_200(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, headers=None, timeout=None: _FakeResponse(404))

    assert BambooHRExtractor().fetch_posted_at("examplecorp", "42") is None


@pytest.mark.discovery
def test_fetch_posted_at_returns_none_when_date_missing(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda url, headers=None, timeout=None: _FakeResponse(200, _detail_payload(date_posted=None))
    )

    assert BambooHRExtractor().fetch_posted_at("examplecorp", "42") is None


@pytest.mark.discovery
def test_blank_extractor_result_is_treated_as_failure(monkeypatch):
    monkeypatch.setattr(ats._REGISTRY["bamboohr"], "extract", lambda url: "   ")

    assert ats.extract_job_text_with_extractor("bamboohr", "https://examplecorp.bamboohr.com/careers/42") is None


@pytest.mark.discovery
def test_only_bamboohr_supports_posted_at_lookup():
    supporting = {extractor.name for extractor in ats.all_extractors() if extractor.supports_posted_at_lookup}

    assert supporting == {"bamboohr"}