import datetime

import pytest
import requests

from core.discovery.ats.base import parse_iso_datetime
from core.discovery.ats.recruitee import RecruiteeExtractor


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}

    def json(self):
        return self._json_data


@pytest.mark.discovery
def test_parse_iso_datetime_accepts_utc_suffix():
    assert parse_iso_datetime("2026-09-04 14:05:49 UTC") == datetime.datetime(2026, 9, 4, 14, 5, 49)


@pytest.mark.discovery
def test_parse_iso_datetime_still_accepts_iso_with_offset():
    assert parse_iso_datetime("2026-08-04T22:56:45+00:00") == datetime.datetime(2026, 8, 4, 22, 56, 45)


@pytest.mark.discovery
def test_recruitee_list_prefers_published_at_over_created_at(monkeypatch):
    payload = {
        "offers": [
            {
                "id": 1,
                "slug": "sample-role",
                "title": "Sample Role",
                "created_at": "2026-09-04 09:45:10 UTC",
                "published_at": "2026-09-04 14:05:49 UTC",
            }
        ]
    }
    monkeypatch.setattr(requests, "get", lambda url, timeout=None: _FakeResponse(200, payload))

    postings = RecruiteeExtractor().list_active_postings("examplecorp")

    assert postings[0]["posted_at"] == datetime.datetime(2026, 9, 4, 14, 5, 49)


@pytest.mark.discovery
def test_recruitee_list_falls_back_to_created_at(monkeypatch):
    payload = {
        "offers": [
            {"id": 1, "slug": "sample-role", "title": "Sample Role", "created_at": "2026-09-04 09:45:10 UTC"}
        ]
    }
    monkeypatch.setattr(requests, "get", lambda url, timeout=None: _FakeResponse(200, payload))

    postings = RecruiteeExtractor().list_active_postings("examplecorp")

    assert postings[0]["posted_at"] == datetime.datetime(2026, 9, 4, 9, 45, 10)