import pytest
import requests

from core.discovery import ats


class _FakeResponse:
    def __init__(self, status_code, json_data=None, content=b""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.content = content

    def json(self):
        return self._json_data


@pytest.mark.discovery
def test_detect_platform_recruitee():
    assert ats.detect_platform("https://examplecorp.recruitee.com/o/senior-engineer") == "recruitee"


@pytest.mark.discovery
def test_detect_platform_personio_de():
    assert ats.detect_platform("https://examplecorp.jobs.personio.de/job/123456") == "personio"


@pytest.mark.discovery
def test_detect_platform_personio_com():
    assert ats.detect_platform("https://examplecorp.jobs.personio.com/job/123456") == "personio"


@pytest.mark.discovery
def test_detect_platform_breezy():
    assert ats.detect_platform("https://examplecorp.breezy.hr/p/abc123-senior-engineer") == "breezy"


@pytest.mark.discovery
def test_detect_platform_bamboohr():
    assert ats.detect_platform("https://examplecorp.bamboohr.com/careers/42") == "bamboohr"


@pytest.mark.discovery
def test_detect_platform_teamtailor():
    assert ats.detect_platform("https://examplecorp.teamtailor.com/jobs/123-senior-engineer") == "teamtailor"


@pytest.mark.discovery
def test_extract_job_text_recruitee(monkeypatch):
    url = "https://examplecorp.recruitee.com/o/senior-backend-engineer"

    def fake_get(api_url, timeout=None):
        assert api_url == "https://examplecorp.recruitee.com/api/offers/senior-backend-engineer"
        return _FakeResponse(
            200,
            {
                "offer": {
                    "title": "Sample Senior Backend Engineer",
                    "department": "Engineering",
                    "city": "Amsterdam",
                    "country_code": "NL",
                    "employment_type_code": "fulltime_permanent",
                    "remote": False,
                    "hybrid": True,
                    "on_site": False,
                    "description": "<p>Sample job description.</p>",
                    "requirements": "<p>Sample requirements.</p>",
                }
            },
        )

    monkeypatch.setattr(requests, "get", fake_get)

    result = ats.extract_job_text(url)

    assert "Sample Senior Backend Engineer" in result
    assert "Amsterdam" in result
    assert "Sample job description." in result
    assert "Sample requirements." in result


@pytest.mark.discovery
def test_extract_job_text_recruitee_non_200_returns_none(monkeypatch):
    url = "https://examplecorp.recruitee.com/o/senior-backend-engineer"

    def fake_get(api_url, timeout=None):
        return _FakeResponse(404)

    monkeypatch.setattr(requests, "get", fake_get)

    assert ats.extract_job_text(url) is None


@pytest.mark.discovery
def test_extract_job_text_recruitee_derives_arrangement_label(monkeypatch):
    url = "https://examplecorp.recruitee.com/o/senior-backend-engineer"

    def fake_get(api_url, timeout=None):
        return _FakeResponse(
            200,
            {"offer": {"title": "Sample Role", "remote": True, "hybrid": False, "on_site": False}},
        )

    monkeypatch.setattr(requests, "get", fake_get)

    result = ats.extract_job_text(url)

    assert "remote" in result


_PERSONIO_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs>
<position>
<id>123456</id>
<office>Munich</office>
<department>Engineering</department>
<name>Sample Backend Engineer</name>
<employmentType>permanent</employmentType>
<seniority>experienced</seniority>
<schedule>full-time</schedule>
<jobDescriptions>
<jobDescription>
<name>Your tasks</name>
<value><![CDATA[Sample job description text.]]></value>
</jobDescription>
</jobDescriptions>
</position>
</workzag-jobs>
"""


@pytest.mark.discovery
def test_extract_job_text_personio(monkeypatch):
    url = "https://examplecorp.jobs.personio.de/job/123456"

    def fake_get(xml_url, params=None, timeout=None):
        assert xml_url == "https://examplecorp.jobs.personio.de/xml"
        assert params == {"language": "en"}
        return _FakeResponse(200, content=_PERSONIO_XML)

    monkeypatch.setattr(requests, "get", fake_get)

    result = ats.extract_job_text(url)

    assert "Sample Backend Engineer" in result
    assert "Munich" in result
    assert "Sample job description text." in result


@pytest.mark.discovery
def test_extract_job_text_personio_falls_back_without_language(monkeypatch):
    url = "https://examplecorp.jobs.personio.de/job/123456"
    calls = []

    def fake_get(xml_url, params=None, timeout=None):
        calls.append(params)
        if params == {"language": "en"}:
            return _FakeResponse(200, content=b"<workzag-jobs></workzag-jobs>")
        return _FakeResponse(200, content=_PERSONIO_XML)

    monkeypatch.setattr(requests, "get", fake_get)

    result = ats.extract_job_text(url)

    assert calls == [{"language": "en"}, {}]
    assert "Sample Backend Engineer" in result


@pytest.mark.discovery
def test_extract_job_text_personio_job_not_found_returns_none(monkeypatch):
    url = "https://examplecorp.jobs.personio.de/job/999999"

    def fake_get(xml_url, params=None, timeout=None):
        return _FakeResponse(200, content=_PERSONIO_XML)

    monkeypatch.setattr(requests, "get", fake_get)

    assert ats.extract_job_text(url) is None


@pytest.mark.discovery
def test_extract_job_text_breezy(monkeypatch):
    url = "https://examplecorp.breezy.hr/p/abc123def456-senior-backend-engineer"

    def fake_get(list_url, params=None, timeout=None):
        assert list_url == "https://examplecorp.breezy.hr/json"
        assert params == {"verbose": "true"}
        return _FakeResponse(
            200,
            [
                {
                    "id": "abc123def456",
                    "name": "Sample Senior Backend Engineer",
                    "department": "Engineering",
                    "location": {"name": "Remote", "is_remote": True},
                    "type": {"name": "Full-Time"},
                    "description": "<p>Sample job description.</p>",
                    "url": "https://examplecorp.breezy.hr/p/abc123def456-senior-backend-engineer",
                }
            ],
        )

    monkeypatch.setattr(requests, "get", fake_get)

    result = ats.extract_job_text(url)

    assert "Sample Senior Backend Engineer" in result
    assert "Sample job description." in result
    assert "remote" in result


@pytest.mark.discovery
def test_extract_job_text_breezy_falls_back_to_id_match(monkeypatch):
    url = "https://examplecorp.breezy.hr/p/abc123def456-different-slug-text"

    def fake_get(list_url, params=None, timeout=None):
        return _FakeResponse(
            200,
            [
                {
                    "id": "abc123def456",
                    "name": "Sample Role",
                    "description": "Sample description.",
                    "url": "https://examplecorp.breezy.hr/p/abc123def456-original-slug",
                }
            ],
        )

    monkeypatch.setattr(requests, "get", fake_get)

    result = ats.extract_job_text(url)

    assert "Sample Role" in result


@pytest.mark.discovery
def test_extract_job_text_breezy_no_match_returns_none(monkeypatch):
    url = "https://examplecorp.breezy.hr/p/zzz999-missing-job"

    def fake_get(list_url, params=None, timeout=None):
        return _FakeResponse(200, [])

    monkeypatch.setattr(requests, "get", fake_get)

    assert ats.extract_job_text(url) is None


@pytest.mark.discovery
def test_extract_job_text_bamboohr(monkeypatch):
    url = "https://examplecorp.bamboohr.com/careers/42"

    def fake_get(api_url, headers=None, timeout=None):
        assert api_url == "https://examplecorp.bamboohr.com/careers/42/detail"
        return _FakeResponse(
            200,
            {
                "result": {
                    "jobOpeningName": "Sample Product Manager",
                    "departmentLabel": "Product",
                    "locationLabel": "Remote",
                    "employmentStatusLabel": "Full-Time",
                    "description": "<p>Sample job description.</p>",
                }
            },
        )

    monkeypatch.setattr(requests, "get", fake_get)

    result = ats.extract_job_text(url)

    assert "Sample Product Manager" in result
    assert "Product" in result
    assert "Sample job description." in result


@pytest.mark.discovery
def test_extract_job_text_bamboohr_non_200_returns_none(monkeypatch):
    url = "https://examplecorp.bamboohr.com/careers/42"

    def fake_get(api_url, headers=None, timeout=None):
        return _FakeResponse(404)

    monkeypatch.setattr(requests, "get", fake_get)

    assert ats.extract_job_text(url) is None


@pytest.mark.discovery
def test_extract_job_text_teamtailor(monkeypatch):
    url = "https://examplecorp.teamtailor.com/jobs/123-senior-backend-engineer"

    def fake_get(api_url, headers=None, timeout=None):
        assert api_url == "https://examplecorp.teamtailor.com/api/v1/jobs/123"
        return _FakeResponse(
            200,
            {
                "data": {
                    "attributes": {
                        "title": "Sample Senior Backend Engineer",
                        "department-name": "Engineering",
                        "location": "Stockholm",
                        "employment-type": "Full-time",
                        "remote-status": "remote",
                        "body": "<p>Sample job description.</p>",
                    }
                }
            },
        )

    monkeypatch.setattr(requests, "get", fake_get)

    result = ats.extract_job_text(url)

    assert "Sample Senior Backend Engineer" in result
    assert "Stockholm" in result
    assert "remote" in result
    assert "Sample job description." in result


@pytest.mark.discovery
def test_extract_job_text_teamtailor_non_200_returns_none(monkeypatch):
    url = "https://examplecorp.teamtailor.com/jobs/123-senior-backend-engineer"

    def fake_get(api_url, headers=None, timeout=None):
        return _FakeResponse(404)

    monkeypatch.setattr(requests, "get", fake_get)

    assert ats.extract_job_text(url) is None