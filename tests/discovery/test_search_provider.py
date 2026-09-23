import pytest

from core.discovery.search_provider import (
    MultiSearchProvider,
    SerpentSearchError,
    SerpentSearchProvider,
    SerperSearchProvider,
    get_search_provider,
)


class _FakeResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


def _raw_response(organic):
    return {
        "success": True,
        "query": "sample query",
        "results": {"organic": organic},
        "metadata": {"totalOrganicResults": len(organic)},
    }


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
            _raw_response(
                [
                    {"title": "Sample Job A", "url": "https://boards.greenhouse.io/a/jobs/1", "snippet": "Snippet A"},
                    {"title": "Sample Job B", "url": "https://jobs.lever.co/b/2", "snippet": "Snippet B"},
                ]
            ),
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
        return _FakeResponse(200, _raw_response([]))

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    provider.search("sample query", num=20, date="d1")

    assert captured["params"]["date"] == "d1"


@pytest.mark.discovery
def test_search_omits_date_param_when_not_given(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(200, _raw_response([]))

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    provider.search("sample query", num=20)

    assert "date" not in captured["params"]


@pytest.mark.discovery
def test_search_clamps_num_to_valid_range(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(200, _raw_response([]))

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    provider.search("sample query", num=500)

    assert captured["params"]["num"] == 100


@pytest.mark.discovery
def test_search_skips_results_without_url(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(
            200,
            _raw_response(
                [
                    {"title": "No URL here", "snippet": "Snippet"},
                    {"title": "Has URL", "url": "https://jobs.ashbyhq.com/c/3", "snippet": "Snippet C"},
                ]
            ),
        )

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    result = provider.search("sample query", num=10)

    assert result["returned_count"] == 2
    assert len(result["results"]) == 1
    assert result["results"][0]["url"] == "https://jobs.ashbyhq.com/c/3"


@pytest.mark.discovery
def test_search_raises_when_success_is_false(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(200, {"success": False, "error": "invalid api key"})

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    with pytest.raises(SerpentSearchError):
        provider.search("sample query", num=10)


@pytest.mark.discovery
def test_search_raises_when_results_shape_unexpected(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(200, {"success": True, "organic_results": []})

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    with pytest.raises(SerpentSearchError):
        provider.search("sample query", num=10)


@pytest.mark.discovery
def test_search_does_not_raise_when_organic_present_but_empty(monkeypatch):
    provider = SerpentSearchProvider(api_key="fake-key", base_url="https://apiserpent.com/api/search/quick")

    def fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(200, _raw_response([]))

    monkeypatch.setattr("core.discovery.search_provider.requests.get", fake_get)

    result = provider.search("sample query", num=10)

    assert result["results"] == []
    assert result["returned_count"] == 0


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


@pytest.mark.discovery
def test_serper_search_returns_parsed_results(monkeypatch):
    provider = SerperSearchProvider(api_key="fake-key", base_url="https://google.serper.dev/search")

    def fake_post(url, json=None, headers=None, timeout=None):
        assert url == "https://google.serper.dev/search"
        assert json["q"] == "sample query"
        assert json["num"] == 30
        assert headers["X-API-KEY"] == "fake-key"
        return _FakeResponse(
            200,
            {
                "organic": [
                    {"title": "Sample Job A", "link": "https://boards.greenhouse.io/a/jobs/1", "snippet": "Snippet A"},
                    {"title": "Sample Job B", "link": "https://jobs.lever.co/b/2", "snippet": "Snippet B"},
                ]
            },
        )

    monkeypatch.setattr("core.discovery.search_provider.requests.post", fake_post)

    result = provider.search("sample query", num=30)

    assert result["returned_count"] == 2
    assert result["results"][0]["url"] == "https://boards.greenhouse.io/a/jobs/1"
    assert result["results"][1]["url"] == "https://jobs.lever.co/b/2"


@pytest.mark.discovery
def test_serper_search_maps_date_to_tbs_param(monkeypatch):
    provider = SerperSearchProvider(api_key="fake-key")
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(200, {"organic": []})

    monkeypatch.setattr("core.discovery.search_provider.requests.post", fake_post)

    provider.search("sample query", num=10, date="w1")

    assert captured["json"]["tbs"] == "qdr:w"


@pytest.mark.discovery
def test_serper_search_omits_tbs_when_no_date(monkeypatch):
    provider = SerperSearchProvider(api_key="fake-key")
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _FakeResponse(200, {"organic": []})

    monkeypatch.setattr("core.discovery.search_provider.requests.post", fake_post)

    provider.search("sample query", num=10)

    assert "tbs" not in captured["json"]


@pytest.mark.discovery
def test_serper_search_raises_on_non_200(monkeypatch):
    provider = SerperSearchProvider(api_key="fake-key")

    def fake_post(url, json=None, headers=None, timeout=None):
        return _FakeResponse(403, text="Forbidden")

    monkeypatch.setattr("core.discovery.search_provider.requests.post", fake_post)

    with pytest.raises(SerpentSearchError):
        provider.search("sample query", num=10)


@pytest.mark.discovery
def test_serper_search_skips_results_without_url(monkeypatch):
    provider = SerperSearchProvider(api_key="fake-key")

    def fake_post(url, json=None, headers=None, timeout=None):
        return _FakeResponse(
            200,
            {"organic": [{"title": "No link here", "snippet": "x"}, {"title": "Has link", "link": "https://example.com/1"}]},
        )

    monkeypatch.setattr("core.discovery.search_provider.requests.post", fake_post)

    result = provider.search("sample query", num=10)

    assert result["returned_count"] == 2
    assert len(result["results"]) == 1
    assert result["results"][0]["url"] == "https://example.com/1"


@pytest.mark.discovery
def test_multi_search_provider_falls_back_to_next_provider_on_error():
    class _FailingProvider:
        name = "failing"

        def search(self, query, num=50, date=None, page=1):
            raise SerpentSearchError("first provider down")

    class _WorkingProvider:
        name = "working"

        def search(self, query, num=50, date=None, page=1):
            return {"results": [], "requested_num": num, "returned_count": 0, "raw_response": {}}

    multi = MultiSearchProvider([_FailingProvider(), _WorkingProvider()])

    result = multi.search("sample query")

    assert result["returned_count"] == 0


@pytest.mark.discovery
def test_multi_search_provider_raises_when_all_providers_fail():
    class _FailingProvider:
        name = "failing"

        def search(self, query, num=50, date=None, page=1):
            raise SerpentSearchError("down")

    multi = MultiSearchProvider([_FailingProvider(), _FailingProvider()])

    with pytest.raises(SerpentSearchError):
        multi.search("sample query")


@pytest.mark.discovery
def test_multi_search_provider_raises_when_no_providers_configured():
    multi = MultiSearchProvider([])

    with pytest.raises(SerpentSearchError):
        multi.search("sample query")


@pytest.mark.discovery
def test_get_search_provider_only_includes_configured_providers(monkeypatch):
    monkeypatch.setattr("core.discovery.search_provider.config.SEARCH_PROVIDER_ORDER", "serpent,serper")
    monkeypatch.setattr("core.discovery.search_provider.config.SERPENT_API_KEY", "")
    monkeypatch.setattr("core.discovery.search_provider.config.SERPER_API_KEY", "serper-key")

    multi = get_search_provider()

    assert isinstance(multi, MultiSearchProvider)
    assert len(multi.providers) == 1
    assert isinstance(multi.providers[0], SerperSearchProvider)


@pytest.mark.discovery
def test_get_search_provider_respects_order(monkeypatch):
    monkeypatch.setattr("core.discovery.search_provider.config.SEARCH_PROVIDER_ORDER", "serper,serpent")
    monkeypatch.setattr("core.discovery.search_provider.config.SERPENT_API_KEY", "sp-key")
    monkeypatch.setattr("core.discovery.search_provider.config.SERPER_API_KEY", "se-key")

    multi = get_search_provider()

    assert [p.name for p in multi.providers] == ["serper", "serpent"]


@pytest.mark.discovery
def test_get_search_provider_empty_when_nothing_configured(monkeypatch):
    monkeypatch.setattr("core.discovery.search_provider.config.SERPENT_API_KEY", "")
    monkeypatch.setattr("core.discovery.search_provider.config.SERPER_API_KEY", "")

    multi = get_search_provider()

    assert multi.providers == []