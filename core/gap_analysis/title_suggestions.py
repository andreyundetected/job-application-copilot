import html as html_module
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_SUGGESTION_RE = re.compile(r'<title_suggestion\s+id="(\d+)"\s*>(.*?)</title_suggestion>', re.DOTALL)


def suggest_title_changes(provider, targets: list[dict], job_posting_text: str) -> list[dict]:
    if not targets:
        return []

    prompt = _env.get_template("suggest_title_changes_prompt.jinja").render(
        targets=[{**target, "id": index} for index, target in enumerate(targets)],
        job_posting_text=job_posting_text,
    )
    raw_response = provider.call(
        system_prompt="You suggest truthful resume title rewordings. Output only tags.",
        user_prompt=prompt,
        max_tokens=2048,
        reasoning_effort="low",
    )

    suggestions = []
    for target_id, body in _SUGGESTION_RE.findall(raw_response or ""):
        index = int(target_id)
        if index >= len(targets):
            continue
        suggested = " ".join(html_module.unescape(body).split())
        target = targets[index]
        if not suggested or suggested == target["current"]:
            continue
        suggestions.append({**target, "suggested": suggested, "order": index})
    suggestions.sort(key=lambda item: item["order"])
    return suggestions