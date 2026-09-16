import pytest

from core.rendering.txt_renderer import render_txt


@pytest.mark.rendering
def test_render_txt_creates_file(tmp_path, sample_resume_content):
    output_path = tmp_path / "resume.txt"

    result_path = render_txt(sample_resume_content, str(output_path))

    assert output_path.exists()
    assert result_path == str(output_path)


@pytest.mark.rendering
def test_render_txt_contains_expected_lines(tmp_path, sample_resume_content):
    output_path = tmp_path / "resume.txt"

    render_txt(sample_resume_content, str(output_path))

    text = output_path.read_text(encoding="utf-8")

    assert "SAMPLE NAME | Software Engineer" in text
    assert "Example Corp - Software Engineer" in text
    assert "Sample project" in text
    assert "- Sample bullet one" in text
    assert "SKILLS" in text