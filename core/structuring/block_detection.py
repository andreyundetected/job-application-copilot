import re
import uuid
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core.parsing.html_blocks import element_text, split_top_level
from core.parsing.html_to_text import html_to_text

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

VALID_KINDS = {"title_main", "summary", "skills", "exp_title", "exp_body"}
MERGEABLE_KINDS = {"summary", "skills", "exp_body"}

_BLOCK_RE = re.compile(r"<block\s+([^>]*?)/?>", re.DOTALL)
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
_SIZE_RE = re.compile(r"font-size:\s*([\d.]+)pt")
_LI_RE = re.compile(r"<li\b[^>]*>(.*?)</li>", re.DOTALL)


def compute_field_path(kind: str, company: str) -> str:
    if kind == "title_main":
        return "title:main"
    if kind == "summary":
        return "summary"
    if kind == "skills":
        return "skills"
    if kind == "exp_title":
        return f"title:{company}"
    return f"experience: {company}"


def default_label(kind: str, company: str) -> str:
    if kind == "title_main":
        return "Title"
    if kind == "summary":
        return "Summary"
    if kind == "skills":
        return "Skills"
    return company


def finalize_blocks(blocks: list[dict]) -> list[dict]:
    used: dict[str, int] = {}
    result = []
    for block in blocks:
        kind = block["kind"]
        company = (block.get("company") or "").strip()
        label = (block.get("label") or "").strip()
        if kind in ("exp_title", "exp_body") and not company:
            company = label or "Company"
        base = compute_field_path(kind, company)
        count = used.get(base, 0) + 1
        used[base] = count
        field_path = base if count == 1 else f"{base} #{count}"
        result.append(
            {
                **block,
                "company": company,
                "role": (block.get("role") or "").strip(),
                "label": default_label(kind, company),
                "field_path": field_path,
            }
        )
    return result


def merge_adjacent_blocks(blocks: list[dict], position: dict[str, int]) -> list[dict]:
    merged: list[dict] = []
    for block in blocks:
        previous = merged[-1] if merged else None
        can_merge = (
            previous is not None
            and block["kind"] in MERGEABLE_KINDS
            and previous["kind"] == block["kind"]
            and (previous.get("company") or "").strip().lower() == (block.get("company") or "").strip().lower()
            and position[block["element_ids"][0]] == position[previous["element_ids"][-1]] + 1
        )
        if can_merge:
            previous["element_ids"] = previous["element_ids"] + block["element_ids"]
        else:
            merged.append({**block, "element_ids": list(block["element_ids"])})
    return merged


def _describe(element: dict) -> dict:
    fragment = element["html"]
    size = _SIZE_RE.search(fragment)
    traits = [
        f"{size.group(1)}pt" if size else "",
        "bold" if "font-weight:bold" in fragment else "",
        "centered" if "text-align:center" in fragment else "",
    ]
    if element["tag"] in ("ul", "ol"):
        items = [" ".join(html_to_text(item).split()) for item in _LI_RE.findall(fragment)]
        preview = f"list of {len(items)}: " + " | ".join(item[:80] for item in items[:3])
    else:
        preview = element_text(fragment)[:200]
    return {"eid": element["eid"], "traits": ", ".join(part for part in traits if part), "preview": preview}


def parse_blocks(raw: str, ordered_eids: list[str]) -> list[dict]:
    position = {eid: index for index, eid in enumerate(ordered_eids)}
    taken: set[str] = set()
    blocks = []

    for match in _BLOCK_RE.finditer(raw or ""):
        attrs = dict(_ATTR_RE.findall(match.group(1)))
        kind = attrs.get("kind", "").strip()
        start = attrs.get("from", "").strip()
        end = attrs.get("to", start).strip()
        if kind not in VALID_KINDS or start not in position or end not in position:
            continue
        low, high = sorted((position[start], position[end]))
        ids = ordered_eids[low : high + 1]
        if any(eid in taken for eid in ids):
            continue
        taken.update(ids)
        blocks.append(
            {
                "id": "b" + uuid.uuid4().hex[:8],
                "kind": kind,
                "label": attrs.get("label", ""),
                "company": attrs.get("company", ""),
                "role": attrs.get("role", ""),
                "element_ids": ids,
            }
        )

    blocks.sort(key=lambda block: position[block["element_ids"][0]])
    return finalize_blocks(merge_adjacent_blocks(blocks, position))


def detect_blocks(provider, html: str) -> list[dict]:
    elements = [element for element in split_top_level(html) if element["eid"]]
    if not elements:
        return []

    prompt = _env.get_template("block_detection_prompt.jinja").render(
        elements=[_describe(element) for element in elements]
    )
    raw_response = provider.call(
        system_prompt="You segment a resume into working blocks. Output only block tags.",
        user_prompt=prompt,
        max_tokens=4096,
        reasoning_effort="medium",
    )

    return parse_blocks(raw_response, [element["eid"] for element in elements])