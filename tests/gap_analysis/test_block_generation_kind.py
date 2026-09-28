import pytest

from core.gap_analysis.block_generation import generate_block_fragments


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def call(self, system_prompt, user_prompt, max_tokens=None, reasoning_effort=None):
        self.last_user_prompt = user_prompt
        return self.response_text


_FRAGMENTS = [
    '<p data-eid="e1"><span style="font-size:10pt">Old text here today</span></p>',
    '<ul data-eid="e2"><li><span style="font-size:10pt">One</span></li></ul>',
]

_LONGER = '<el n="0">New text here today with Docker</el><el n="1" list="true"><li>One</li></el>'


@pytest.mark.gap_analysis
def test_text_block_rejects_growth_that_skills_block_allows():
    with pytest.raises(ValueError):
        generate_block_fragments(_FakeProvider(_LONGER), _FRAGMENTS, "Job", "resume", "job", [], [], "", kind="exp_body")

    result = generate_block_fragments(_FakeProvider(_LONGER), _FRAGMENTS, "Skills", "resume", "job", [], [], "", kind="skills")

    assert "with Docker" in result[0]


@pytest.mark.gap_analysis
def test_prompt_contains_skills_rules_only_for_skills_kind():
    skills_provider = _FakeProvider("")
    text_provider = _FakeProvider("")

    generate_block_fragments(skills_provider, _FRAGMENTS, "Skills", "resume", "job", [], [], "", kind="skills")
    generate_block_fragments(text_provider, _FRAGMENTS, "Job", "resume", "job", [], [], "", kind="exp_body")

    assert "SKILLS BLOCK" in skills_provider.last_user_prompt
    assert "WHAT YOU NEVER DO" not in skills_provider.last_user_prompt
    assert "WHAT YOU NEVER DO" in text_provider.last_user_prompt