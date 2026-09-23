import logging
import re

from core.gap_analysis.prompt import (
    render_extract_requirements_prompt,
    render_extract_resume_items_section_prompt,
    render_match_gap_items_prompt,
)
from core.parsing.html_like_parser import parse_html_like

logger = logging.getLogger(__name__)

_VALID_PRIORITIES = {"required", "preferred"}
_VALID_CATEGORIES = {"skill", "tool", "title", "certification", "methodology", "domain", "experience"}
_VALID_STATUSES = {"match", "can_add", "miss", "over"}

_G_TAG_RE = re.compile(r"<g\s+([^>]*?)/?>", re.DOTALL)
_ATTR_RE = re.compile(r'(\w+)=(?:"([^"]*)"|((?:(?!\s+\w+=)\S)+(?:\s+(?!\w+=)\S+)*))')
_ITEMS_BLOCK_RE = re.compile(r"<items(?:_(\d+))?>(.*?)</items(?:_\d+)?>", re.DOTALL)

_GAP_MAX_TOKENS = 8192
_GAP_REASONING_EFFORT = "low"
_MATCH_BATCH_SIZE = 8
_MATCH_BATCH_MAX_ATTEMPTS = 3

_PLACEHOLDER_TEXTS = {
    "text", "item", "requirement", "short item name", "item text",
    "the requirement", "status", "category", "keyword text",
}


def _extract_attrs(attrs_raw: str) -> dict:
    attrs = {}
    for name, quoted_value, bare_value in _ATTR_RE.findall(attrs_raw):
        attrs[name] = quoted_value if bare_value == "" else bare_value.strip()
    return attrs


def _looks_like_placeholder(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered in _PLACEHOLDER_TEXTS:
        return True
    if len(lowered) < 2:
        return True
    return False


def _normalize_category(value: str | None) -> str:
    category = (value or "domain").strip().lower()
    return category if category in _VALID_CATEGORIES else "domain"


def _log_empty_parse(step: str, raw_response: str) -> None:
    tail = raw_response[-400:] if len(raw_response) > 400 else raw_response
    logger.warning(
        "[gap_analysis] %s: parsed 0 usable items from a %s-char response. Tail: %r",
        step, len(raw_response), tail,
    )


def _parse_item_lines(block_text: str) -> list[tuple[str, str | None]]:
    items = []
    for line in block_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" in line:
            text_part, category_part = line.split("|", 1)
            text = text_part.strip()
            category = category_part.strip()
        else:
            text = line
            category = None
        if not text or _looks_like_placeholder(text):
            continue
        items.append((text, category))
    return items


def _parse_single_items_block(raw_response: str) -> list[tuple[str, str | None]]:
    match = _ITEMS_BLOCK_RE.search(raw_response)
    if not match:
        return []
    return _parse_item_lines(match.group(2))


def _parse_tiered_items(raw_response: str) -> list[dict]:
    tiers = []
    for match in _ITEMS_BLOCK_RE.finditer(raw_response):
        tier_num = int(match.group(1)) if match.group(1) else None
        tiers.append((tier_num, match.group(2)))

    tiers.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 0))

    results = []
    for index, (tier_num, block_text) in enumerate(tiers, start=1):
        effective_tier = tier_num if tier_num is not None else index
        priority = "required" if effective_tier <= 3 else "preferred"
        for text, category in _parse_item_lines(block_text):
            results.append({"text": text, "priority": priority, "category": _normalize_category(category)})

    return results


def extract_job_requirements(provider, job_posting_text: str) -> list[dict]:
    prompt = render_extract_requirements_prompt(job_posting_text)

    raw_response = provider.call(
        system_prompt="You extract structured requirements from a job posting for gap analysis against a resume. Wrap reasoning in <think>, output keywords only inside <items_N> tags.",
        user_prompt=prompt,
        max_tokens=_GAP_MAX_TOKENS,
        reasoning_effort=_GAP_REASONING_EFFORT,
    )

    requirements = _parse_tiered_items(raw_response)

    if not requirements:
        _log_empty_parse("extract_job_requirements", raw_response)

    return requirements


def _call_extract_section(
    provider,
    section_label: str,
    section_text: str,
    field_path: str | None,
    source_value: str,
    max_items: int,
) -> list[dict]:
    if not section_text.strip():
        return []

    prompt = render_extract_resume_items_section_prompt(section_label, section_text, max_items)

    items = []
    for attempt in range(_MATCH_BATCH_MAX_ATTEMPTS):
        raw_response = provider.call(
            system_prompt="You extract ATS-style keywords from one section of a candidate's resume/profile. Wrap reasoning in <think>, output keywords only inside <items>.",
            user_prompt=prompt,
            max_tokens=2048,
            reasoning_effort=_GAP_REASONING_EFFORT,
        )
        parsed = _parse_single_items_block(raw_response)
        if parsed:
            items = [
                {"text": text, "category": _normalize_category(category), "field_path": field_path, "source": source_value}
                for text, category in parsed
            ]
            break
        _log_empty_parse(f"extract_resume_items ({section_label}, attempt {attempt + 1}/{_MATCH_BATCH_MAX_ATTEMPTS})", raw_response)

    return items


def extract_resume_items(
    provider,
    resume_html: str,
    linkedin_text: str,
    extra_info: str | None,
) -> list[dict]:
    from core.gap_analysis.block_extraction import extract_ordered_blocks

    blocks = extract_ordered_blocks(resume_html)
    all_items: list[dict] = []

    summary_block = next((b for b in blocks if b["field_path"] == "summary"), None)
    skills_block = next((b for b in blocks if b["field_path"] == "skills"), None)

    if summary_block:
        all_items.extend(_call_extract_section(provider, "Summary", summary_block["body_text"], "summary", "resume", 5))

    if skills_block:
        all_items.extend(_call_extract_section(provider, "Skills", skills_block["body_text"], "skills", "resume", 25))

    for block in blocks:
        if not block["field_path"].startswith("experience:") and not block["field_path"].startswith("section:"):
            continue
        all_items.extend(_call_extract_section(provider, block["label"], block["body_text"], block["field_path"], "resume", 10))

    if linkedin_text.strip():
        all_items.extend(_call_extract_section(provider, "LinkedIn profile", linkedin_text, None, "linkedin", 20))

    if extra_info and extra_info.strip():
        all_items.extend(_call_extract_section(provider, "Additional profile info", extra_info, None, "profile", 10))

    if not all_items:
        logger.warning("[gap_analysis] extract_resume_items: 0 items across all sections")

    return all_items


def parse_g_tags(raw_response: str) -> list[dict]:
    results = []
    for match in _G_TAG_RE.finditer(raw_response):
        attrs_raw = match.group(1)
        attrs = _extract_attrs(attrs_raw)

        status = (attrs.get("status") or "").strip().lower()
        if status not in _VALID_STATUSES:
            continue
        text = (attrs.get("text") or "").strip()
        if not text or _looks_like_placeholder(text):
            continue

        priority = (attrs.get("priority") or "").strip().lower()
        priority = priority if priority in _VALID_PRIORITIES else None

        original = (attrs.get("original") or "").strip()
        original = None if original.lower() in ("", "none") else original

        suggest_raw = (attrs.get("suggest") or "").strip()
        suggested_paths = (
            [p.strip() for p in suggest_raw.split(";") if p.strip() and p.strip().lower() != "none"]
            if suggest_raw.lower() not in ("", "none")
            else []
        )

        keep_raw = (attrs.get("keep") or "").strip().lower()
        recommend_keep = {"yes": True, "no": False}.get(keep_raw) if status == "over" else None

        reason = (attrs.get("reason") or "").strip() or None

        results.append(
            {
                "text": text,
                "category": _normalize_category(attrs.get("category")),
                "status": status,
                "priority": priority,
                "source": None,
                "original_field_path": original,
                "suggested_field_paths": suggested_paths,
                "suggested_reason": reason,
                "recommend_keep": recommend_keep,
            }
        )

    return results


_STATUS_PRIORITY = {"match": 0, "can_add": 1, "miss": 2, "over": 3}


def _dedupe_gap_items(items: list[dict]) -> list[dict]:
    best_by_text: dict[str, dict] = {}
    for item in items:
        key = item["text"].strip().lower()
        existing = best_by_text.get(key)
        if existing is None or _STATUS_PRIORITY[item["status"]] < _STATUS_PRIORITY[existing["status"]]:
            best_by_text[key] = item
    return list(best_by_text.values())


def match_gap_items(provider, requirements: list[dict], resume_items: list[dict]) -> list[dict]:
    req_batches = [requirements[i : i + _MATCH_BATCH_SIZE] for i in range(0, len(requirements), _MATCH_BATCH_SIZE)]
    all_results: list[dict] = []

    for batch_index, req_batch in enumerate(req_batches):
        prompt = render_match_gap_items_prompt(req_batch, resume_items)

        parsed = []
        for attempt in range(_MATCH_BATCH_MAX_ATTEMPTS):
            raw_response = provider.call(
                system_prompt=(
                    "You categorize each requirement and each resume item into a gap-analysis status, "
                    "and suggest where each accepted item should live in the resume. Output only the specified line format, no explanation."
                ),
                user_prompt=prompt,
                max_tokens=_GAP_MAX_TOKENS,
                reasoning_effort=_GAP_REASONING_EFFORT,
            )
            parsed = parse_g_tags(raw_response)
            if parsed:
                break
            _log_empty_parse(
                f"match_gap_items (batch {batch_index + 1}/{len(req_batches)}, attempt {attempt + 1}/{_MATCH_BATCH_MAX_ATTEMPTS})",
                raw_response,
            )

        all_results.extend(parsed)

    return _dedupe_gap_items(all_results)


def suggest_titles(
    provider, main_title: str, experience_titles: list[dict], job_posting_text: str
) -> list[dict]:
    from core.gap_analysis.prompt import render_suggest_title_prompt

    prompt = render_suggest_title_prompt(main_title, experience_titles, job_posting_text)
    raw_response = provider.call(
        system_prompt="You suggest resume title rewordings across the whole resume to match a job posting. Output only tags, no explanation.",
        user_prompt=prompt,
        max_tokens=2048,
        reasoning_effort=_GAP_REASONING_EFFORT,
    )

    parsed = parse_html_like(raw_response)
    suggestions = []
    for item in parsed.get("title_suggestion", []):
        if isinstance(item, str):
            continue
        kind = (item.get("kind") or "").strip().lower()
        text = (item.get("text") or "").strip()
        if not text or kind not in ("main", "experience"):
            continue
        suggestions.append({"kind": kind, "company": item.get("company"), "suggested": text})

    return suggestions


def run_full_gap_analysis(
    provider,
    job_posting_text: str,
    resume_html: str,
    linkedin_text: str,
    extra_info: str | None,
    max_attempts: int = 3,
) -> dict:
    requirements = []
    for _ in range(max_attempts):
        requirements = extract_job_requirements(provider, job_posting_text)
        if requirements:
            break

    resume_items = extract_resume_items(provider, resume_html, linkedin_text, extra_info)

    gap_items = match_gap_items(provider, requirements, resume_items)

    return {"gap_items": gap_items, "resume_items": resume_items}