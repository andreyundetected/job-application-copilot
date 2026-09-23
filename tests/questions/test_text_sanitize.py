import pytest

from core.questions.text_sanitize import sanitize_generated_text


@pytest.mark.questions
def test_removes_bold():
    assert sanitize_generated_text("I have **five years** of experience.") == "I have five years of experience."


@pytest.mark.questions
def test_removes_italic_star():
    assert sanitize_generated_text("This was a *great* fit.") == "This was a great fit."


@pytest.mark.questions
def test_removes_underline():
    assert sanitize_generated_text("__Summary__: I build things.") == "Summary: I build things."


@pytest.mark.questions
def test_removes_italic_underscore():
    assert sanitize_generated_text("I led a _small_ team.") == "I led a small team."


@pytest.mark.questions
def test_removes_headers():
    text = "# Summary\nI am a backend engineer.\n## Skills\nPython, SQL."
    result = sanitize_generated_text(text)
    assert result == "Summary\nI am a backend engineer.\nSkills\nPython, SQL."


@pytest.mark.questions
def test_converts_star_bullets_to_dash_bullets():
    text = "* Built the payments service\n* Migrated the monolith"
    result = sanitize_generated_text(text)
    assert result == "- Built the payments service\n- Migrated the monolith"


@pytest.mark.questions
def test_dash_bullets_left_untouched():
    text = "- Built the payments service\n- Migrated the monolith"
    assert sanitize_generated_text(text) == text


@pytest.mark.questions
def test_star_bullet_not_confused_with_bold():
    text = "**Summary**\n* First point\nRegular text"
    result = sanitize_generated_text(text)
    assert result == "Summary\n- First point\nRegular text"


@pytest.mark.questions
def test_markdown_link_becomes_visible():
    text = "Check out [my portfolio](https://example.com/portfolio) for more."
    result = sanitize_generated_text(text)
    assert result == "Check out my portfolio (https://example.com/portfolio) for more."


@pytest.mark.questions
def test_em_and_en_dash_become_hyphen():
    text = "I worked there \u2014 mostly on backend \u2013 for three years."
    result = sanitize_generated_text(text)
    assert result == "I worked there - mostly on backend - for three years."


@pytest.mark.questions
def test_arrow_glyphs_become_ascii_arrow():
    text = "Revenue grew \u2192 doubled within a year."
    result = sanitize_generated_text(text)
    assert result == "Revenue grew -> doubled within a year."


@pytest.mark.questions
def test_existing_ascii_arrow_left_as_is():
    text = "Revenue grew -> doubled."
    assert sanitize_generated_text(text) == text


@pytest.mark.questions
def test_semicolon_becomes_colon():
    text = "I have three strengths; communication, ownership, and speed."
    result = sanitize_generated_text(text)
    assert result == "I have three strengths: communication, ownership, and speed."


@pytest.mark.questions
def test_combined_sanitization():
    text = "# About me\nI led projects \u2014 always **on time**; check [my site](https://example.com) \u2192 see more."
    result = sanitize_generated_text(text)
    assert result == "About me\nI led projects - always on time: check my site (https://example.com) -> see more."


@pytest.mark.questions
def test_none_and_empty_pass_through():
    assert sanitize_generated_text(None) is None
    assert sanitize_generated_text("") == ""