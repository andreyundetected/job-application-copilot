import json
from pathlib import Path

import pytest

PAGE_DIR = Path(__file__).resolve().parents[2] / "ui" / "automation_page"
APPLY_KEYS = ["title_main", "exp_titles", "summary", "skills"]


def _locale(name):
    return json.loads((PAGE_DIR / "locales" / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.ui
def test_automation_locales_have_the_same_keys():
    assert set(_locale("en")) == set(_locale("ru"))


@pytest.mark.ui
@pytest.mark.parametrize("lang", ["en", "ru"])
def test_every_resume_apply_target_has_label_and_tooltip(lang):
    strings = _locale(lang)

    for key in APPLY_KEYS:
        assert f"resume_apply_{key}" in strings
        assert f"resume_apply_{key}_tooltip" in strings


@pytest.mark.ui
def test_template_keeps_resume_and_letter_blocks_separate():
    template = (PAGE_DIR / "templates" / "automation.html").read_text(encoding="utf-8")

    assert 'id="auto_tailor_master_enabled"' in template
    assert 'id="auto_letter_master_enabled"' in template
    assert 'id="letter_note"' in template