import html as html_module
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core.parsing.html_to_text import html_to_text

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_OPEN_RE = re.compile(r"<([a-zA-Z0-9]+)([^>]*)>")
_LI_RE = re.compile(r"(<li\b[^>]*>)(.*?)</li>", re.DOTALL)
_SPAN_RE = re.compile(r'<span\b[^>]*style="([^"]*)"[^>]*>(.*?)</span>', re.DOTALL)
_EL_RE = re.compile(r'<el\s+n="(\d+)"[^>]*>(.*?)</el>', re.DOTALL)
_OUT_LI_RE = re.compile(r"<li>(.*?)</li>", re.DOTALL)

MIN_LENGTH_RATIO = 0.5
MAX_LENGTH_RATIO = 1.6


def _plain(fragment: str) -> str:
    return " ".join(html_to_text(fragment).split())


def build_units(fragments: list[str]) -> list[dict]:
    units = []
    for index, fragment in enumerate(fragments):
        match = _OPEN_RE.match(fragment)
        tag = match.group(1).lower() if match else "p"
        if tag in ("ul", "ol"):
            items = [_plain(inner) for _, inner in _LI_RE.findall(fragment)]
            units.append({"n": index, "list": True, "items": items})
        else:
            units.append({"n": index, "list": False, "text": _plain(fragment)})
    return units


def _dominant_style(inner_html: str) -> str:
    best_style = ""
    best_length = -1
    for style, content in _SPAN_RE.findall(inner_html):
        length = len(_plain(content))
        if length > best_length:
            best_style, best_length = style, length
    return best_style


def _wrap(style: str, text: str) -> str:
    escaped = html_module.escape(text)
    if style:
        return f'<span style="{style}">{escaped}</span>'
    return escaped


def rebuild_paragraph(fragment: str, new_text: str) -> str:
    match = _OPEN_RE.match(fragment)
    inner = fragment[match.end() : fragment.rfind("</")]
    return f"<{match.group(1)}{match.group(2)}>{_wrap(_dominant_style(inner), new_text)}</{match.group(1)}>"


def rebuild_list(fragment: str, new_items: list[str]) -> str:
    match = _OPEN_RE.match(fragment)
    originals = list(_LI_RE.finditer(fragment))
    rows = []
    for index, text in enumerate(new_items):
        source = originals[min(index, len(originals) - 1)] if originals else None
        if source is not None and index < len(originals) and _plain(source.group(2)) == text:
            rows.append(source.group(0))
            continue
        opening = source.group(1) if source is not None else "<li>"
        style = _dominant_style(source.group(2)) if source is not None else ""
        rows.append(f"{opening}{_wrap(style, text)}</li>")
    return f"<{match.group(1)}{match.group(2)}>{''.join(rows)}</{match.group(1)}>"


def parse_generated(raw: str) -> dict[int, dict]:
    parsed: dict[int, dict] = {}
    for number, body in _EL_RE.findall(raw or ""):
        items = _OUT_LI_RE.findall(body)
        if items:
            parsed[int(number)] = {"items": [" ".join(html_module.unescape(item).split()) for item in items if item.strip()]}
        else:
            parsed[int(number)] = {"text": " ".join(html_module.unescape(body).split())}
    return parsed


def merge_generated(fragments: list[str], units: list[dict], parsed: dict[int, dict]) -> list[str]:
    result = []
    for fragment, unit in zip(fragments, units):
        generated = parsed.get(unit["n"])
        if generated is None:
            result.append(fragment)
            continue
        if unit["list"]:
            items = generated.get("items")
            if not items or items == unit["items"]:
                result.append(fragment)
            else:
                result.append(rebuild_list(fragment, items))
        else:
            text = generated.get("text")
            if not text or text == unit["text"]:
                result.append(fragment)
            else:
                result.append(rebuild_paragraph(fragment, text))
    return result


def count_words(units: list[dict]) -> int:
    total = 0
    for unit in units:
        if unit["list"]:
            total += sum(len(item.split()) for item in unit["items"])
        else:
            total += len(unit["text"].split())
    return total


def generate_block_fragments(
    provider,
    fragments: list[str],
    label: str,
    full_resume_text: str,
    job_posting_text: str,
    included_items: list[str],
    keep_items: list[str],
    comment: str,
) -> list[str]:
    units = build_units(fragments)
    original_words = count_words(units)

    prompt = _env.get_template("generate_block_prompt.jinja").render(
        label=label,
        units=units,
        words=original_words,
        full_resume_text=full_resume_text,
        job_posting_text=job_posting_text,
        included_items=included_items,
        keep_items=keep_items,
        comment=comment,
    )

    raw_response = provider.call(
        system_prompt="You rewrite one block of a resume with minimal, truthful edits and keep its structure intact.",
        user_prompt=prompt,
        max_tokens=2048,
        reasoning_effort="low",
    )

    merged = merge_generated(fragments, units, parse_generated(raw_response))
    new_words = count_words(build_units(merged))
    if original_words and not (MIN_LENGTH_RATIO * original_words <= new_words <= MAX_LENGTH_RATIO * original_words):
        raise ValueError(f"The model changed the block length too much ({original_words} -> {new_words} words)")
    return merged