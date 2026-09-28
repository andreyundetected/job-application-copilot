import re
import uuid

from core.parsing.html_to_text import html_to_text

_TAG_RE = re.compile(r"<(/?)([a-zA-Z][a-zA-Z0-9]*)\b([^>]*?)(/?)>")
_VOID_TAGS = {"br", "hr", "img", "input", "meta", "link", "wbr"}
_EID_ATTR_RE = re.compile(r'\sdata-eid="([^"]*)"')
_BLK_ATTR_RE = re.compile(r'\sdata-blk="[^"]*"')
_CLASS_ATTR_RE = re.compile(r'\sclass="([^"]*)"')

TITLE_KINDS = ("title_main", "exp_title")


def new_eid() -> str:
    return "e" + uuid.uuid4().hex[:8]


def _strip_blk_classes(match) -> str:
    kept = [name for name in match.group(1).split() if not name.startswith("blk-")]
    return f' class="{" ".join(kept)}"' if kept else ""


def clean_transient_attrs(html: str) -> str:
    html = _BLK_ATTR_RE.sub("", html or "")
    return _CLASS_ATTR_RE.sub(_strip_blk_classes, html)


def _make_element(fragment: str) -> dict:
    match = _TAG_RE.match(fragment)
    eid_match = _EID_ATTR_RE.search(match.group(3)) if match else None
    return {
        "html": fragment,
        "tag": match.group(2).lower() if match else "",
        "eid": eid_match.group(1) if eid_match else None,
    }


def split_top_level(html: str) -> list[dict]:
    html = html or ""
    elements: list[dict] = []
    depth = 0
    start = 0
    cursor = 0

    for match in _TAG_RE.finditer(html):
        closing = bool(match.group(1))
        name = match.group(2).lower()
        self_closing = bool(match.group(4)) or name in _VOID_TAGS

        if depth == 0:
            if closing:
                continue
            gap = html[cursor : match.start()]
            if gap.strip():
                elements.append(_make_element(f"<p>{gap.strip()}</p>"))
            if self_closing:
                cursor = match.end()
                continue
            depth = 1
            start = match.start()
            continue

        if self_closing:
            continue
        if closing:
            depth -= 1
            if depth == 0:
                elements.append(_make_element(html[start : match.end()]))
                cursor = match.end()
        else:
            depth += 1

    if depth > 0:
        elements.append(_make_element(html[start:]))
    elif html[cursor:].strip():
        elements.append(_make_element(f"<p>{html[cursor:].strip()}</p>"))

    return elements


def join_elements(elements: list[dict]) -> str:
    return "\n".join(element["html"] for element in elements)


def set_eid(fragment: str, eid: str) -> str:
    match = _TAG_RE.match(fragment)
    if not match:
        return fragment
    attrs = match.group(3)
    if _EID_ATTR_RE.search(attrs):
        attrs = _EID_ATTR_RE.sub(f' data-eid="{eid}"', attrs, count=1)
    else:
        attrs = f'{attrs} data-eid="{eid}"'
    return f"<{match.group(2)}{attrs}>{fragment[match.end():]}"


def element_text(fragment: str) -> str:
    return " ".join(html_to_text(fragment).split())


def _rebuild_blocks(blocks: list[dict] | None, assignment: dict, ordered: list[str]) -> list[dict]:
    position = {eid: index for index, eid in enumerate(ordered)}
    rebuilt = []
    for block in blocks or []:
        ids = [eid for eid in ordered if assignment.get(eid) == block["id"]]
        if not ids:
            continue
        rebuilt.append({**block, "element_ids": ids})
    rebuilt.sort(key=lambda item: position[item["element_ids"][0]])
    return rebuilt


def normalize_elements(html: str, blocks: list[dict] | None) -> tuple[str, list[dict]]:
    elements = split_top_level(clean_transient_attrs(html))

    assignment: dict[str, str] = {}
    for block in blocks or []:
        for eid in block.get("element_ids", []):
            assignment.setdefault(eid, block["id"])

    seen: set[str] = set()
    previous_block = None
    for element in elements:
        eid = element["eid"]
        if not eid or eid in seen:
            eid = new_eid()
            element["html"] = set_eid(element["html"], eid)
            element["eid"] = eid
            if previous_block is not None:
                assignment[eid] = previous_block
        seen.add(eid)
        previous_block = assignment.get(eid)

    ordered = [element["eid"] for element in elements]
    return join_elements(elements), _rebuild_blocks(blocks, assignment, ordered)


def block_fragments(html: str, block: dict) -> list[str]:
    by_id = {element["eid"]: element["html"] for element in split_top_level(html)}
    return [by_id[eid] for eid in block["element_ids"] if eid in by_id]


def replace_block_elements(html: str, block: dict, new_fragments: list[str]) -> tuple[str, dict]:
    elements = split_top_level(html)
    block_ids = set(block["element_ids"])
    indexes = [index for index, element in enumerate(elements) if element["eid"] in block_ids]
    if not indexes:
        raise ValueError("Block not found in resume")

    old_ids = [elements[index]["eid"] for index in indexes]
    used = {element["eid"] for index, element in enumerate(elements) if index not in indexes and element["eid"]}

    prepared = []
    for position, fragment in enumerate(new_fragments):
        element = _make_element(fragment)
        eid = element["eid"]
        if not eid or eid in used:
            candidate = old_ids[position] if position < len(old_ids) else None
            eid = candidate if candidate and candidate not in used else new_eid()
            element["html"] = set_eid(element["html"], eid)
            element["eid"] = eid
        used.add(eid)
        prepared.append(element)

    result = []
    inserted = False
    skip = set(indexes)
    for index, element in enumerate(elements):
        if index == indexes[0] and not inserted:
            result.extend(prepared)
            inserted = True
        if index in skip:
            continue
        result.append(element)

    new_block = {**block, "element_ids": [element["eid"] for element in prepared]}
    return join_elements(result), new_block


def body_block_texts(html: str, blocks: list[dict]) -> list[dict]:
    by_id = {element["eid"]: element for element in split_top_level(html)}
    titles = {block.get("company"): block for block in blocks if block["kind"] == "exp_title"}
    result = []
    for block in blocks:
        if block["kind"] in TITLE_KINDS:
            continue
        parts = [html_to_text(by_id[eid]["html"]) for eid in block["element_ids"] if eid in by_id]
        text = "\n".join(part for part in parts if part)
        if not text:
            continue
        label = block["label"]
        if block["kind"] == "exp_body":
            title_block = titles.get(block.get("company"))
            if title_block and title_block.get("role"):
                label = f'{block["company"]} - {title_block["role"]}'
        result.append({"field_path": block["field_path"], "kind": block["kind"], "label": label, "text": text})
    return result


def build_title_targets(html: str, blocks: list[dict]) -> list[dict]:
    by_id = {element["eid"]: element for element in split_top_level(html)}
    targets = []
    for block in blocks:
        if block["kind"] == "title_main":
            for line, eid in enumerate(block["element_ids"]):
                element = by_id.get(eid)
                text = element_text(element["html"]) if element else ""
                if text:
                    targets.append(
                        {"key": block["field_path"], "kind": "main", "company": "", "line": line, "current": text}
                    )
        elif block["kind"] == "exp_title" and block.get("role"):
            targets.append(
                {
                    "key": block["field_path"],
                    "kind": "experience",
                    "company": block.get("company", ""),
                    "line": 0,
                    "current": block["role"],
                }
            )
    return targets