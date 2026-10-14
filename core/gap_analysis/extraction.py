import logging
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_KW_RE = re.compile(r"<kw\s+(.*?)/>")
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')

VALID_PRIORITIES = {"required", "preferred"}


def parse_keywords(raw: str) -> list[dict]:
    items = []
    for match in _KW_RE.finditer(raw or ""):
        attrs = dict(_ATTR_RE.findall(match.group(1)))
        text = attrs.get("text", "").strip()
        if not text:
            continue
        level = attrs.get("level", "").strip().lower()
        items.append(
            {
                "text": text,
                "category": attrs.get("kind", "").strip().lower() or "skill",
                "priority": level if level in VALID_PRIORITIES else "required",
                "tier": attrs.get("tier", "").strip().upper() or None,
            }
        )
    return items


def extract_keywords(provider, job_text: str, max_attempts: int = 3) -> list[dict]:
    prompt = _env.get_template("extract_keywords_prompt.jinja").render(job_posting_text=job_text)

    for attempt in range(max_attempts):
        try:
            raw = provider.call(
                system_prompt="You extract resume keywords from job postings and output only <kw /> tags.",
                user_prompt=prompt,
                max_tokens=2048,
            )
            items = parse_keywords(raw)
        except Exception as error:
            logger.warning("[keywords] extraction attempt %s failed: %s", attempt + 1, error)
            items = []
        if items:
            return items

    return []