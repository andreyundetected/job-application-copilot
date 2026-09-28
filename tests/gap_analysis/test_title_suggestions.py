import pytest

from core.gap_analysis.title_suggestions import suggest_title_changes
from ui.tailoring_page.router import _title_sort_key


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def call(self, system_prompt, user_prompt, max_tokens=None, reasoning_effort=None):
        return self.response_text


_TARGETS = [
    {"key": "title:main", "kind": "main", "company": "", "line": 0, "current": "AI Engineer"},
    {"key": "title:Acme", "kind": "experience", "company": "Acme", "line": 0, "current": "Developer"},
]


@pytest.mark.gap_analysis
def test_suggestions_keep_document_order_and_carry_order_index():
    response = (
        '<title_suggestion id="1">Backend Engineer</title_suggestion>'
        '<title_suggestion id="0">LLM Engineer</title_suggestion>'
    )

    result = suggest_title_changes(_FakeProvider(response), _TARGETS, "job")

    assert [item["key"] for item in result] == ["title:main", "title:Acme"]
    assert [item["order"] for item in result] == [0, 1]


@pytest.mark.gap_analysis
def test_title_sort_key_prefers_stored_order():
    items = [
        {"key": "title:Acme", "line": 0, "order": 1},
        {"key": "title:main", "line": 0, "order": 0},
    ]

    items.sort(key=lambda item: _title_sort_key(item, {"title:Acme": 0, "title:main": 1}))

    assert [item["key"] for item in items] == ["title:main", "title:Acme"]


@pytest.mark.gap_analysis
def test_title_sort_key_falls_back_to_block_order_for_legacy_items():
    items = [
        {"key": "title:Acme", "line": 0},
        {"key": "title:main", "line": 0},
    ]

    items.sort(key=lambda item: _title_sort_key(item, {"title:main": 0, "title:Acme": 1}))

    assert [item["key"] for item in items] == ["title:main", "title:Acme"]