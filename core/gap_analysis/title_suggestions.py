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

_SUGGESTION_RE = re.compile(r"<title_suggestion\s+(.*?)>(.*?)</title_suggestion>", re.DOTALL)
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')

WORK_LIMIT = 700


def with_work_context(targets: list[dict], block_texts: list[dict], limit: int = WORK_LIMIT) -> list[dict]:
    by_path = {block["field_path"]: block for block in block_texts}
    result = []
    for target in targets:
        key = target.get("key", "")
        if key == "title:main":
            path = "summary"
        elif key.startswith("title:"):
            path = "experience: " + key[len("title:") :]
        else:
            path = ""
        block = by_path.get(path)
        work = " ".join((block["text"] if block else "").split())[:limit]
        result.append({**target, "work": work})
    return result


def suggest_title_changes(
    provider,
    targets: list[dict],
    job_posting_text: str,
    comments: dict | None = None,
    job_title: str = "",
    rejections: list[dict] | None = None,
) -> list[dict]:
    comments = comments or {}
    if not targets:
        return []

    prompt = _env.get_template("suggest_title_changes_prompt.jinja").render(
        targets=[
            {**target, "id": index, "comment": comments.get(target["key"], "")}
            for index, target in enumerate(targets)
        ],
        job_posting_text=job_posting_text,
        job_title=job_title,
        rejections=rejections or [],
    )
    raw_response = provider.call(
        system_prompt="You suggest truthful resume title rewordings. Output only tags.",
        user_prompt=prompt,
        max_tokens=2048,
    )

    suggestions = []
    seen: set[int] = set()
    for attrs_raw, body in _SUGGESTION_RE.findall(raw_response or ""):
        attrs = {name: html_module.unescape(value) for name, value in _ATTR_RE.findall(attrs_raw)}
        identifier = attrs.get("id", "")
        if not identifier.isdigit():
            continue
        index = int(identifier)
        if index >= len(targets) or index in seen:
            continue
        seen.add(index)

        target = {key: value for key, value in targets[index].items() if key != "work"}
        text = " ".join(html_module.unescape(body).split())
        status = attrs.get("status", "").strip().lower()
        changed = bool(text) and text != target["current"] and status != "same"
        suggestions.append(
            {
                **target,
                "suggested": text if changed else target["current"],
                "changed": changed,
                "reason": attrs.get("reason", "").strip(),
                "order": index,
            }
        )

    suggestions.sort(key=lambda item: item["order"])
    return suggestions