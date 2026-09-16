from core.parsing.html_like_parser import parse_html_like
from core.structuring.prompt import render_structure_prompt


def _first_or_none(values: list):
    if not values:
        return None
    return values[0]


def _map_content_block(raw_block) -> dict:
    if isinstance(raw_block, str):
        return {"type": "paragraph", "text": raw_block}

    block_type = raw_block.get("type", "paragraph")

    if block_type == "bullet_list":
        return {"type": "bullet_list", "items": raw_block.get("item", [])}

    return {"type": block_type, "text": raw_block.get("text", "")}


def _map_experience_entry(raw_entry) -> dict:
    if isinstance(raw_entry, str):
        raw_entry = {}

    return {
        "company": raw_entry.get("company", ""),
        "role": raw_entry.get("role", ""),
        "location": raw_entry.get("location", ""),
        "dates": raw_entry.get("dates", ""),
        "employment_type": raw_entry.get("employment_type", ""),
        "content": [_map_content_block(block) for block in raw_entry.get("block", [])],
    }


def _map_extra_section(raw_section) -> dict:
    if isinstance(raw_section, str):
        raw_section = {}

    return {
        "heading": raw_section.get("heading", ""),
        "content": [_map_content_block(block) for block in raw_section.get("block", [])],
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


def structure_profile_text(provider, raw_text: str, source_label: str, language: str = "en") -> dict:
    prompt = render_structure_prompt(raw_text, source_label, language=language)

    raw_response = provider.call(
        system_prompt="You convert raw profile text into structured tagged data without adding or inventing content.",
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)
    return _parsed_to_content(parsed)


def structure_resume_text(provider, raw_text: str, language: str = "en") -> dict:
    return structure_profile_text(provider, raw_text, source_label="resume", language=language)


def structure_linkedin_text(provider, raw_text: str, language: str = "en") -> dict:
    return structure_profile_text(
        provider, raw_text, source_label="LinkedIn experience export", language=language
    )