from core.parsing.html_like_parser import parse_html_like
from core.tailoring.prompt import render_medium_tailoring_prompt, render_soft_tailoring_prompt


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


def _blocks_to_display_text(blocks: list[dict]) -> str:
    lines = []
    for block in blocks:
        if block["type"] == "bullet_list":
            lines.extend(f"- {item}" for item in block["items"])
        else:
            lines.append(block.get("text", ""))
    return "\n".join(lines)


def _current_experience_title(resume_content: dict, company: str) -> str | None:
    for entry in resume_content.get("experience", []):
        if entry.get("company") == company:
            return entry.get("role")
    return None


def propose_soft_changes(
    provider,
    job_posting_text: str,
    resume_content: dict,
    matched_factors: list[dict],
) -> list[dict]:
    prompt = render_soft_tailoring_prompt(
        job_posting_text=job_posting_text,
        resume_content=resume_content,
        matched_factors=matched_factors,
    )

    raw_response = provider.call(
        system_prompt="You tailor resume titles and skills to a target job posting without inventing content.",
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)
    changes = []

    title_rewrite = _first_or_none(parsed.get("title_rewrite", []))
    if title_rewrite:
        changes.append(
            {
                "level": "soft",
                "change_type": "title",
                "target_ref": None,
                "original_text": resume_content.get("name"),
                "proposed_text": title_rewrite,
            }
        )

    for item in parsed.get("experience_title", []):
        if isinstance(item, str):
            continue
        company = item.get("company")
        proposed = item.get("text", "")
        if not company or not proposed:
            continue
        changes.append(
            {
                "level": "soft",
                "change_type": "experience_title",
                "target_ref": company,
                "original_text": _current_experience_title(resume_content, company),
                "proposed_text": proposed,
            }
        )

    skill_groups = parsed.get("skill_group", [])
    if skill_groups:
        lines = []
        for group in skill_groups:
            if isinstance(group, str):
                continue
            label = group.get("label", "")
            items = group.get("item", [])
            lines.append(f"{label}: {', '.join(items)}")
        if lines:
            original_lines = [
                f"{group.get('label', '')}: {', '.join(group.get('items', []))}"
                for group in resume_content.get("skills", [])
            ]
            changes.append(
                {
                    "level": "soft",
                    "change_type": "skills",
                    "target_ref": None,
                    "original_text": "\n".join(original_lines),
                    "proposed_text": "\n".join(lines),
                }
            )

    return changes


def propose_medium_changes(
    provider,
    job_posting_text: str,
    resume_content: dict,
    matched_factors: list[dict],
    keywords: list[str],
) -> list[dict]:
    prompt = render_medium_tailoring_prompt(
        job_posting_text=job_posting_text,
        resume_content=resume_content,
        matched_factors=matched_factors,
        keywords=keywords,
    )

    raw_response = provider.call(
        system_prompt="You tailor resume summary and experience descriptions to a target job posting without inventing content.",
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)
    changes = []

    summary_rewrite = _first_or_none(parsed.get("summary_rewrite", []))
    if summary_rewrite:
        changes.append(
            {
                "level": "medium",
                "change_type": "summary",
                "target_ref": None,
                "original_text": resume_content.get("summary"),
                "proposed_text": summary_rewrite,
            }
        )

    for item in parsed.get("experience_rewrite", []):
        if isinstance(item, str):
            continue
        company = item.get("company")
        if not company:
            continue

        proposed_blocks = [_map_content_block(block) for block in item.get("block", [])]
        if not proposed_blocks:
            continue

        original_entry = next(
            (e for e in resume_content.get("experience", []) if e.get("company") == company),
            {},
        )

        # NOTE: proposed/original are stored as plain display text for now (soft/medium HIL
        # review). Applying an approved change back into the structured resume content as
        # actual blocks is part of the upcoming tailoring-session/agent phase, not this one.
        changes.append(
            {
                "level": "medium",
                "change_type": "experience",
                "target_ref": company,
                "original_text": _blocks_to_display_text(original_entry.get("content", [])),
                "proposed_text": _blocks_to_display_text(proposed_blocks),
            }
        )

    return changes