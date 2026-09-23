import re

from core.parsing.html_to_text import html_to_text

_TAG_RE = re.compile(r'<(p|ul)\b[^>]*>.*?</\1>', re.DOTALL | re.IGNORECASE)
_STYLE_RE = re.compile(r'style="([^"]*)"')
_SIZE_RE = re.compile(r'font-size:\s*([\d.]+)pt')
_BOLD_RE = re.compile(r'font-weight:\s*bold')


def extract_ordered_blocks(html: str) -> list[dict]:
    blocks: list[dict] = []
    current = None

    for match in _TAG_RE.finditer(html or ""):
        fragment = match.group(0)
        tag = match.group(1).lower()

        if tag == "ul":
            if current is not None:
                current["body_fragments"].append(fragment)
            continue

        style_match = _STYLE_RE.search(fragment[: fragment.find(">") + 1])
        style = style_match.group(1) if style_match else ""
        size_match = _SIZE_RE.search(style)
        size = float(size_match.group(1)) if size_match else None
        is_bold = bool(_BOLD_RE.search(style))
        text = html_to_text(fragment).strip()

        if size == 16:
            continue

        if size == 12 and is_bold and text:
            if current is not None:
                blocks.append(current)
            upper = text.upper()
            if upper == "SUMMARY":
                field_path = "summary"
            elif upper == "SKILLS":
                field_path = "skills"
            else:
                field_path = f"section: {text}"
            current = {"field_path": field_path, "label": text, "body_fragments": []}
            continue

        if size == 11 and is_bold and text:
            if current is not None:
                blocks.append(current)
            company = text.split(" - ")[0].strip()
            current = {"field_path": f"experience: {company}", "label": text, "body_fragments": []}
            continue

        if current is not None:
            current["body_fragments"].append(fragment)

    if current is not None:
        blocks.append(current)

    result = []
    for block in blocks:
        body_html = "".join(block["body_fragments"])
        body_text = " ".join(html_to_text(body_html).split())
        result.append({"field_path": block["field_path"], "label": block["label"], "body_text": body_text})
    return result