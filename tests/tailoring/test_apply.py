import pytest

from core.tailoring.apply import get_by_path, set_by_path


_SAMPLE_CONTENT = {
    "name": "Sample Name",
    "summary": "Sample summary",
    "experience": [
        {
            "company": "Example Corp",
            "role": "Engineer",
            "content": [
                {"type": "paragraph", "text": "Intro"},
                {"type": "bullet_list", "items": ["First", "Second"]},
            ],
        }
    ],
    "skills": [{"label": "Languages", "items": ["Python", "SQL"]}],
}


@pytest.mark.tailoring
def test_get_by_path_plain_key():
    assert get_by_path(_SAMPLE_CONTENT, "summary") == "Sample summary"


@pytest.mark.tailoring
def test_get_by_path_nested_index():
    assert get_by_path(_SAMPLE_CONTENT, "experience[0].role") == "Engineer"


@pytest.mark.tailoring
def test_get_by_path_deep_list_index():
    result = get_by_path(_SAMPLE_CONTENT, "experience[0].content[1]")
    assert result == {"type": "bullet_list", "items": ["First", "Second"]}


@pytest.mark.tailoring
def test_set_by_path_plain_key_does_not_mutate_original():
    updated = set_by_path(_SAMPLE_CONTENT, "summary", "New summary")

    assert updated["summary"] == "New summary"
    assert _SAMPLE_CONTENT["summary"] == "Sample summary"


@pytest.mark.tailoring
def test_set_by_path_nested_field():
    updated = set_by_path(_SAMPLE_CONTENT, "experience[0].role", "LLM Engineer")

    assert updated["experience"][0]["role"] == "LLM Engineer"
    assert _SAMPLE_CONTENT["experience"][0]["role"] == "Engineer"


@pytest.mark.tailoring
def test_set_by_path_replaces_content_blocks_list():
    new_blocks = [{"type": "paragraph", "text": "Rewritten"}]

    updated = set_by_path(_SAMPLE_CONTENT, "experience[0].content", new_blocks)

    assert updated["experience"][0]["content"] == new_blocks


@pytest.mark.tailoring
def test_set_by_path_invalid_segment_raises():
    with pytest.raises(ValueError):
        set_by_path(_SAMPLE_CONTENT, "experience[0]..role", "x")