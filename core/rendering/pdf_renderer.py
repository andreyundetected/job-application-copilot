from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

from core.rendering.base import merge_style


def _build_styles(style: dict) -> dict:
    return {
        "name": ParagraphStyle(
            "name",
            fontName="Helvetica-Bold",
            fontSize=style["name_font_size"],
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "contacts": ParagraphStyle(
            "contacts",
            fontName="Helvetica",
            fontSize=style["meta_font_size"],
            alignment=TA_CENTER,
            spaceAfter=12,
        ),
        "section_header": ParagraphStyle(
            "section_header",
            fontName="Helvetica-Bold",
            fontSize=style["section_header_font_size"],
            alignment=TA_LEFT,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "role_company": ParagraphStyle(
            "role_company",
            fontName="Helvetica-Bold",
            fontSize=style["role_company_font_size"],
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "meta": ParagraphStyle(
            "meta",
            fontName="Helvetica",
            fontSize=style["meta_font_size"],
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "meta_italic": ParagraphStyle(
            "meta_italic",
            fontName="Helvetica-Oblique",
            fontSize=style["meta_font_size"],
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=style["body_font_size"],
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "subheading": ParagraphStyle(
            "subheading",
            fontName="Helvetica-Bold",
            fontSize=style["body_font_size"],
            alignment=TA_LEFT,
            spaceBefore=6,
            spaceAfter=2,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName="Helvetica",
            fontSize=style["body_font_size"],
            alignment=TA_LEFT,
        ),
    }


def _bullet_list(bullets: list[str], styles: dict):
    return ListFlowable(
        [ListItem(Paragraph(bullet, styles["bullet"])) for bullet in bullets],
        bulletType="bullet",
        leftIndent=14,
    )


def render_pdf(content: dict, output_path: str, style: dict | None = None) -> str:
    style = merge_style(style)
    styles = _build_styles(style)

    document = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    elements = [Paragraph(content["name"], styles["name"])]

    if content.get("contacts"):
        contacts_text = " | ".join(content["contacts"])
        elements.append(Paragraph(contacts_text, styles["contacts"]))

    if content.get("summary"):
        elements.append(Paragraph("SUMMARY", styles["section_header"]))
        elements.append(Paragraph(content["summary"], styles["body"]))

    if content.get("experience"):
        elements.append(Paragraph("EXPERIENCE", styles["section_header"]))
        for entry in content["experience"]:
            elements.append(
                Paragraph(f"{entry['company']} - {entry['role']}", styles["role_company"])
            )
            elements.append(
                Paragraph(f"{entry['location']} - {entry['dates']}", styles["meta"])
            )
            if entry.get("employment_type"):
                elements.append(Paragraph(entry["employment_type"], styles["meta_italic"]))
            if entry.get("description"):
                elements.append(Paragraph(entry["description"], styles["body"]))
            if entry.get("bullets"):
                elements.append(_bullet_list(entry["bullets"], styles))

            for subsection in entry.get("subsections", []):
                elements.append(Paragraph(subsection["heading"], styles["subheading"]))
                elements.append(_bullet_list(subsection.get("bullets", []), styles))

            elements.append(Spacer(1, 8))

    for section in content.get("extra_sections", []):
        elements.append(Paragraph(section["heading"], styles["section_header"]))
        if section.get("text"):
            elements.append(Paragraph(section["text"], styles["body"]))
        if section.get("bullets"):
            elements.append(_bullet_list(section["bullets"], styles))

    if content.get("skills"):
        elements.append(Paragraph("SKILLS", styles["section_header"]))
        for skill_line in content["skills"]:
            text = f"{skill_line['label']}: {', '.join(skill_line['items'])}"
            elements.append(Paragraph(text, styles["body"]))

    document.build(elements)
    return output_path