from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core.parsing.html_like_parser import parse_html_like

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_VALID_CATEGORIES = {"skill", "tool", "title", "certification", "methodology", "domain"}
_VALID_PRIORITIES = {"required", "preferred"}


def render_keyword_extraction_prompt(job_posting_text: str) -> str:
    template = _env.get_template("keyword_extraction_prompt.jinja")
    return template.render(job_posting_text=job_posting_text)


def extract_tailoring_keywords(provider, job_posting_text: str) -> list[dict]:
    prompt = render_keyword_extraction_prompt(job_posting_text)

    raw_response = provider.call(
        system_prompt="You extract ATS-style resume keywords from a job posting, categorized and prioritized.",
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)

    keywords = []
    for item in parsed.get("keyword", []):
        if isinstance(item, str):
            continue

        text = (item.get("text") or "").strip()
        if not text:
            continue

        category = (item.get("category") or "domain").strip().lower()
        if category not in _VALID_CATEGORIES:
            category = "domain"

        priority = (item.get("priority") or "preferred").strip().lower()
        if priority not in _VALID_PRIORITIES:
            priority = "preferred"

        keywords.append({"text": text, "category": category, "priority": priority})

    return keywords