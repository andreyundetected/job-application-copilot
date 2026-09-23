import pytest

from core.gap_analysis.pipeline import (
    _dedupe_gap_items,
    extract_job_requirements,
    match_gap_items,
    parse_g_tags,
)


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_user_prompt = None

    def call(self, system_prompt: str, user_prompt: str, max_tokens=None, reasoning_effort=None) -> str:
        self.last_user_prompt = user_prompt
        return self.response_text


@pytest.mark.gap_analysis
def test_extract_job_requirements_parses_tiered_items():
    provider = _FakeProvider(
        "<think>reasoning</think>"
        "<items_1>\nPython | skill\nDocker | tool\n</items_1>"
        "<items_4>\nteaching | experience\n</items_4>"
    )

    result = extract_job_requirements(provider, "job text")

    assert result == [
        {"text": "Python", "priority": "required", "category": "skill"},
        {"text": "Docker", "priority": "required", "category": "tool"},
        {"text": "teaching", "priority": "preferred", "category": "experience"},
    ]


@pytest.mark.gap_analysis
def test_extract_job_requirements_ignores_think_block():
    provider = _FakeProvider(
        "<think>Python appears twice so it's important\nDocker is mentioned once</think>"
        "<items_1>\nPython | skill\n</items_1>"
    )

    result = extract_job_requirements(provider, "job text")

    assert len(result) == 1
    assert result[0]["text"] == "Python"


@pytest.mark.gap_analysis
def test_extract_job_requirements_untiered_items_default_to_required():
    provider = _FakeProvider("<items>\nPython | skill\n</items>")

    result = extract_job_requirements(provider, "job text")

    assert result[0]["priority"] == "required"


@pytest.mark.gap_analysis
def test_extract_job_requirements_item_without_category_defaults_to_domain():
    provider = _FakeProvider("<items_1>\nfintech\n</items_1>")

    result = extract_job_requirements(provider, "job text")

    assert result[0]["category"] == "domain"


@pytest.mark.gap_analysis
def test_extract_job_requirements_empty_response_returns_empty_list():
    provider = _FakeProvider("<think>nothing found</think>")

    result = extract_job_requirements(provider, "job text")

    assert result == []


@pytest.mark.gap_analysis
def test_match_gap_items_skips_invalid_status():
    provider = _FakeProvider(
        '<g status=unknown text="Python" category=skill />'
        '<g status=match text="Docker" category=skill />'
    )

    result = match_gap_items(provider, requirements=[], resume_items=[])

    assert len(result) == 1
    assert result[0]["text"] == "Docker"


@pytest.mark.gap_analysis
def test_parse_g_tags_accepts_unquoted_attributes():
    raw = '<g status=match text="Python" category=skill priority=required original=skills suggest=skills keep=none reason="" />'

    result = parse_g_tags(raw)

    assert len(result) == 1
    item = result[0]
    assert item["status"] == "match"
    assert item["text"] == "Python"
    assert item["category"] == "skill"
    assert item["priority"] == "required"
    assert item["original_field_path"] == "skills"
    assert item["suggested_field_paths"] == ["skills"]


@pytest.mark.gap_analysis
def test_parse_g_tags_accepts_mixed_quoted_and_unquoted():
    raw = '<g status=over text="Flask" category=tool priority=none original=skills suggest=none keep=no reason="not core" />'

    result = parse_g_tags(raw)

    assert len(result) == 1
    assert result[0]["status"] == "over"
    assert result[0]["recommend_keep"] is False
    assert result[0]["suggested_reason"] == "not core"


@pytest.mark.gap_analysis
def test_parse_g_tags_bare_value_with_spaces_stops_at_next_attr():
    raw = '<g status=match text="LLM" category=skill priority=required original=experience: NeuroMentor suggest=skills;summary keep=none reason="" />'

    result = parse_g_tags(raw)

    assert len(result) == 1
    assert result[0]["original_field_path"] == "experience: NeuroMentor"
    assert result[0]["suggested_field_paths"] == ["skills", "summary"]


@pytest.mark.gap_analysis
def test_dedupe_gap_items_prefers_match_over_over():
    items = [
        {"text": "Python", "status": "over", "category": "skill", "priority": None,
         "source": None, "original_field_path": "skills", "suggested_field_paths": [],
         "suggested_reason": None, "recommend_keep": True},
        {"text": "Python", "status": "match", "category": "skill", "priority": "required",
         "source": None, "original_field_path": "skills", "suggested_field_paths": ["skills"],
         "suggested_reason": None, "recommend_keep": None},
    ]

    result = _dedupe_gap_items(items)

    assert len(result) == 1
    assert result[0]["status"] == "match"


@pytest.mark.gap_analysis
def test_dedupe_gap_items_keeps_distinct_texts():
    items = [
        {"text": "Python", "status": "match", "category": "skill", "priority": "required",
         "source": None, "original_field_path": "skills", "suggested_field_paths": [],
         "suggested_reason": None, "recommend_keep": None},
        {"text": "Docker", "status": "over", "category": "skill", "priority": None,
         "source": None, "original_field_path": "skills", "suggested_field_paths": [],
         "suggested_reason": None, "recommend_keep": True},
    ]

    result = _dedupe_gap_items(items)

    assert {i["text"] for i in result} == {"Python", "Docker"}