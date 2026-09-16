import pytest

from core.rendering.pdf_renderer import render_pdf


@pytest.mark.rendering
def test_render_pdf_creates_valid_file(tmp_path, sample_resume_content):
    output_path = tmp_path / "resume.pdf"

    result_path = render_pdf(sample_resume_content, str(output_path))

    assert output_path.exists()
    assert result_path == str(output_path)

    with open(output_path, "rb") as file:
        header = file.read(5)

    assert header == b"%PDF-"


@pytest.mark.rendering
def test_render_pdf_handles_minimal_content(tmp_path):
    minimal_content = {"name": "SAMPLE NAME"}
    output_path = tmp_path / "minimal.pdf"

    render_pdf(minimal_content, str(output_path))

    assert output_path.exists()