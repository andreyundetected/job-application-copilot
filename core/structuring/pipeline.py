from core.parsing.html_like_parser import parse_html_like
from core.structuring.prompt import render_structure_prompt


def _first_or_none(values: list):
    if not values:
        return None
    return values[0]


def _map_experience_entry(raw_entry) -> dict:
    if isinstance(raw_entry, str):
        raw_entry = {}

    return {
        "company": raw_entry.get("company", ""),
        "role": raw_entry.get("role", ""),
        "location": raw_entry.get("location", ""),
        "dates": raw_entry.get("dates", ""),
        "employment_type": raw_entry.get("employment_type", ""),
        "description": _first_or_none(raw_entry.get("description", [])),
        "bullets": raw_entry.get("bullet", []),
        "subsections": [_map_subsection(item) for item in raw_entry.get("subsection", [])],
    }


def _map_subsection(raw_subsection) -> dict:
    if isinstance(raw_subsection, str):
        raw_subsection = {}

    return {
        "heading": raw_subsection.get("heading", ""),
        "bullets": raw_subsection.get("bullet", []),
    }


def _map_extra_section(raw_section) -> dict:
    if isinstance(raw_section, str):
        raw_section = {}

    return {
        "heading": raw_section.get("heading", ""),
        "text": _first_or_none(raw_section.get("text", [])) or "",
        "bullets": raw_section.get("bullet", []),
    }


def _map_skill_group(raw_group) -> dict:
    if isinstance(raw_group, str):
        raw_group = {}

    return {
        "label": raw_group.get("label", ""),
        "items": raw_group.get("item", []),
    }


def _parsed_to_content(parsed: dict) -> dict:
    return {
        "name": _first_or_none(parsed.get("name", [])),
        "contacts": parsed.get("contact", []),
        "summary": _first_or_none(parsed.get("summary", [])),
        "experience": [_map_experience_entry(entry) for entry in parsed.get("experience", [])],
        "extra_sections": [_map_extra_section(section) for section in parsed.get("extra_section", [])],
        "skills": [_map_skill_group(group) for group in parsed.get("skill_group", [])],
    }


def structure_profile_text(provider, raw_text: str, source_label: str) -> dict:
    prompt = render_structure_prompt(raw_text, source_label)

    raw_response = provider.call(
        system_prompt="You convert raw profile text into structured tagged data without adding or inventing content.",
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)
    return _parsed_to_content(parsed)


def structure_resume_text(provider, raw_text: str) -> dict:
    return structure_profile_text(provider, raw_text, source_label="resume")


def structure_linkedin_text(provider, raw_text: str) -> dict:
    return structure_profile_text(provider, raw_text, source_label="LinkedIn experience export")