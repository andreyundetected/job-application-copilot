import pytest

from core.gap_analysis.title_suggestions import suggest_title_changes


class _FakeProvider:
    def __init__(self):
        self.last_prompt = ""

    def call(self, system_prompt, user_prompt, max_tokens=None, **kwargs):
        self.last_prompt = user_prompt
        return ""


def _prompt():
    provider = _FakeProvider()
    targets = [{"key": "title:Acme", "kind": "experience", "company": "Acme", "current": "LLM Engineer"}]
    suggest_title_changes(provider, targets, "posting", {}, "Data Scientist")
    return provider.last_prompt


@pytest.mark.gap_analysis
def test_prompt_makes_unchanged_title_a_good_result():
    prompt = _prompt()

    assert "A title that stays unchanged is a normal, good result" in prompt
    assert "Do not force a change to look useful." in prompt
    assert "do not hold back" not in prompt.lower()


@pytest.mark.gap_analysis
def test_prompt_lists_free_synonyms_of_the_ai_family():
    prompt = _prompt()

    assert "FAMILY A" in prompt
    for word in ["LLM", "GenAI", "Generative AI", "Applied AI", "Agentic AI", "Conversational AI"]:
        assert word in prompt
    assert "Engineer and Developer are interchangeable" in prompt


@pytest.mark.gap_analysis
def test_prompt_requires_proof_for_neighbouring_specialisations():
    prompt = _prompt()

    assert "FAMILY B" in prompt
    assert "Full-Stack, Frontend, Mobile" in prompt
    assert "only when the work text contains a concrete phrase" in prompt


@pytest.mark.gap_analysis
def test_prompt_forbids_other_professions_and_seniority_changes():
    prompt = _prompt()

    assert "FORBIDDEN CATEGORIES" in prompt
    for word in ["Data Scientist", "Product Manager", "Architect", "Analyst"]:
        assert word in prompt
    assert "Never add or raise seniority" in prompt


@pytest.mark.gap_analysis
def test_prompt_has_the_former_employer_test_and_proof_in_reason():
    prompt = _prompt()

    assert "THE GOLDEN TEST" in prompt
    assert "former employer" in prompt
    assert "A changed title without such support is not allowed: use same." in prompt