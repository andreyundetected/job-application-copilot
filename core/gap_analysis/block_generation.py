from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)


def generate_block_content(
    provider,
    resume_html: str,
    job_posting_text: str,
    field_path: str,
    current_text: str,
    included_items: list[str],
    comment: str,
    keep_items: list[str] | None = None,
) -> dict:
    template = _env.get_template("generate_block_prompt.jinja")
    prompt = template.render(
        resume_html=resume_html,
        job_posting_text=job_posting_text,
        field_path=field_path,
        current_text=current_text,
        included_items=included_items,
        comment=comment,
        keep_items=keep_items or [],
    )

    raw_response = provider.call(
        system_prompt="You rewrite one section of a resume to include specific skills, grounded only in the candidate's real background.",
        user_prompt=prompt,
        max_tokens=2048,
        reasoning_effort="low",
    )

    import re

    new_match = re.search(r"<new>(.*?)</new>", raw_response, re.DOTALL)

    return {"new_text": new_match.group(1).strip() if new_match else ""}