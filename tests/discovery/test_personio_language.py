import pytest
import requests

from core.discovery.ats.personio import PersonioExtractor

_EMPTY_DESCRIPTIONS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs>
<position>
<id>123456</id>
<office>Munich</office>
<name>Sample Backend Engineer</name>
<jobDescriptions />
</position>
</workzag-jobs>
"""

_FILLED_DESCRIPTIONS_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs>
<position>
<id>123456</id>
<office>Munich</office>
<name>Sample Backend Engineer</name>
<jobDescriptions>
<jobDescription>
<name>Aufgaben</name>
<value><![CDATA[Sample job description text.]]></value>
</jobDescription>
</jobDescriptions>
</position>
</workzag-jobs>
"""


class _FakeResponse:
    def __init__(self, content):
        self.status_code = 200
        self.content = content


@pytest.mark.discovery
def test_default_language_used_first_and_english_not_requested_when_filled(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        return _FakeResponse(_FILLED_DESCRIPTIONS_XML)

    monkeypatch.setattr(requests, "get", fake_get)

    result = PersonioExtractor().extract("https://examplecorp.jobs.personio.de/job/123456")

    assert calls == [{}]
    assert "Sample job description text." in result


@pytest.mark.discovery
def test_falls_back_to_english_when_default_language_has_no_descriptions(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        if params == {}:
            return _FakeResponse(_EMPTY_DESCRIPTIONS_XML)
        return _FakeResponse(_FILLED_DESCRIPTIONS_XML)

    monkeypatch.setattr(requests, "get", fake_get)

    result = PersonioExtractor().extract("https://examplecorp.jobs.personio.de/job/123456")

    assert calls == [{}, {"language": "en"}]
    assert "Sample job description text." in result


@pytest.mark.discovery
def test_returns_header_only_when_no_language_has_descriptions(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, params=None, timeout=None: _FakeResponse(_EMPTY_DESCRIPTIONS_XML))

    result = PersonioExtractor().extract("https://examplecorp.jobs.personio.de/job/123456")

    assert "Sample Backend Engineer" in result
    assert "Sample job description text." not in result