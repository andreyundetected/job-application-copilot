import pytest

from core.structuring.prompt import render_structure_prompt


@pytest.mark.structuring
def test_prompt_includes_raw_text_and_label():
    prompt = render_structure_prompt("Sample resume raw text", source_label="resume")

    assert "Sample resume raw text" in prompt
    assert "resume" in prompt


@pytest.mark.structuring
def test_prompt_contains_output_format_tags():
    prompt = render_structure_prompt("text", source_label="resume")

    for tag in ["<name>", "<contact>", "<summary>", "<experience", "<bullet>", "<subsection", "<extra_section", "<skill_group"]:
        assert tag in prompt