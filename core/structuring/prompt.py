from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


_LANGUAGE_NAMES = {
    "en": "English",
    "ru": "Russian",
}


def render_structure_prompt(raw_text: str, source_label: str, language: str = "en") -> str:
    template = _env.get_template("structure_prompt.jinja")
    return template.render(
        raw_text=raw_text,
        source_label=source_label,
        output_language=_LANGUAGE_NAMES.get(language, "English"),
    )