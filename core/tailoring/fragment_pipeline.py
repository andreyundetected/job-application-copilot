import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_CHANGE_RE = re.compile(
    r'<change\s+category="([^"]*)">\s*<find>(.*?)</find>\s*<replace>(.*?)</replace>\s*</change>',
    re.DOTALL,
)
_MESSAGE_RE = re.compile(r"<message>(.*?)</message>", re.DOTALL)


def _parse_changes(raw_response: str, level: str) -> list[dict]:
    changes = []
    for match in _CHANGE_RE.finditer(raw_response):
        category, original, replace = match.groups()
        original = original.strip()
        replace = replace.strip()
        if not original:
            continue
        changes.append(
            {
                "level": level,
                "change_type": category.strip(),
                "field_path": None,
                "target_ref": None,
                "original_text": original,
                "proposed_text": replace,
                "proposed_content": None,
            }
        )
    return changes


def propose_soft_fragment_changes(
    provider,
    job_posting_text: str,
    resume_html: str,
    matched_factors: list[dict],
    keywords: list[str] | None = None,
) -> list[dict]:
    template = _env.get_template("soft_html_prompt.jinja")
    prompt = template.render(
        job_posting_text=job_posting_text,
        resume_html=resume_html,
        matched_factors=matched_factors,
        keywords=keywords or [],
    )

    raw_response = provider.call(
        system_prompt="You propose terminology-only resume edits as exact find/replace pairs.",
        user_prompt=prompt,
    )

    return _parse_changes(raw_response, "soft")


def propose_medium_fragment_changes(
    provider,
    job_posting_text: str,
    resume_html: str,
    matched_factors: list[dict],
    keywords: list[str],
) -> list[dict]:
    template = _env.get_template("medium_html_prompt.jinja")
    prompt = template.render(
        job_posting_text=job_posting_text,
        resume_html=resume_html,
        matched_factors=matched_factors,
        keywords=keywords,
    )

    raw_response = provider.call(
        system_prompt="You propose keyword-weaving resume edits as exact find/replace pairs.",
        user_prompt=prompt,
    )

    return _parse_changes(raw_response, "medium")


def run_agent_fragment_turn(
    provider,
    job_posting_text: str,
    resume_html: str,
    matched_factors: list[dict],
    conversation_history: list[dict],
    user_message: str | None = None,
    keywords: list[str] | None = None,
) -> dict:
    template = _env.get_template("agent_html_prompt.jinja")
    prompt = template.render(
        job_posting_text=job_posting_text,
        resume_html=resume_html,
        matched_factors=matched_factors,
        conversation_history=conversation_history,
        user_message=user_message,
        keywords=keywords or [],
    )

    raw_response = provider.call(
        system_prompt="You are a careful, truthful resume tailoring copilot working with exact find/replace edits.",
        user_prompt=prompt,
    )

    message_match = _MESSAGE_RE.search(raw_response)
    message = message_match.group(1).strip() if message_match else ""

    return {
        "message": message,
        "changes": _parse_changes(raw_response, "custom"),
    }