from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from core.rendering.base import color_hex, merge_style, resolve_style


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


def render_pdf(content: dict, output_path: str, style: dict | None = None) -> str:
    style = merge_style(style)

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
        contacts_text = " | ".join(content["contacts"])
        elements.append(
            Paragraph(
                contacts_text, _paragraph_style("contacts", style, alignment=TA_CENTER, space_after=12)
            )
        )

    if content.get("summary"):
        elements.append(
            Paragraph("SUMMARY", _paragraph_style("section_header", style, space_before=10, space_after=6))
        )
        elements.append(Paragraph(content["summary"], _paragraph_style("body", style, "summary")))

    if content.get("experience"):
        elements.append(
            Paragraph("EXPERIENCE", _paragraph_style("section_header", style, space_before=10, space_after=6))
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
            Paragraph("SKILLS", _paragraph_style("section_header", style, space_before=10, space_after=6))
        )
        for skill_line in content["skills"]:
            text = f"{skill_line['label']}: {', '.join(skill_line['items'])}"
            elements.append(Paragraph(text, _paragraph_style("body", style)))

    document.build(elements)
    return output_path