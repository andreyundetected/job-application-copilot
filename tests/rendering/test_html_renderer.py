import pytest

from core.rendering.html_renderer import render_html


@pytest.mark.rendering
def test_render_html_contains_name_and_data_paths(sample_resume_content):
    result = render_html(sample_resume_content)

    assert "SAMPLE NAME | Software Engineer" in result
    assert 'data-path="experience[0].company_role"' in result
    assert 'data-path="experience[0].content[2]"' in result


@pytest.mark.rendering
def test_render_html_applies_class_style(sample_resume_content):
    result = render_html(sample_resume_content, style={"classes": {"name": {"size": 20}}})

    assert "font-size:20pt" in result


@pytest.mark.rendering
def test_render_html_applies_path_override(sample_resume_content):
    result = render_html(
        sample_resume_content,
        style={"overrides": {"experience[0].company_role": {"bold": False}}},
    )

    company_role_start = result.index('data-path="experience[0].company_role"')
    surrounding = result[company_role_start : company_role_start + 200]

    assert "font-weight:bold" not in surrounding


@pytest.mark.rendering
def test_render_html_renders_bullet_list_as_ul(sample_resume_content):
    result = render_html(sample_resume_content)

    assert "<ul" in result
    assert "<li>Sample bullet one</li>" in result