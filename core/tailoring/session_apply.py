from core.tailoring.apply import set_by_path


def _find_experience_index(resume_content: dict, company: str | None) -> int | None:
    if not company:
        return None
    for index, entry in enumerate(resume_content.get("experience", [])):
        if entry.get("company") == company:
            return index
    return None


def _parse_skills_text(proposed_text: str) -> list[dict]:
    # Fallback parser for the soft-level "skills" change, whose proposed_text is a
    # flat "Label: item1, item2" block per line (see core/tailoring/pipeline.py).
    groups = []
    for line in proposed_text.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        label, items_text = line.split(":", 1)
        items = [item.strip() for item in items_text.split(",") if item.strip()]
        groups.append({"label": label.strip(), "items": items})
    return groups


def attach_field_paths(resume_content: dict, changes: list[dict]) -> list[dict]:
    """Maps soft/medium pipeline changes (which key off change_type/target_ref)
    onto exact field_path values, so they can go through the same apply/storage
    path as agent-produced changes (which already carry field_path)."""
    result = []
    for change in changes:
        change_type = change["change_type"]
        field_path = None

        if change_type == "title":
            field_path = "name"
        elif change_type == "summary":
            field_path = "summary"
        elif change_type == "skills":
            field_path = "skills"
        elif change_type == "experience_title":
            index = _find_experience_index(resume_content, change.get("target_ref"))
            if index is not None:
                field_path = f"experience[{index}].role"
        elif change_type == "experience":
            index = _find_experience_index(resume_content, change.get("target_ref"))
            if index is not None:
                field_path = f"experience[{index}].content"

        if field_path is None:
            # Target company no longer exists in the resume (e.g. removed since
            # evaluation) - skip the change rather than crash.
            continue

        result.append({**change, "field_path": field_path})

    return result


def apply_change_to_content(resume_content: dict, change: dict) -> dict:
    field_path = change["field_path"]

    if change["change_type"] == "skills" and change.get("proposed_content") is None:
        new_value = _parse_skills_text(change["proposed_text"])
    elif change.get("proposed_content") is not None:
        new_value = change["proposed_content"]
    else:
        new_value = change["proposed_text"]

    return set_by_path(resume_content, field_path, new_value)