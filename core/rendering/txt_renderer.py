def render_txt(content: dict, output_path: str) -> str:
    lines = [content["name"]]

    if content.get("contacts"):
        lines.append(" | ".join(content["contacts"]))

    if content.get("summary"):
        lines.append("")
        lines.append("SUMMARY")
        lines.append(content["summary"])

    if content.get("experience"):
        lines.append("")
        lines.append("EXPERIENCE")
        for entry in content["experience"]:
            lines.append("")
            lines.append(f"{entry['company']} - {entry['role']}")
            lines.append(f"{entry['location']} - {entry['dates']}")
            if entry.get("employment_type"):
                lines.append(entry["employment_type"])
            if entry.get("description"):
                lines.append(entry["description"])
            for bullet in entry.get("bullets", []):
                lines.append(f"- {bullet}")
            for subsection in entry.get("subsections", []):
                lines.append(subsection["heading"])
                for bullet in subsection.get("bullets", []):
                    lines.append(f"- {bullet}")

    for section in content.get("extra_sections", []):
        lines.append("")
        lines.append(section["heading"])
        if section.get("text"):
            lines.append(section["text"])
        for bullet in section.get("bullets", []):
            lines.append(f"- {bullet}")

    if content.get("skills"):
        lines.append("")
        lines.append("SKILLS")
        for skill_line in content["skills"]:
            lines.append(f"{skill_line['label']}: {', '.join(skill_line['items'])}")

    text = "\n".join(lines)

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(text)

    return output_path