import pytest

from core.gap_analysis.block_generation import generate_block_fragments
from core.gap_analysis.title_suggestions import suggest_title_changes


class _FakeProvider:
    def __init__(self, response_text):
        self.response_text = response_text
        self.last_prompt = ""

    def call(self, system_prompt, user_prompt, max_tokens=None, **kwargs):
        self.last_prompt = user_prompt
        return self.response_text


@pytest.mark.gap_analysis
def test_target_role_reaches_the_title_prompt_and_the_suggestion_is_returned():
    provider = _FakeProvider('<title_suggestion id="0">AI Engineer</title_suggestion>')
    targets = [{"key": "title:Acme", "kind": "experience", "company": "Acme", "current": "LLM Engineer"}]

    result = suggest_title_changes(provider, targets, "posting", {}, "AI Engineer")

    assert "AI Engineer" in provider.last_prompt
    assert result[0]["suggested"] == "AI Engineer"


@pytest.mark.gap_analysis
def test_unchanged_title_is_returned_as_not_changed():
    provider = _FakeProvider('<title_suggestion id="0">Backend Developer</title_suggestion>')
    targets = [{"key": "title:Acme", "kind": "experience", "company": "Acme", "current": "Backend Developer"}]

    result = suggest_title_changes(provider, targets, "posting", {}, "AI Engineer")

    assert len(result) == 1
    assert result[0]["changed"] is False


@pytest.mark.gap_analysis
def test_skills_block_uses_the_skills_prompt():
    provider = _FakeProvider('<el n="0">Languages: Python\nFrameworks: Flask, Kafka</el>')

    result = generate_block_fragments(
        provider,
        ["<p>Languages: Python<br>Frameworks: Flask</p>"],
        "Skills",
        "resume text",
        "posting text",
        ["Kafka"],
        [],
        "",
        kind="skills",
    )

    assert "SKILLS block" in provider.last_prompt
    assert "Kafka" in result[0]


@pytest.mark.gap_analysis
def test_summary_uses_the_summary_prompt():
    provider = _FakeProvider(
        '<el n="0">Built agents and RAG pipelines for clients with Python and vector databases</el>'
    )

    result = generate_block_fragments(
        provider,
        ["<p>Built agents and RAG pipelines for clients with Python</p>"],
        "Summary",
        "resume text",
        "posting text",
        ["vector databases"],
        [],
        "",
        kind="summary",
    )

    assert "SUMMARY" in provider.last_prompt
    assert "vector databases" in result[0]