import pytest

from core.tailoring.html_diff import (
    apply_fragment,
    find_html_range,
    strip_marks,
    wrap_highlights,
)


@pytest.mark.tailoring
def test_find_html_range_finds_unique_plain_text():
    html = "<p>Hello world</p>"
    found = find_html_range(html, "Hello world")

    assert found is not None
    start, end = found
    assert html[start:end] == "Hello world"


@pytest.mark.tailoring
def test_find_html_range_returns_none_when_not_unique():
    html = "<p>duplicate</p><p>duplicate</p>"
    assert find_html_range(html, "duplicate") is None


@pytest.mark.tailoring
def test_find_html_range_returns_none_when_absent():
    html = "<p>Hello world</p>"
    assert find_html_range(html, "Goodbye") is None


@pytest.mark.tailoring
def test_apply_fragment_replaces_text_and_escapes_html():
    html = "<p>Hello world</p>"
    result = apply_fragment(html, "Hello world", "Hi <there>")

    assert "Hi &lt;there&gt;" in result
    assert "Hello world" not in result


@pytest.mark.tailoring
def test_apply_fragment_raises_when_fragment_not_found():
    html = "<p>Hello world</p>"
    with pytest.raises(ValueError):
        apply_fragment(html, "Not present", "Replacement")


@pytest.mark.tailoring
def test_wrap_highlights_default_wraps_original_text_pending_style():
    html = "<p>Hello world</p>"
    changes = [{"id": 1, "original_text": "Hello world", "proposed_text": "Hi there"}]

    result = wrap_highlights(html, changes)

    assert '<mark data-change-id="1">Hello world</mark>' in result


@pytest.mark.tailoring
def test_wrap_highlights_approved_style_searches_proposed_text_with_title():
    html = "<p>Hi there</p>"
    changes = [{"id": 2, "original_text": "Hello world", "proposed_text": "Hi there"}]

    result = wrap_highlights(html, changes, search_field="proposed_text", css_class="approved-mark")

    assert 'class="approved-mark"' in result
    assert 'title="Hello world"' in result
    assert ">Hi there</mark>" in result


@pytest.mark.tailoring
def test_wrap_highlights_skips_changes_it_cannot_find():
    html = "<p>Some text</p>"
    changes = [{"id": 3, "original_text": "Missing text", "proposed_text": "New text"}]

    result = wrap_highlights(html, changes)

    assert result == html


@pytest.mark.tailoring
def test_strip_marks_unwraps_mark_tags_regardless_of_class():
    html = '<p>Before <mark data-change-id="1" class="approved-mark" title="x">edited</mark> after</p>'
    result = strip_marks(html)

    assert result == "<p>Before edited after</p>"