from core.parsing.html_like_parser import parse_html_like
from core.tailoring.agent_prompt import render_agent_prompt
from core.tailoring.apply import get_by_path


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


def _blocks_to_display_text(blocks) -> str:
    if not isinstance(blocks, list):
        return str(blocks) if blocks is not None else ""

    lines = []
    for block in blocks:
        if block.get("type") == "bullet_list":
            lines.extend(f"- {item}" for item in block.get("items", []))
        else:
            lines.append(block.get("text", ""))
    return "\n".join(lines)


def _parse_changes(parsed: dict, resume_content: dict) -> list[dict]:
    changes = []

    for item in parsed.get("change", []):
        if isinstance(item, str):
            continue

        field_path = item.get("field_path")
        if not field_path:
            continue

        level = item.get("level", "medium")
        change_type = item.get("change_type", "custom")
        kind = item.get("kind", "text")

        if kind == "blocks":
            proposed_content = [_map_content_block(block) for block in item.get("block", [])]
            proposed_text = _blocks_to_display_text(proposed_content)
        else:
            proposed_content = None
            proposed_text = item.get("text", "")

        try:
            original_value = get_by_path(resume_content, field_path)
        except (KeyError, IndexError, ValueError):
            original_value = None

        if isinstance(original_value, list):
            original_text = _blocks_to_display_text(original_value)
        elif isinstance(original_value, str) or original_value is None:
            original_text = original_value or ""
        else:
            original_text = str(original_value)

        changes.append(
            {
                "level": level,
                "change_type": change_type,
                "field_path": field_path,
                "original_text": original_text,
                "proposed_text": proposed_text,
                "proposed_content": proposed_content,
            }
        )

    return changes


def run_agent_turn(
    provider,
    job_posting_text: str,
    resume_content: dict,
    matched_factors: list[dict],
    conversation_history: list[dict],
    user_message: str | None = None,
) -> dict:
    prompt = render_agent_prompt(
        job_posting_text=job_posting_text,
        resume_content=resume_content,
        matched_factors=matched_factors,
        conversation_history=conversation_history,
        user_message=user_message,
    )

    raw_response = provider.call(
        system_prompt="You are a careful, truthful resume tailoring copilot.",
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)

    return {
        "message": _first_or_none(parsed.get("message", [])) or "",
        "changes": _parse_changes(parsed, resume_content),
    }