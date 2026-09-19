import requests

import config


class SerpentSearchError(Exception):
    pass


class SerpentSearchProvider:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key if api_key is not None else config.SERPENT_API_KEY
        self.base_url = base_url if base_url is not None else config.SERPENT_BASE_URL

    def search(self, query: str, num: int = 50, date: str | None = None) -> dict:
        num = max(1, min(num, 100))

        params = {"engine": "google", "q": query, "num": num}
        if date:
            params["date"] = date

        response = requests.get(
            self.base_url,
            params=params,
            headers={"X-API-Key": self.api_key},
            timeout=30,
        )

        if response.status_code != 200:
            raise SerpentSearchError(
                f"Serpent search failed with status {response.status_code}: {response.text[:300]}"
            )

        data = response.json()

        if not data.get("success", True):
            raise SerpentSearchError(f"Serpent search unsuccessful: {str(data)[:300]}")

        results_block = data.get("results")
        if not isinstance(results_block, dict) or "organic" not in results_block:
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

        return {
            "results": results,
            "requested_num": num,
            "returned_count": len(organic_results),
            "raw_response": data,
        }