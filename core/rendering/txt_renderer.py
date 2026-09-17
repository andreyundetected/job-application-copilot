from core.rendering.html_export import parse_resume_html


def render_html_export_to_txt(html_content: str, output_path: str) -> str:
    blocks = parse_resume_html(html_content)
    lines = []

    for block in blocks:
        text = "".join(run["text"] for run in block["runs"]).replace("\n", " ").strip()
        if not text:
            continue
        lines.append(f"- {text}" if block["type"] == "bullet" else text)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))

    return output_path


def _render_content_blocks_lines(blocks):
    lines = []
    for block in blocks or []:
        block_type = block.get("type")
        if block_type == "bullet_list":
            for item in block.get("items", []):
                lines.append(f"- {item}")
        else:
            lines.append(block.get("text", ""))
    return lines


DEFAULT_SECTION_LABELS = {
    "summary": "SUMMARY",
    "experience": "EXPERIENCE",
    "skills": "SKILLS",
}


def render_txt(content: dict, output_path: str) -> str:
    section_labels = {**DEFAULT_SECTION_LABELS, **(content.get("section_labels") or {})}

    lines = [content["name"]]

    if content.get("contacts"):
        lines.append(" | ".join(content["contacts"]))

    if content.get("summary"):
        lines.append("")
        lines.append(section_labels["summary"])
        lines.append(content["summary"])

    if content.get("experience"):
        lines.append("")
        lines.append(section_labels["experience"])
        for entry in content["experience"]:
            lines.append("")
            lines.append(f"{entry['company']} - {entry['role']}")
            lines.append(f"{entry['location']} - {entry['dates']}")
            if entry.get("employment_type"):
                lines.append(entry["employment_type"])
            lines.extend(_render_content_blocks_lines(entry.get("content", [])))

    for section in content.get("extra_sections", []):
        lines.append("")
        lines.append(section["heading"])
        lines.extend(_render_content_blocks_lines(section.get("content", [])))

    if content.get("skills"):
        lines.append("")
        lines.append(section_labels["skills"])
        for skill_line in content["skills"]:
            lines.append(f"{skill_line['label']}: {', '.join(skill_line['items'])}")

    text = "\n".join(lines)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(text)

    return output_path