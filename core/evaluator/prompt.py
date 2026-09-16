from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_evaluator_prompt(
    job_posting_text: str,
    resume_text: str,
    linkedin_text: str,
    blockers: list[str],
    scoring_factors: list[dict] | None = None,
    contacts: list[str] | None = None,
    extra_info: str | None = None,
    language: str = "en",
) -> str:
    # language is accepted for future use (prompt output translation is
    # intentionally disabled for now) but not applied yet.
    template = _env.get_template("evaluator_prompt.jinja")
    return template.render(
        job_posting_text=job_posting_text,
        resume_text=resume_text,
        linkedin_text=linkedin_text,
        blockers=blockers,
        scoring_factors=scoring_factors or [],
        contacts=contacts or [],
        extra_info=extra_info or "",
    )


def render_quick_extract_prompt(job_posting_text: str) -> str:
    template = _env.get_template("quick_extract_prompt.jinja")
    return template.render(job_posting_text=job_posting_text)