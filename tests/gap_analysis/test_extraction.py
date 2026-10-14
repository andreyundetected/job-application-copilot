import pytest

from core.gap_analysis.extraction import extract_keywords, parse_keywords


class _SequenceProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def call(self, system_prompt, user_prompt, max_tokens=None, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


@pytest.mark.gap_analysis
def test_parse_keywords_reads_tags_and_ignores_surrounding_text():
    raw = """
leaked reasoning
<kw text="AI Engineer" tier="p0" kind="title" level="required" />
<kw text="Snowflake" tier="P1" kind="tool" level="preferred" />
<kw text="" tier="P0" kind="skill" level="required" />
"""

    items = parse_keywords(raw)

    assert items == [
        {"text": "AI Engineer", "category": "title", "priority": "required", "tier": "P0"},
        {"text": "Snowflake", "category": "tool", "priority": "preferred", "tier": "P1"},
    ]


@pytest.mark.gap_analysis
def test_parse_keywords_defaults_for_missing_attributes():
    items = parse_keywords('<kw text="Docker" level="whatever" />')

    assert items == [{"text": "Docker", "category": "skill", "priority": "required", "tier": None}]


@pytest.mark.gap_analysis
def test_extract_keywords_retries_on_empty_response():
    provider = _SequenceProvider(
        ["no tags here", '<kw text="Python" tier="P0" kind="skill" level="required" />']
    )

    items = extract_keywords(provider, "job text")

    assert provider.calls == 2
    assert [item["text"] for item in items] == ["Python"]