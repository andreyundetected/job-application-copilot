import html as html_module
import re
from collections import Counter
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

SKILLS_LENGTH_BOUNDS = (0.5, 1.6)
TEXT_LENGTH_BOUNDS = (0.9, 1.25)
SUMMARY_LENGTH_BOUNDS = (0.9, 1.4)
MIN_RETAINED_WORDS = 0.8

_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _lines(text: str) -> str:
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def _plain(fragment: str) -> str:
    return _lines(html_to_text(fragment))


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
    escaped = html_module.escape(text).replace("\n", "<br>")
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
            parsed[int(number)] = {"items": [_lines(html_module.unescape(item)) for item in items if item.strip()]}
        else:
            parsed[int(number)] = {"text": _lines(html_module.unescape(body))}
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


def _units_text(units: list[dict]) -> str:
    parts = []
    for unit in units:
        if unit["list"]:
            parts.extend(unit["items"])
        else:
            parts.append(unit["text"])
    return "\n".join(parts)


def _numbers_preserved(old: str, new: str) -> bool:
    old_numbers = Counter(_NUM_RE.findall(old))
    new_numbers = Counter(_NUM_RE.findall(new))
    return all(new_numbers[number] >= count for number, count in old_numbers.items())


def _retained_ratio(old: str, new: str) -> float:
    old_words = Counter(word.lower() for word in _WORD_RE.findall(old))
    new_words = Counter(word.lower() for word in _WORD_RE.findall(new))
    total = sum(old_words.values())
    if not total:
        return 1.0
    kept = sum(min(count, new_words[word]) for word, count in old_words.items())
    return kept / total


def generate_block_fragments(
    provider,
    fragments: list[str],
    label: str,
    full_resume_text: str,
    job_posting_text: str,
    add_items: list[str],
    rephrase_items: list[dict],
    comment: str,
    kind: str = "exp_body",
) -> list[str]:
    units = build_units(fragments)
    original_words = count_words(units)

    prompt = _env.get_template("generate_block_prompt.jinja").render(
        label=label,
        kind=kind,
        units=units,
        words=original_words,
        full_resume_text=full_resume_text,
        job_posting_text=job_posting_text,
        add_items=add_items,
        rephrase_items=rephrase_items,
        comment=comment,
    )

    raw_response = provider.call(
        system_prompt="You align the terminology of one resume block with a job posting and change nothing else.",
        user_prompt=prompt,
        max_tokens=2048,
        reasoning_effort="low",
    )

    merged = merge_generated(fragments, units, parse_generated(raw_response))
    new_words = count_words(build_units(merged))
    bounds = {"skills": SKILLS_LENGTH_BOUNDS, "summary": SUMMARY_LENGTH_BOUNDS}
    low, high = bounds.get(kind, TEXT_LENGTH_BOUNDS)
    if original_words and not (low * original_words <= new_words <= high * original_words):
        raise ValueError(f"The model changed the block length too much ({original_words} -> {new_words} words)")
    if kind != "skills":
        old_text = _units_text(units)
        new_text = _units_text(build_units(merged))
        if not _numbers_preserved(old_text, new_text):
            raise ValueError("The model changed numbers or metrics in the block")
        if _retained_ratio(old_text, new_text) < MIN_RETAINED_WORDS:
            raise ValueError("The model rewrote too much of the block")
    return merged