import json
from functools import lru_cache
from pathlib import Path

from fastapi import Cookie

SUPPORTED_LANGUAGES = ["en", "ru"]
DEFAULT_LANGUAGE = "en"


@lru_cache(maxsize=None)
def _load_locale_file(path: str) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_page_strings(page_dir: str, lang: str) -> dict:
    if lang not in SUPPORTED_LANGUAGES:
        lang = DEFAULT_LANGUAGE

    common = _load_locale_file(f"ui/common/locales/{lang}.json")
    page = _load_locale_file(f"{page_dir}/locales/{lang}.json")

    return {**common, **page}


def get_language(lang: str | None = Cookie(default=None)) -> str:
    if lang in SUPPORTED_LANGUAGES:
        return lang
    return DEFAULT_LANGUAGE