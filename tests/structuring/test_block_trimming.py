import pytest

from core.structuring.block_detection import detect_blocks, parse_blocks


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_user_prompt = ""

    def call(self, system_prompt, user_prompt, max_tokens=None, reasoning_effort=None):
        self.last_user_prompt = user_prompt
        return self.response_text


@pytest.mark.structuring
def test_detect_blocks_uses_ranges_from_llm_without_code_trimming():
    html = (
        '<p data-eid="e1">SKILLS</p>'
        '<ul data-eid="e2"><li>Python</li></ul>'
        '<p data-eid="e3">Remote | 2023 - 2024</p>'
        '<p data-eid="e4">Built things</p>'
    )
    raw = (
        '<block kind="skills" from="e2" to="e2" />'
        '<block kind="exp_body" company="Acme" from="e4" to="e4" />'
    )

    blocks = detect_blocks(_FakeProvider(raw), html)

    assert blocks[0]["element_ids"] == ["e2"]
    assert blocks[1]["element_ids"] == ["e4"]


@pytest.mark.structuring
def test_parse_blocks_rejects_section_kind():
    raw = '<block kind="section" label="Education" from="e1" to="e1" />'

    assert parse_blocks(raw, ["e1"]) == []


@pytest.mark.structuring
def test_prompt_lists_fixed_text_examples():
    provider = _FakeProvider("")

    detect_blocks(provider, '<p data-eid="e1">Text</p>')

    assert "WORDS THAT NEVER BELONG TO A BLOCK" in provider.last_user_prompt