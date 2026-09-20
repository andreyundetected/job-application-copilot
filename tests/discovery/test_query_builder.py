import pytest

from core.discovery.query_builder import (
    build_query_string,
    build_site_filter,
    count_words,
    validate_query_length,
    suggest_search_queries,
)


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_user_prompt = None

    def call(self, system_prompt: str, user_prompt: str) -> str:
        self.last_user_prompt = user_prompt
        return self.response_text


@pytest.mark.discovery
def test_count_words_counts_whitespace_separated_tokens():
    assert count_words("AI Engineer LLM") == 3


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
def test_build_query_string_combines_site_filter_and_terms():
    query = build_query_string(["AI Engineer", "LLM Engineer"], ["example.com"])

    assert query.startswith("(site:example.com)")
    assert '"AI Engineer"' in query
    assert '"LLM Engineer"' in query
    assert " OR " in query


@pytest.mark.discovery
def test_build_query_string_with_no_terms_returns_only_site_filter():
    query = build_query_string([], ["example.com"])

    assert query == "(site:example.com)"


@pytest.mark.discovery
def test_validate_query_length_true_when_under_limit():
    assert validate_query_length("one two three", max_words=5) is True


@pytest.mark.discovery
def test_validate_query_length_false_when_over_limit():
    assert validate_query_length("one two three four five six", max_words=5) is False


@pytest.mark.discovery
def test_suggest_search_queries_parses_grouped_terms():
    provider = _FakeProvider(
        "<query><term>AI Engineer</term><term>LLM Engineer</term></query>"
        "<query><term>Applied AI Engineer</term></query>"
    )

    groups = suggest_search_queries(provider, "Sample candidate background")

    assert groups == [["AI Engineer", "LLM Engineer"], ["Applied AI Engineer"]]


@pytest.mark.discovery
def test_suggest_search_queries_passes_context_to_prompt():
    provider = _FakeProvider("<query><term>AI Engineer</term></query>")

    suggest_search_queries(provider, "Unique candidate marker")

    assert "Unique candidate marker" in provider.last_user_prompt


@pytest.mark.discovery
def test_suggest_search_queries_handles_empty_response():
    provider = _FakeProvider("")

    groups = suggest_search_queries(provider, "context")

    assert groups == []


@pytest.mark.discovery
def test_suggest_search_queries_skips_groups_with_no_valid_terms():
    provider = _FakeProvider("<query></query><query><term>AI Engineer</term></query>")

    groups = suggest_search_queries(provider, "context")

    assert groups == [["AI Engineer"]]