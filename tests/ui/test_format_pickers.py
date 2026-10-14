from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "ui"


@pytest.mark.ui
@pytest.mark.parametrize(
    "path",
    ["tailoring_page/templates/tailor.html", "questions_page/templates/questions.html"],
)
def test_no_native_select_left_on_download_pages(path):
    assert "<select" not in (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.ui
def test_tailor_page_uses_format_pickers_and_reads_their_value():
    text = (ROOT / "tailoring_page/templates/tailor.html").read_text(encoding="utf-8")

    assert text.count('class="custom-select fmt-pick"') == 2
    assert "letterFormatSelect.dataset.value" in text
    assert "downloadFormatSelect.dataset.value" in text


@pytest.mark.ui
def test_letter_scheme_lane_is_hover_linked_to_the_letter_text():
    text = (ROOT / "tailoring_page/templates/tailor.html").read_text(encoding="utf-8")

    assert 'bindHot(lane, "letter")' in text
    assert 'setBlockHot("letter", true' in text