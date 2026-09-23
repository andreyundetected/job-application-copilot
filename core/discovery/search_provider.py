import logging

import requests

import config

logger = logging.getLogger(__name__)

# Kept as the name every provider raises, for backwards compatibility with
# existing call sites and tests that catch/import "SerpentSearchError" -
# despite the name, it's now the generic error for any search provider.
class SerpentSearchError(Exception):
    pass


# Serpent's date param values map straight onto its own API. Serper uses a
# different format (Google's "tbs" query-time-range codes), so we translate.
_SERPER_DATE_MAP = {
    "d1": "qdr:d",
    "w1": "qdr:w",
    "m1": "qdr:m",
}


class BaseSearchProvider:
    name = "base"

    def search(self, query: str, num: int = 50, date: str | None = None, page: int = 1) -> dict:
        raise NotImplementedError


class SerpentSearchProvider(BaseSearchProvider):
    name = "serpent"

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key if api_key is not None else config.SERPENT_API_KEY
        self.base_url = base_url if base_url is not None else config.SERPENT_BASE_URL

    def search(self, query: str, num: int = 50, date: str | None = None, page: int = 1) -> dict:
        num = max(1, min(num, 100))

        params = {"engine": "google", "q": query, "num": num}
        if date:
            params["date"] = date
        if page and page > 1:
            params["page"] = page

        logger.info("Serpent request: q=%r num=%s date=%s page=%s", query, num, date, page)

        response = requests.get(
            self.base_url,
            params=params,
            headers={"X-API-Key": self.api_key},
            timeout=30,
        )

        if response.status_code != 200:
            logger.error(
                "Serpent request failed: status=%s body=%s", response.status_code, response.text[:500]
            )
            raise SerpentSearchError(
                f"Serpent search failed with status {response.status_code}: {response.text[:300]}"
            )

        data = response.json()

        if not data.get("success", True):
            logger.error("Serpent request unsuccessful: %s", str(data)[:500])
            raise SerpentSearchError(f"Serpent search unsuccessful: {str(data)[:300]}")

        results_block = data.get("results")
        if not isinstance(results_block, dict) or "organic" not in results_block:
            logger.error("Serpent unexpected response shape: %s", str(data)[:500])
            raise SerpentSearchError(f"Unexpected Serpent response shape: {str(data)[:300]}")

        organic_results = results_block.get("organic") or []

        results = []
        for item in organic_results:
            url = item.get("url") or item.get("link")
            if not url:
                continue
            results.append(
                {
                    "title": item.get("title"),
                    "url": url,
                    "snippet": item.get("snippet"),
                }
            )

        logger.info(
            "Serpent response: q=%r organic_count=%s parsed_count=%s",
            query,
            len(organic_results),
            len(results),
        )
        if len(organic_results) == 0:
            logger.warning("Serpent returned 0 organic results for query: %r", query)

        return {
            "results": results,
            "requested_num": num,
            "returned_count": len(organic_results),
            "raw_response": data,
        }


class SerperSearchProvider(BaseSearchProvider):
    """https://serper.dev - Google SERP API. POST {base_url} with an X-API-KEY
    header and a {"q": ..., "num": ...} JSON body; response has an "organic"
    array of {title, link, snippet, ...}."""

    name = "serper"

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key if api_key is not None else config.SERPER_API_KEY
        self.base_url = base_url if base_url is not None else config.SERPER_BASE_URL

    def search(self, query: str, num: int = 50, date: str | None = None, page: int = 1) -> dict:
        num = max(1, min(num, 100))

        payload = {"q": query, "num": num}
        tbs = _SERPER_DATE_MAP.get(date)
        if tbs:
            payload["tbs"] = tbs
        if page and page > 1:
            payload["page"] = page

        logger.info("Serper request: q=%r num=%s date=%s page=%s (tbs=%s)", query, num, date, page, tbs)

        response = requests.post(
            self.base_url,
            json=payload,
            headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code != 200:
            logger.error(
                "Serper request failed: status=%s body=%s", response.status_code, response.text[:500]
            )
            raise SerpentSearchError(
                f"Serper search failed with status {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        organic_results = data.get("organic") or []

        results = []
        for item in organic_results:
            url = item.get("link") or item.get("url")
            if not url:
                continue
            results.append(
                {
                    "title": item.get("title"),
                    "url": url,
                    "snippet": item.get("snippet"),
                }
            )

        logger.info(
            "Serper response: q=%r organic_count=%s parsed_count=%s",
            query,
            len(organic_results),
            len(results),
        )
        if len(organic_results) == 0:
            logger.warning("Serper returned 0 organic results for query: %r", query)

        return {
            "results": results,
            "requested_num": num,
            "returned_count": len(organic_results),
            "raw_response": data,
        }


_PROVIDER_REGISTRY = {
    "serpent": (SerpentSearchProvider, "SERPENT_API_KEY"),
    "serper": (SerperSearchProvider, "SERPER_API_KEY"),
}


def _configured_providers() -> list[BaseSearchProvider]:
    """Builds provider instances in SEARCH_PROVIDER_ORDER, skipping any whose
    API key is empty. A provider with no key configured is silently left out
    rather than instantiated and made to fail."""
    order = [name.strip() for name in config.SEARCH_PROVIDER_ORDER.split(",") if name.strip()]

    providers = []
    for name in order:
        entry = _PROVIDER_REGISTRY.get(name)
        if entry is None:
            logger.warning("Unknown search provider in SEARCH_PROVIDER_ORDER: %r", name)
            continue
        provider_cls, key_attr = entry
        if not getattr(config, key_attr, ""):
            continue
        providers.append(provider_cls())

    return providers


class MultiSearchProvider(BaseSearchProvider):
    """Tries each configured provider in order; on any SerpentSearchError,
    logs it and falls through to the next provider. Only raises once every
    configured provider has failed (or none were configured at all)."""

    name = "multi"

    def __init__(self, providers: list[BaseSearchProvider]):
        self.providers = providers

    def search(self, query: str, num: int = 50, date: str | None = None, page: int = 1) -> dict:
        if not self.providers:
            raise SerpentSearchError(
                "No search provider configured - set SERPENT_API_KEY and/or SERPER_API_KEY"
            )

        last_error: Exception | None = None
        for provider in self.providers:
            try:
                return provider.search(query, num=num, date=date, page=page)
            except SerpentSearchError as error:
                logger.warning(
                    "Search provider %r failed (%s), trying next configured provider", provider.name, error
                )
                last_error = error
                continue

        raise last_error or SerpentSearchError("All configured search providers failed")


def get_search_provider() -> BaseSearchProvider:
    return MultiSearchProvider(_configured_providers())