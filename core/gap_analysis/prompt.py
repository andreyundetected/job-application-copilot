from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_extract_requirements_prompt(job_posting_text: str) -> str:
    template = _env.get_template("extract_requirements_prompt.jinja")
    return template.render(job_posting_text=job_posting_text)


def render_extract_resume_items_section_prompt(
    section_label: str,
    section_text: str,
    max_items: int,
) -> str:
    template = _env.get_template("extract_resume_items_prompt.jinja")
    return template.render(section_label=section_label, section_text=section_text, max_items=max_items)


def render_match_gap_items_prompt(requirements: list[dict], resume_items: list[dict]) -> str:
    template = _env.get_template("match_gap_items_prompt.jinja")
    return template.render(requirements=requirements, resume_items=resume_items)


def render_suggest_title_prompt(
    main_title: str, experience_titles: list[dict], job_posting_text: str
) -> str:
    template = _env.get_template("suggest_title_prompt.jinja")
    return template.render(
        main_title=main_title, experience_titles=experience_titles, job_posting_text=job_posting_text
    )