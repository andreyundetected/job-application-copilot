import pytest

from core.discovery.search_provider import SerpentSearchError, SerpentSearchProvider


class _FakeResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


@pytest.mark.discovery
def test_search_returns_parsed_results(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")

    def fake_get(url, params=None, headers=None, timeout=None):
        assert url == "https://apiserpent.com/api/search/quick"
        assert params["engine"] == "google"
        assert params["q"] == "sample query"
        assert params["num"] == 50
        assert headers["X-API-Key"] == "fake-key"
        return _FakeResponse(
            200,
            {
                "organic_results": [
                    {
                        "title": "Sample Job A",
                        "link": "https://boards.greenhouse.io/a/jobs/1",
                        "snippet": "Snippet A",
                    },
                    {
                        "title": "Sample Job B",
                        "link": "https://jobs.lever.co/b/2",
                        "snippet": "Snippet B",
                    },
                ]
            },
        )

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    result = provider.search("sample query", num=50)

    assert result["requested_num"] == 50
    assert result["returned_count"] == 2
    assert len(result["results"]) == 2
    assert result["results"][0]["title"] == "Sample Job A"
    assert result["results"][0]["url"] == "https://boards.greenhouse.io/a/jobs/1"


@pytest.mark.discovery
def test_search_passes_date_param_when_given(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(200, {"organic_results": []})

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    provider.search("sample query", num=20, date="d1")

    assert captured["params"]["date"] == "d1"


@pytest.mark.discovery
def test_search_omits_date_param_when_not_given(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(200, {"organic_results": []})

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    provider.search("sample query", num=20)

    assert "date" not in captured["params"]


@pytest.mark.discovery
def test_search_clamps_num_to_valid_range(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(200, {"organic_results": []})

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    provider.search("sample query", num=500)

    assert captured["params"]["num"] == 100


@pytest.mark.discovery
def test_search_skips_results_without_url(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(
            200,
            {
                "organic_results": [
                    {"title": "No URL here", "snippet": "Snippet"},
                    {"title": "Has URL", "link": "https://jobs.ashbyhq.com/c/3", "snippet": "Snippet C"},
                ]
            },
        )

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    result = provider.search("sample query", num=10)

    assert result["returned_count"] == 2
    assert len(result["results"]) == 1
    assert result["results"][0]["url"] == "https://jobs.ashbyhq.com/c/3"


@pytest.mark.discovery
def test_search_raises_on_non_200_status(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(400, text="Bad request")

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    with pytest.raises(SerpentSearchError):
        provider.search("sample query", num=10)


@pytest.mark.discovery
def test_provider_uses_config_defaults(monkeypatch):
    monkeypatch.setattr("core.discovery.search_provider.config.SERPENT_API_KEY", "config-key")
    monkeypatch.setattr(
        "core.discovery.search_provider.config.SERPENT_BASE_URL",
        "https://apiserpent.com/api/search/quick",
    )

    provider = SerpentSearchProvider()

    assert provider.api_key == "config-key"
    assert provider.base_url == "https://apiserpent.com/api/search/quick"