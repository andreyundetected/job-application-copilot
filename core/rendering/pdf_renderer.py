import html as html_module

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from core.rendering.base import color_hex, merge_style, resolve_style
from core.rendering.html_export import parse_resume_html

_ALIGN_MAP = {"left": TA_LEFT, "center": TA_CENTER, "right": TA_RIGHT}


def _font_name(resolved: dict) -> str:
    if resolved.get("bold") and resolved.get("italic"):
        return "Helvetica-BoldOblique"
    if resolved.get("bold"):
        return "Helvetica-Bold"
    if resolved.get("italic"):
        return "Helvetica-Oblique"
    return "Helvetica"


def _paragraph_style(
    class_name, style, path=None, alignment=TA_LEFT, space_after=6, space_before=0
) -> ParagraphStyle:
    resolved = resolve_style(style, class_name, path)
    return ParagraphStyle(
        f"{class_name}_{path or 'default'}",
        fontName=_font_name(resolved),
        fontSize=resolved.get("size", 10),
        textColor=HexColor(color_hex(resolved.get("color", "black"))),
        alignment=alignment,
        spaceBefore=space_before,
        spaceAfter=space_after,
    )


def _bullet_list(items, class_name, style, path):
    para_style = _paragraph_style(class_name, style, path, alignment=TA_LEFT, space_after=0)
    return ListFlowable(
        [ListItem(Paragraph(item, para_style)) for item in items],
        bulletType="bullet",
        leftIndent=14,
    )


def _content_block_flowables(blocks, path_prefix, style):
    flowables = []
    for index, block in enumerate(blocks or []):
        block_path = f"{path_prefix}[{index}]"
        block_type = block.get("type")

        if block_type == "heading":
            flowables.append(
                Paragraph(
                    block.get("text", ""),
                    _paragraph_style("heading", style, block_path, space_before=6, space_after=2),
                )
            )
        elif block_type == "bullet_list":
            flowables.append(_bullet_list(block.get("items", []), "bullet", style, block_path))
        else:
            flowables.append(
                Paragraph(block.get("text", ""), _paragraph_style("body", style, block_path))
            )
    return flowables


DEFAULT_SECTION_LABELS = {
    "summary": "SUMMARY",
    "experience": "EXPERIENCE",
    "skills": "SKILLS",
}


def render_pdf(content: dict, output_path: str, style: dict | None = None) -> str:
    style = merge_style(style)

    section_labels = {**DEFAULT_SECTION_LABELS, **(content.get("section_labels") or {})}

    document = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    elements = [
        Paragraph(content["name"], _paragraph_style("name", style, alignment=TA_CENTER, space_after=4))
    ]

    if content.get("contacts"):
        layout = style.get("contacts_layout", "inline")
        if layout == "stacked":
            contacts_text = "<br/>".join(content["contacts"])
        else:
            contacts_text = " | ".join(content["contacts"])
        elements.append(
            Paragraph(
                contacts_text, _paragraph_style("contacts", style, alignment=TA_CENTER, space_after=12)
            )
        )

    if content.get("summary"):
        elements.append(
            Paragraph(
                section_labels["summary"],
                _paragraph_style("section_header", style, space_before=10, space_after=6),
            )
        )
        elements.append(Paragraph(content["summary"], _paragraph_style("body", style, "summary")))

    if content.get("experience"):
        elements.append(
            Paragraph(
                section_labels["experience"],
                _paragraph_style("section_header", style, space_before=10, space_after=6),
            )
        )
        for index, entry in enumerate(content["experience"]):
            path_prefix = f"experience[{index}]"
            elements.append(
                Paragraph(
                    f"{entry['company']} - {entry['role']}",
                    _paragraph_style("company_role", style, f"{path_prefix}.company_role", space_after=2),
                )
            )
            elements.append(
                Paragraph(
                    f"{entry['location']} - {entry['dates']}",
                    _paragraph_style("meta", style, f"{path_prefix}.meta", space_after=2),
                )
            )
            if entry.get("employment_type"):
                elements.append(
                    Paragraph(
                        entry["employment_type"],
                        _paragraph_style(
                            "employment_type", style, f"{path_prefix}.employment_type", space_after=6
                        ),
                    )
                )
            elements.extend(
                _content_block_flowables(entry.get("content", []), f"{path_prefix}.content", style)
            )
            elements.append(Spacer(1, 8))

    for index, section in enumerate(content.get("extra_sections", [])):
        path_prefix = f"extra_sections[{index}]"
        elements.append(
            Paragraph(
                section["heading"],
                _paragraph_style("extra_heading", style, f"{path_prefix}.heading", space_before=10, space_after=6),
            )
        )
        elements.extend(
            _content_block_flowables(section.get("content", []), f"{path_prefix}.content", style)
        )

    if content.get("skills"):
        elements.append(
            Paragraph(
                section_labels["skills"],
                _paragraph_style("section_header", style, space_before=10, space_after=6),
            )
        )
        for skill_line in content["skills"]:
            text = f"{skill_line['label']}: {', '.join(skill_line['items'])}"
            elements.append(Paragraph(text, _paragraph_style("body", style)))

    document.build(elements)
    return output_path


def _run_to_markup(run: dict) -> str:
    text = html_module.escape(run["text"]).replace("\n", "<br/>")
    size = run.get("size") or 10
    color = run.get("color") or "#000000"
    text = f'<font color="{color}" size="{size}">{text}</font>'
    if run.get("bold"):
        text = f"<b>{text}</b>"
    if run.get("italic"):
        text = f"<i>{text}</i>"
    return text


def render_html_export_to_pdf(html_content: str, output_path: str) -> str:
    blocks = parse_resume_html(html_content)

    document = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    elements = []
    bullet_buffer = []

    def flush_bullets():
        if bullet_buffer:
            elements.append(ListFlowable(list(bullet_buffer), bulletType="bullet", leftIndent=14))
            bullet_buffer.clear()

    for block in blocks:
        markup = "".join(_run_to_markup(run) for run in block["runs"])
        base_size = block["runs"][0].get("size") or 10
        style = ParagraphStyle(
            "block",
            alignment=_ALIGN_MAP.get(block["align"], TA_LEFT),
            spaceAfter=6,
            leading=base_size * 1.3,
        )

        if block["type"] == "bullet":
            bullet_buffer.append(ListItem(Paragraph(markup, style)))
        else:
            flush_bullets()
            elements.append(Paragraph(markup, style))

    flush_bullets()
    document.build(elements)
    return output_path