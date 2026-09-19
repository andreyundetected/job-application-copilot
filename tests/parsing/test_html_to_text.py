import pytest

from core.parsing.html_to_text import html_to_text


@pytest.mark.parsing
def test_html_to_text_strips_tags_and_preserves_paragraphs():
    html = "<p>First paragraph.</p><p>Second paragraph with <b>bold</b> text.</p>"

    result = html_to_text(html)

    assert result == "First paragraph.\nSecond paragraph with bold text."


@pytest.mark.parsing
def test_html_to_text_handles_list_items():
    html = "<ul><li>Item one</li><li>Item two</li></ul>"

    result = html_to_text(html)

    assert result == "Item one\nItem two"


@pytest.mark.parsing
def test_html_to_text_handles_br_tags():
    html = "Line one<br>Line two"

    result = html_to_text(html)

    assert result == "Line one\nLine two"


@pytest.mark.parsing
def test_html_to_text_empty_input_returns_empty_string():
    assert html_to_text("") == ""
    assert html_to_text(None) == ""