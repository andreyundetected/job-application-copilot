import html
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import config

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

SYSTEM_PROMPT = (
    "You are the job candidate writing your own cover letter. You write like a plain-spoken senior engineer, "
    "in your own voice, only from your own materials. You never invent facts and you follow the candidate's instructions exactly."
)

_LETTER_RE = re.compile(r"<letter>(.*?)(?:</letter>|\Z)", re.DOTALL)
_PLAN_RE = re.compile(r"<plan>(.*?)(?:</plan>|\Z)", re.DOTALL)


def _extract(raw: str | None) -> tuple[str, str]:
    raw = raw or ""
    plan_match = _PLAN_RE.search(raw)
    plan = html.unescape(plan_match.group(1)).strip() if plan_match else ""
    letter_match = _LETTER_RE.search(raw)
    if letter_match:
        body = letter_match.group(1)
    elif plan_match:
        body = raw[plan_match.end():]
    else:
        body = raw
    return plan, html.unescape(body).strip()


def _language_for(job_posting_text: str) -> str:
    letters = [char for char in (job_posting_text or "") if char.isalpha()]
    if letters:
        cyrillic = sum(1 for char in letters if "\u0400" <= char <= "\u04ff")
        if cyrillic / len(letters) > 0.3:
            return "Russian"
    return "the language of the job posting (English if unsure)"


def generate_cover_letter(
    provider,
    company,
    job_title,
    job_posting_text,
    resume_text,
    linkedin_text,
    extra_info,
    topics,
    not_proven,
    notes="",
    contacts=None,
    candidate_name="",
    writing_preferences="",
    temperature=None,
    comment="",
    previous_letter="",
):
    template = _env.get_template("cover_letter_prompt.jinja")
    prompt = template.render(
        company=company,
        job_title=job_title,
        language=_language_for(job_posting_text),
        job_posting_text=job_posting_text,
        resume_text=resume_text,
        linkedin_text=linkedin_text or "",
        extra_info=extra_info or "",
        topics=list(topics or []),
        not_proven=list(not_proven or []),
        notes=(notes or "").strip(),
        comment=(comment or "").strip(),
        previous_letter=(previous_letter or "").strip(),
        writing_preferences=(writing_preferences or "").strip(),
        contacts=list(contacts or []),
        candidate_name=(candidate_name or "").strip(),
    )
    value = config.LETTER_TEMPERATURE if temperature is None else temperature
    raw = provider.call(system_prompt=SYSTEM_PROMPT, user_prompt=prompt, max_tokens=3000, temperature=value)
    _, text = _extract(raw)
    if not text:
        raise ValueError("The model returned an empty letter")
    return text