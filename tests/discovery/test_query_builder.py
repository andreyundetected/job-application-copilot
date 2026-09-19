import pytest

from core.discovery.query_builder import (
    build_queries,
    build_site_filter,
    chunk_terms,
    suggest_search_terms,
)


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_user_prompt = None

    def call(self, system_prompt: str, user_prompt: str) -> str:
        self.last_user_prompt = user_prompt
        return self.response_text


@pytest.mark.discovery
def test_chunk_terms_splits_evenly():
    terms = ["a", "b", "c", "d", "e"]

    chunks = chunk_terms(terms, chunk_size=2)

    assert chunks == [["a", "b"], ["c", "d"], ["e"]]


@pytest.mark.discovery
def test_chunk_terms_single_chunk_when_size_covers_all():
    terms = ["a", "b", "c"]

    chunks = chunk_terms(terms, chunk_size=10)

    assert chunks == [["a", "b", "c"]]


@pytest.mark.discovery
def test_chunk_terms_rejects_non_positive_size():
    with pytest.raises(ValueError):
        chunk_terms(["a"], chunk_size=0)


@pytest.mark.discovery
def test_build_site_filter_default_sites():
    result = build_site_filter()

    assert "site:boards.greenhouse.io" in result
    assert "site:jobs.lever.co" in result
    assert "site:jobs.ashbyhq.com" in result
    assert " OR " in result


@pytest.mark.discovery
def test_build_site_filter_custom_sites():
    result = build_site_filter(["example.com"])

    assert result == "(site:example.com)"


@pytest.mark.discovery
def test_build_queries_chunks_terms_into_separate_queries():
    terms = ["AI Engineer", "LLM Engineer", "Applied AI Engineer"]

    queries = build_queries(terms, chunk_size=2)

    assert len(queries) == 2
    assert '"AI Engineer"' in queries[0]
    assert '"LLM Engineer"' in queries[0]
    assert '"Applied AI Engineer"' in queries[1]
    assert "site:boards.greenhouse.io" in queries[0]
    assert "site:boards.greenhouse.io" in queries[1]


@pytest.mark.discovery
def test_suggest_search_terms_parses_response():
    provider = _FakeProvider("<term>AI Engineer</term><term>LLM Engineer</term>")

    terms = suggest_search_terms(provider, "Sample candidate background")

    assert terms == ["AI Engineer", "LLM Engineer"]


@pytest.mark.discovery
def test_suggest_search_terms_passes_context_to_prompt():
    provider = _FakeProvider("<term>AI Engineer</term>")

    suggest_search_terms(provider, "Unique candidate marker")

    assert "Unique candidate marker" in provider.last_user_prompt


@pytest.mark.discovery
def test_suggest_search_terms_handles_empty_response():
    provider = _FakeProvider("")

    terms = suggest_search_terms(provider, "context")

    assert terms == []