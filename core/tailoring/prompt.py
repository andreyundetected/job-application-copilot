from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_soft_tailoring_prompt(
    job_posting_text: str,
    resume_content: dict,
    matched_factors: list[dict],
) -> str:
    template = _env.get_template("soft_prompt.jinja")
    return template.render(
        job_posting_text=job_posting_text,
        resume_content=resume_content,
        matched_factors=matched_factors,
    )


def render_medium_tailoring_prompt(
    job_posting_text: str,
    resume_content: dict,
    matched_factors: list[dict],
    keywords: list[str],
) -> str:
    template = _env.get_template("medium_prompt.jinja")
    return template.render(
        job_posting_text=job_posting_text,
        resume_content=resume_content,
        matched_factors=matched_factors,
        keywords=keywords,
    )