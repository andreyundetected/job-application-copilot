import html

from core.rendering.base import color_hex, merge_style, resolve_style


def _esc(text: str) -> str:
    return html.escape(text or "")


def _inline_style(resolved: dict, font_name: str) -> str:
    parts = [
        f"font-family:'{font_name}',sans-serif",
        f"font-size:{resolved.get('size', 10)}pt",
        f"color:{color_hex(resolved.get('color', 'black'))}",
    ]
    if resolved.get("bold"):
        parts.append("font-weight:bold")
    if resolved.get("italic"):
        parts.append("font-style:italic")
    return ";".join(parts)


def _styled_div(text, class_name, style, path=None, extra_style=""):
    resolved = resolve_style(style, class_name, path)
    css = _inline_style(resolved, style["font_name"])
    if extra_style:
        css += ";" + extra_style
    path_attr = f' data-path="{path}"' if path else ""
    return f'<div class="resume-{class_name}"{path_attr} style="{css}">{_esc(text)}</div>'


def _content_blocks_html(blocks, path_prefix, style):
    html_parts = []
    for index, block in enumerate(blocks or []):
        block_path = f"{path_prefix}[{index}]"
        block_type = block.get("type")

        if block_type == "heading":
            html_parts.append(_styled_div(block.get("text", ""), "heading", style, path=block_path))
        elif block_type == "bullet_list":
            resolved = resolve_style(style, "bullet", block_path)
            css = _inline_style(resolved, style["font_name"])
            items_html = "".join(f"<li>{_esc(item)}</li>" for item in block.get("items", []))
            html_parts.append(
                f'<ul class="resume-bullet" data-path="{block_path}" style="{css}">{items_html}</ul>'
            )
        else:
            html_parts.append(_styled_div(block.get("text", ""), "body", style, path=block_path))

    return "".join(html_parts)


def render_html(content: dict, style: dict | None = None) -> str:
    style = merge_style(style)
    parts = ['<div class="resume-document">']

    parts.append(_styled_div(content["name"], "name", style, extra_style="text-align:center"))

    if content.get("contacts"):
        contacts_text = " | ".join(content["contacts"])
        parts.append(_styled_div(contacts_text, "contacts", style, extra_style="text-align:center"))

    if content.get("summary"):
        parts.append(_styled_div("SUMMARY", "section_header", style))
        parts.append(_styled_div(content["summary"], "body", style, path="summary"))

    if content.get("experience"):
        parts.append(_styled_div("EXPERIENCE", "section_header", style))
        for index, entry in enumerate(content["experience"]):
            path_prefix = f"experience[{index}]"
            company_role_text = f"{entry['company']} - {entry['role']}"
            parts.append(_styled_div(company_role_text, "company_role", style, path=f"{path_prefix}.company_role"))
            meta_text = f"{entry['location']} - {entry['dates']}"
            parts.append(_styled_div(meta_text, "meta", style, path=f"{path_prefix}.meta"))
            if entry.get("employment_type"):
                parts.append(
                    _styled_div(
                        entry["employment_type"], "employment_type", style, path=f"{path_prefix}.employment_type"
                    )
                )
            parts.append(_content_blocks_html(entry.get("content", []), f"{path_prefix}.content", style))

    for index, section in enumerate(content.get("extra_sections", [])):
        path_prefix = f"extra_sections[{index}]"
        parts.append(_styled_div(section["heading"], "extra_heading", style, path=f"{path_prefix}.heading"))
        parts.append(_content_blocks_html(section.get("content", []), f"{path_prefix}.content", style))

    if content.get("skills"):
        parts.append(_styled_div("SKILLS", "section_header", style))
        for skill_line in content["skills"]:
            text = f"{skill_line['label']}: {', '.join(skill_line['items'])}"
            parts.append(_styled_div(text, "body", style))

    parts.append("</div>")
    return "".join(parts)