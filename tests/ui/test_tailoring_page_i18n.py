import json
import re
from pathlib import Path

import pytest

PAGE_DIR = Path(__file__).resolve().parents[2] / "ui" / "tailoring_page"
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


def _locale(name):
    return json.loads((PAGE_DIR / "locales" / f"{name}.json").read_text(encoding="utf-8"))


def _template():
    return (PAGE_DIR / "templates" / "tailor.html").read_text(encoding="utf-8")


def _router():
    return (PAGE_DIR / "router.py").read_text(encoding="utf-8")


@pytest.mark.ui
def test_both_locales_have_the_same_keys():
    assert set(_locale("en")) == set(_locale("ru"))


@pytest.mark.ui
def test_placeholders_match_between_locales():
    english = _locale("en")
    russian = _locale("ru")

    for key, value in english.items():
        assert set(re.findall(r"\{(\w+)\}", value)) == set(re.findall(r"\{(\w+)\}", russian[key])), key


@pytest.mark.ui
def test_every_key_used_in_the_template_exists():
    template = _template()
    used = set(re.findall(r"\{\{\s*t\.(\w+)", template)) | set(re.findall(r'tr\("(\w+)"', template))

    assert used - set(_locale("en")) == set()


@pytest.mark.ui
def test_no_dead_locale_keys():
    haystack = _template() + _router()

    dead = [key for key in _locale("en") if f'"{key}"' not in haystack and f"t.{key}" not in haystack]

    assert dead == []


@pytest.mark.ui
def test_tailor_template_has_no_hardcoded_russian():
    assert CYRILLIC_RE.search(_template()) is None