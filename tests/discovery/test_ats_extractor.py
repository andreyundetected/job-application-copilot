import pytest

from core.discovery import ats_extractor


class _FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


@pytest.mark.discovery
def test_detect_platform_greenhouse():
    assert ats_extractor.detect_platform("https://boards.greenhouse.io/examplecorp/jobs/1234567") == "greenhouse"


@pytest.mark.discovery
def test_detect_platform_job_boards_subdomain_greenhouse():
    assert (
        ats_extractor.detect_platform("https://job-boards.greenhouse.io/examplecorp/jobs/1234567")
        == "greenhouse"
    )


@pytest.mark.discovery
def test_detect_platform_lever():
    assert ats_extractor.detect_platform("https://jobs.lever.co/examplecorp/abc123-def456") == "lever"


@pytest.mark.discovery
def test_detect_platform_ashby():
    assert ats_extractor.detect_platform("https://jobs.ashbyhq.com/examplecorp/abc123") == "ashby"


@pytest.mark.discovery
def test_detect_platform_unknown_returns_none():
    assert ats_extractor.detect_platform("https://example.com/careers/123") is None


@pytest.mark.discovery
def test_extract_job_text_greenhouse(monkeypatch):
    url = "https://boards.greenhouse.io/examplecorp/jobs/1234567"

    def fake_get(api_url, params=None, timeout=None):
        assert api_url == "https://boards-api.greenhouse.io/v1/boards/examplecorp/jobs/1234567"
        return _FakeResponse(
            200,
            {
                "title": "Sample Backend Engineer",
                "location": {"name": "Remote"},
                "content": "<p>Sample job description.</p>",
            },
        )

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    result = ats_extractor.extract_job_text(url)

    assert "Sample Backend Engineer" in result
    assert "Remote" in result
    assert "Sample job description." in result


@pytest.mark.discovery
def test_extract_job_text_greenhouse_non_200_returns_none(monkeypatch):
    url = "https://boards.greenhouse.io/examplecorp/jobs/1234567"

    def fake_get(api_url, params=None, timeout=None):
        return _FakeResponse(404)

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    assert ats_extractor.extract_job_text(url) is None


@pytest.mark.discovery
def test_extract_job_text_lever(monkeypatch):
    url = "https://jobs.lever.co/examplecorp/abc123-def456"

    def fake_get(api_url, params=None, timeout=None):
        assert api_url == "https://api.lever.co/v0/postings/examplecorp/abc123-def456"
        return _FakeResponse(
            200,
            {
                "text": "Sample LLM Engineer",
                "descriptionPlain": "Sample plain description.",
                "lists": [{"text": "Requirements", "content": "<li>Python</li>"}],
                "additionalPlain": "Additional info.",
            },
        )

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    result = ats_extractor.extract_job_text(url)

    assert "Sample LLM Engineer" in result
    assert "Sample plain description." in result
    assert "Requirements" in result
    assert "Additional info." in result


@pytest.mark.discovery
def test_extract_job_text_ashby(monkeypatch):
    url = "https://jobs.ashbyhq.com/examplecorp/job-slug-123"

    def fake_get(api_url, params=None, timeout=None):
        assert api_url == "https://api.ashbyhq.com/posting-api/job-board/examplecorp"
        return _FakeResponse(
            200,
            {
                "jobPostings": [
                    {
                        "id": "job-slug-123",
                        "title": "Sample Applied AI Engineer",
                        "locationName": "Remote",
                        "descriptionPlain": "Sample ashby description.",
                    }
                ]
            },
        )

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    result = ats_extractor.extract_job_text(url)

    assert "Sample Applied AI Engineer" in result
    assert "Sample ashby description." in result


@pytest.mark.discovery
def test_extract_job_text_ashby_no_matching_posting_returns_none(monkeypatch):
    url = "https://jobs.ashbyhq.com/examplecorp/missing-slug"

    def fake_get(api_url, params=None, timeout=None):
        return _FakeResponse(200, {"jobPostings": []})

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    assert ats_extractor.extract_job_text(url) is None


@pytest.mark.discovery
def test_extract_job_text_unknown_platform_returns_none():
    assert ats_extractor.extract_job_text("https://example.com/careers/123") is None


@pytest.mark.discovery
def test_extract_job_text_handles_request_exception(monkeypatch):
    url = "https://boards.greenhouse.io/examplecorp/jobs/1234567"

    def fake_get(api_url, params=None, timeout=None):
        raise ats_extractor.requests.RequestException("network error")

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    assert ats_extractor.extract_job_text(url) is None