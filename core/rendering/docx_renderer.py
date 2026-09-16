from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from core.rendering.base import merge_style


def _add_contacts_paragraph(document: Document, contacts: list[str], style: dict):
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER

    if style["contacts_layout"] == "inline":
        run = paragraph.add_run(" | ".join(contacts))
        run.font.size = Pt(style["meta_font_size"])
        run.font.name = style["font_name"]
    else:
        for index, contact in enumerate(contacts):
            run = paragraph.add_run(contact)
            run.font.size = Pt(style["meta_font_size"])
            run.font.name = style["font_name"]
            if index < len(contacts) - 1:
                paragraph.add_run().add_break()


def _add_section_header(document: Document, text: str, style: dict):
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    run.bold = True
    run.font.size = Pt(style["section_header_font_size"])
    run.font.name = style["font_name"]


def _add_bullets(document: Document, bullets: list[str], style: dict):
    for bullet in bullets:
        paragraph = document.add_paragraph(style="List Bullet")
        run = paragraph.add_run(bullet)
        run.font.size = Pt(style["body_font_size"])
        run.font.name = style["font_name"]


def _add_experience_entry(document: Document, entry: dict, style: dict):
    header_paragraph = document.add_paragraph()
    run = header_paragraph.add_run(f"{entry['company']} - {entry['role']}")
    run.bold = True
    run.font.size = Pt(style["role_company_font_size"])
    run.font.name = style["font_name"]

    meta_paragraph = document.add_paragraph()
    meta_text = f"{entry['location']} - {entry['dates']}"
    meta_run = meta_paragraph.add_run(meta_text)
    meta_run.font.size = Pt(style["meta_font_size"])
    meta_run.font.name = style["font_name"]

    if entry.get("employment_type"):
        type_paragraph = document.add_paragraph()
        type_run = type_paragraph.add_run(entry["employment_type"])
        type_run.italic = True
        type_run.font.size = Pt(style["meta_font_size"])
        type_run.font.name = style["font_name"]

    if entry.get("description"):
        description_paragraph = document.add_paragraph()
        description_run = description_paragraph.add_run(entry["description"])
        description_run.font.size = Pt(style["body_font_size"])
        description_run.font.name = style["font_name"]

    if entry.get("bullets"):
        _add_bullets(document, entry["bullets"], style)

    for subsection in entry.get("subsections", []):
        heading_paragraph = document.add_paragraph()
        heading_run = heading_paragraph.add_run(subsection["heading"])
        heading_run.bold = True
        heading_run.font.size = Pt(style["body_font_size"])
        heading_run.font.name = style["font_name"]

        _add_bullets(document, subsection.get("bullets", []), style)


def render_docx(content: dict, output_path: str, style: dict | None = None) -> str:
    style = merge_style(style)
    document = Document()

    name_paragraph = document.add_paragraph()
    name_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_run = name_paragraph.add_run(content["name"])
    name_run.bold = True
    name_run.font.size = Pt(style["name_font_size"])
    name_run.font.name = style["font_name"]

    if content.get("contacts"):
        _add_contacts_paragraph(document, content["contacts"], style)

    if content.get("summary"):
        _add_section_header(document, "SUMMARY", style)
        summary_paragraph = document.add_paragraph()
        summary_run = summary_paragraph.add_run(content["summary"])
        summary_run.font.size = Pt(style["body_font_size"])
        summary_run.font.name = style["font_name"]

    if content.get("experience"):
        _add_section_header(document, "EXPERIENCE", style)
        for entry in content["experience"]:
            _add_experience_entry(document, entry, style)

    for section in content.get("extra_sections", []):
        _add_section_header(document, section["heading"], style)
        if section.get("text"):
            text_paragraph = document.add_paragraph()
            text_run = text_paragraph.add_run(section["text"])
            text_run.font.size = Pt(style["body_font_size"])
            text_run.font.name = style["font_name"]
        if section.get("bullets"):
            _add_bullets(document, section["bullets"], style)

    if content.get("skills"):
        _add_section_header(document, "SKILLS", style)
        for skill_line in content["skills"]:
            paragraph = document.add_paragraph()
            text = f"{skill_line['label']}: {', '.join(skill_line['items'])}"
            run = paragraph.add_run(text)
            run.font.size = Pt(style["body_font_size"])
            run.font.name = style["font_name"]

    document.save(output_path)
    return output_path