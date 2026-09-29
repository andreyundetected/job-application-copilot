import pytest
import requests

from core.discovery import ats
from core.discovery.ats.greenhouse import GreenhouseExtractor
from core.discovery.ats.workable import WorkableExtractor


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}

    def json(self):
        return self._json_data


@pytest.mark.discovery
def test_greenhouse_extract_unescapes_html_content(monkeypatch):
    payload = {
        "title": "Sample Engineer",
        "location": {"name": "Berlin"},
        "content": "&lt;p&gt;Real description here.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Item one&lt;/li&gt;&lt;/ul&gt;",
    }
    monkeypatch.setattr(requests, "get", lambda url, params=None, timeout=None: _FakeResponse(200, payload))

    result = GreenhouseExtractor().extract("https://boards.greenhouse.io/examplecorp/jobs/123")

    assert "Real description here." in result
    assert "Item one" in result
    assert "<p>" not in result
    assert "&lt;" not in result


@pytest.mark.discovery
def test_greenhouse_list_builds_url_from_slug_and_id(monkeypatch):
    payload = {
        "jobs": [
            {"id": 555, "title": "Sample Role", "absolute_url": "https://careers.example.com/role?gh_jid=555"},
        ]
    }
    monkeypatch.setattr(requests, "get", lambda url, params=None, timeout=None: _FakeResponse(200, payload))

    postings = GreenhouseExtractor().list_active_postings("examplecorp")

    assert postings[0]["url"] == "https://job-boards.greenhouse.io/examplecorp/jobs/555"
    assert GreenhouseExtractor().matches(postings[0]["url"])


@pytest.mark.discovery
def test_workable_extract_uses_top_level_location_fields(monkeypatch):
    payload = {
        "jobs": [
            {
                "shortcode": "ABC123",
                "title": "Sample Engineer",
                "city": "Berlin",
                "state": "Berlin",
                "country": "Germany",
                "telecommuting": True,
                "employment_type": "Full-time",
                "department": "Engineering",
                "description": "<p>Sample description.</p>",
            }
        ]
    }
    monkeypatch.setattr(requests, "get", lambda url, params=None, timeout=None: _FakeResponse(200, payload))

    result = WorkableExtractor().extract("https://apply.workable.com/examplecorp/j/ABC123")

    assert "Berlin" in result
    assert "Germany" in result
    assert "remote" in result
    assert "Sample description." in result


@pytest.mark.discovery
def test_workable_extract_without_location_fields_still_works(monkeypatch):
    payload = {"jobs": [{"shortcode": "ABC123", "title": "Sample Engineer", "description": "<p>Sample description.</p>"}]}
    monkeypatch.setattr(requests, "get", lambda url, params=None, timeout=None: _FakeResponse(200, payload))

    result = WorkableExtractor().extract("https://apply.workable.com/examplecorp/j/ABC123")

    assert "Sample Engineer" in result
    assert "Sample description." in result


@pytest.mark.discovery
def test_is_usable_job_text_thresholds():
    assert ats.is_usable_job_text(None) is False
    assert ats.is_usable_job_text("   ") is False
    assert ats.is_usable_job_text("short header only") is False
    assert ats.is_usable_job_text("x" * ats.MIN_JOB_TEXT_CHARS) is True