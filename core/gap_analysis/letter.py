import html
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_LETTER_RE = re.compile(r"<letter>(.*?)</letter>", re.DOTALL)

MIN_WORDS = 200
MAX_WORDS = 400

_BAD_OPENER_RE = re.compile(
    r"^\s*(?:(?:dear|hello|hi|здравствуйте|добрый день)[^\n]*\n+)?\s*"
    r"(?:i am writing|i'm writing|i am applying|i'm applying|i would like to apply|"
    r"i am excited to|i am thrilled|please accept|я пишу|я хочу откликнуться|"
    r"я хотел бы откликнуться|хочу откликнуться|меня зовут)",
    re.IGNORECASE,
)
_TO_WHOM_RE = re.compile(r"to whom it may concern", re.IGNORECASE)
_FILLER_RE = re.compile(
    r"\b(thrilled|passionate|synergy|leverage|dynamic|fast-paced|team player|hard-working|results-driven)\b",
    re.IGNORECASE,
)


def validate_letter(text: str) -> list[str]:
    issues = []
    words = len(text.split())
    if words < MIN_WORDS:
        issues.append(f"The letter is too short ({words} words). Write 250 to 350 words.")
    elif words > MAX_WORDS:
        issues.append(f"The letter is too long ({words} words). Cut it to 250 to 350 words.")
    if _BAD_OPENER_RE.search(text):
        issues.append(
            "The first sentence is a generic opener about applying or writing. "
            "Start with the substance: why this work fits and the strongest matching fact."
        )
    if _TO_WHOM_RE.search(text):
        issues.append('Do not use "To Whom It May Concern". Use "Dear Hiring Team," when no name is given.')
    filler = sorted({match.group(1).lower() for match in _FILLER_RE.finditer(text)})
    if filler:
        issues.append("Remove empty buzzwords: " + ", ".join(filler) + ".")
    return issues


def _extract(raw: str | None) -> str:
    match = _LETTER_RE.search(raw or "")
    text = html.unescape(match.group(1) if match else (raw or "")).strip()
    return "\n".join(line.rstrip() for line in text.splitlines())


def generate_cover_letter(
    provider,
    company: str,
    job_title: str,
    job_posting_text: str,
    resume_text: str,
    linkedin_text: str,
    extra_info: str | None,
    topics: list[str],
    not_proven: list[str],
    notes: str = "",
    contacts: list[str] | None = None,
    max_attempts: int = 2,
) -> str:
    template = _env.get_template("cover_letter_prompt.jinja")
    fixes: list[str] = []
    best = ""

    for _ in range(max(1, max_attempts)):
        prompt = template.render(
            company=company,
            job_title=job_title,
            job_posting_text=job_posting_text,
            resume_text=resume_text,
            linkedin_text=linkedin_text or "",
            extra_info=extra_info or "",
            topics=topics,
            not_proven=not_proven,
            notes=notes,
            contacts=contacts or [],
            fixes=fixes,
        )
        raw = provider.call(
            system_prompt="You write truthful, specific cover letters from the candidate's own materials.",
            user_prompt=prompt,
            max_tokens=2048,
        )
        text = _extract(raw)
        if not text:
            fixes = ["The previous answer was empty. Return the full letter inside the letter tag."]
            continue
        best = text
        fixes = validate_letter(text)
        if not fixes:
            return text

    if not best:
        raise ValueError("The model returned an empty letter")
    return best