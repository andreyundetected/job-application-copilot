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
def test_detect_platform_workable():
    assert ats_extractor.detect_platform("https://apply.workable.com/action1/j/950A91C0A2") == "workable"


@pytest.mark.discovery
def test_detect_platform_smartrecruiters():
    assert (
        ats_extractor.detect_platform("https://careers.smartrecruiters.com/ExampleCorp/743999912345678-software-engineer")
        == "smartrecruiters"
    )


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
def test_extract_job_text_lever_includes_categories_header(monkeypatch):
    url = "https://jobs.lever.co/aifund/abc123-def456"

    def fake_get(api_url, params=None, timeout=None):
        return _FakeResponse(
            200,
            {
                "text": "AI Engineer",
                "categories": {
                    "location": "Mountain View, CA",
                    "team": "AI Fund",
                    "commitment": "Full time",
                    "workplaceType": "on-site",
                },
                "descriptionPlain": "Who We Are...",
            },
        )

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    result = ats_extractor.extract_job_text(url)

    assert "Mountain View, CA" in result
    assert "AI Fund" in result
    assert "Full time" in result
    assert "on-site" in result


@pytest.mark.discovery
def test_extract_job_text_lever_falls_back_to_top_level_workplace_type(monkeypatch):
    url = "https://jobs.lever.co/aifund/abc123-def456"

    def fake_get(api_url, params=None, timeout=None):
        return _FakeResponse(
            200,
            {
                "text": "AI Engineer",
                "workplaceType": "remote",
                "categories": {},
                "descriptionPlain": "Who We Are...",
            },
        )

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    result = ats_extractor.extract_job_text(url)

    assert "remote" in result


@pytest.mark.discovery
def test_extract_job_text_lever_handles_missing_categories_gracefully(monkeypatch):
    url = "https://jobs.lever.co/aifund/abc123-def456"

    def fake_get(api_url, params=None, timeout=None):
        return _FakeResponse(200, {"text": "AI Engineer", "descriptionPlain": "Body text."})

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    result = ats_extractor.extract_job_text(url)

    assert "AI Engineer" in result
    assert "Body text." in result


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
def test_extract_job_text_workable(monkeypatch):
    url = "https://apply.workable.com/action1/j/950A91C0A2"

    def fake_get(api_url, params=None, timeout=None):
        assert api_url == "https://apply.workable.com/api/v1/widget/accounts/action1"
        return _FakeResponse(
            200,
            {
                "jobs": [
                    {
                        "shortcode": "950A91C0A2",
                        "title": "Sample LLM Engineer",
                        "location": {"location_str": "Remote"},
                        "description": "<p>Sample job description.</p>",
                        "full_description": "",
                        "requirements": "",
                        "benefits": "",
                    }
                ]
            },
        )

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    result = ats_extractor.extract_job_text(url)

    assert "Sample LLM Engineer" in result
    assert "Remote" in result
    assert "Sample job description." in result


@pytest.mark.discovery
def test_extract_job_text_workable_no_matching_shortcode_returns_none(monkeypatch):
    url = "https://apply.workable.com/action1/j/missing-code"

    def fake_get(api_url, params=None, timeout=None):
        return _FakeResponse(200, {"jobs": []})

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    assert ats_extractor.extract_job_text(url) is None


@pytest.mark.discovery
def test_extract_job_text_smartrecruiters(monkeypatch):
    url = "https://careers.smartrecruiters.com/ExampleCorp/743999912345678-software-engineer"

    def fake_get(api_url, params=None, timeout=None):
        assert api_url == "https://api.smartrecruiters.com/v1/companies/ExampleCorp/postings/743999912345678"
        return _FakeResponse(
            200,
            {
                "name": "Sample Software Engineer",
                "location": {"city": "Berlin", "country": "Germany"},
                "jobAd": {
                    "sections": {
                        "jobDescription": {"text": "<p>Sample job description.</p>"},
                        "qualifications": {"text": "<p>Sample qualifications.</p>"},
                    }
                },
            },
        )

    monkeypatch.setattr(ats_extractor.requests, "get", fake_get)

    result = ats_extractor.extract_job_text(url)

    assert "Sample Software Engineer" in result
    assert "Berlin" in result
    assert "Sample job description." in result
    assert "Sample qualifications." in result


@pytest.mark.discovery
def test_extract_job_text_smartrecruiters_non_200_returns_none(monkeypatch):
    url = "https://careers.smartrecruiters.com/ExampleCorp/743999912345678-software-engineer"

    def fake_get(api_url, params=None, timeout=None):
        return _FakeResponse(404)

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