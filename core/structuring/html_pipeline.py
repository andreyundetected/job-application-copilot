from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core.parsing.html_sanitize import close_unclosed_tags

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text.strip()


def structure_resume_to_html(provider, raw_text: str) -> str:
    template = _env.get_template("resume_html_prompt.jinja")
    prompt = template.render(raw_text=raw_text)

    raw_response = provider.call(
        system_prompt="You convert raw resume text into clean styled HTML without adding, removing, or reordering content.",
        user_prompt=prompt,
    )

    return close_unclosed_tags(_strip_code_fences(raw_response))