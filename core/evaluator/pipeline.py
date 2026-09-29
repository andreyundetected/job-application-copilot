import re

import config
from core.evaluator.prompt import render_evaluator_prompt, render_quick_extract_prompt
from core.parsing.html_like_parser import parse_html_like


def _first_or_none(parsed: dict, key: str) -> str | None:
    values = parsed.get(key)
    if not values:
        return None
    return values[0]


def _parse_score(raw_score: str | None) -> int | None:
    if raw_score is None:
        return None
    try:
        return int(raw_score.strip())
    except ValueError:
        return None


def _parse_float(raw_value: str | None) -> float | None:
    if raw_value is None:
        return None
    try:
        return float(raw_value.strip())
    except ValueError:
        return None


def _parse_bool(raw_value: str | None) -> bool | None:
    if raw_value is None:
        return None
    return raw_value.strip().lower() == "true"


def _build_salary(parsed: dict) -> dict:
    return {
        "min": _parse_float(_first_or_none(parsed, "salary_min")),
        "max": _parse_float(_first_or_none(parsed, "salary_max")),
        "currency": _first_or_none(parsed, "salary_currency"),
        "period": _first_or_none(parsed, "salary_period"),
        "is_estimate": _parse_bool(_first_or_none(parsed, "salary_is_estimate")),
        "original_text": _first_or_none(parsed, "salary_original_text"),
    }


def _build_location(parsed: dict) -> dict:
    country = _first_or_none(parsed, "location_country")
    state = _first_or_none(parsed, "location_state")
    city = _first_or_none(parsed, "location_city")

    if country and country.strip().upper() == "N/A":
        country = None

    display_parts = [part for part in [country, state, city] if part]
    display = ", ".join(display_parts) if display_parts else "N/A"

    return {"country": country, "state": state, "city": city, "display": display}


def _build_matched_factors(parsed: dict, scoring_factors: list[dict]) -> list[dict]:
    factors_by_id = {str(factor["id"]): factor for factor in scoring_factors}
    matched_raw = parsed.get("matched_factor", [])

    matched = []
    for item in matched_raw:
        if isinstance(item, dict):
            factor_id = item.get("id")
            note = item.get("text", "")
        else:
            factor_id = None
            note = item

        factor = factors_by_id.get(str(factor_id)) if factor_id is not None else None
        if factor is None:
            continue

        matched.append(
            {
                "id": factor["id"],
                "text": factor["text"],
                "direction": factor["direction"],
                "weight": factor["weight"],
                "note": note,
            }
        )

    return matched


_SCORE_RE = re.compile(r"<score>\s*(-?\d+)\s*</score>")
_REASONING_RE = re.compile(r"<reasoning>(.*?)</reasoning>", re.DOTALL)
_FACTOR_RE = re.compile(r'<matched_factor\s+id="(\d+)"[^>]*>(.*?)</matched_factor>', re.DOTALL)
_BULLET_RE = re.compile(r"<bullet>(.*?)</bullet>", re.DOTALL)
_ANY_TAG_RE = re.compile(r"<[^>]+>")


def _extract_score(raw_response: str) -> int | None:
    matches = _SCORE_RE.findall(raw_response)
    if not matches:
        return None
    return max(0, min(10, int(matches[-1])))


def _extract_reasoning(raw_response: str) -> str | None:
    match = _REASONING_RE.search(raw_response)
    if match is None:
        return None
    return match.group(1).strip()


def _extract_factor_notes(raw_response: str) -> dict:
    return {
        "matched_factor": [
            {"id": factor_id, "text": " ".join(note.split())}
            for factor_id, note in _FACTOR_RE.findall(raw_response)
        ]
    }


def _extract_bullets(raw_response: str, tag: str) -> list[str]:
    bullets = []
    for inner in re.findall(rf"<{tag}>(.*?)</{tag}>", raw_response, re.DOTALL):
        for candidate in _BULLET_RE.findall(inner) or [inner]:
            text = " ".join(_ANY_TAG_RE.sub(" ", candidate).split())
            if text:
                bullets.append(text)
    return bullets


def evaluate_job_posting(
    provider,
    job_posting_text: str,
    resume_text: str,
    linkedin_text: str,
    blockers: list[str],
    scoring_factors: list[dict] | None = None,
    contacts: list[str] | None = None,
    extra_info: str | None = None,
    language: str = "en",
) -> dict:
    scoring_factors = scoring_factors or []

    prompt = render_evaluator_prompt(
        job_posting_text=job_posting_text,
        resume_text=resume_text,
        linkedin_text=linkedin_text,
        blockers=blockers,
        scoring_factors=scoring_factors,
        contacts=contacts,
        extra_info=extra_info,
        language=language,
    )

    raw_response = provider.call(
        system_prompt="You are a strict, consistent job-fit evaluator.",
        user_prompt=prompt,
        temperature=config.EVALUATOR_TEMPERATURE,
    )

    score = _extract_score(raw_response)

    return {
        "reasoning": _extract_reasoning(raw_response),
        "score": score,
        "matched_factors": _build_matched_factors(_extract_factor_notes(raw_response), scoring_factors),
        "cons": _extract_bullets(raw_response, "con"),
        "pros": _extract_bullets(raw_response, "pro"),
        "verdict": bool(score) and score > 0,
        "raw_response": raw_response,
    }


def quick_extract_job_posting(provider, job_posting_text: str) -> dict:
    prompt = render_quick_extract_prompt(job_posting_text=job_posting_text)

    raw_response = provider.call(
        system_prompt="You extract short literal facts from a job posting as fast as possible.",
        user_prompt=prompt,
        temperature=config.EVALUATOR_TEMPERATURE,
    )

    parsed = parse_html_like(raw_response)
    location = _build_location(parsed)

    return {
        "company": _first_or_none(parsed, "company"),
        "role": _first_or_none(parsed, "role"),
        "location": location["display"],
        "location_country": location["country"],
        "location_state": location["state"],
        "location_city": location["city"],
        "work_mode": _first_or_none(parsed, "work_mode"),
        "employment_type": _first_or_none(parsed, "employment_type"),
        "tags": parsed.get("tag", []),
        "salary": _build_salary(parsed),
        "summary": _first_or_none(parsed, "summary"),
    }


def empty_quick_result() -> dict:
    return {
        "company": None,
        "role": None,
        "location": None,
        "location_country": None,
        "location_state": None,
        "location_city": None,
        "work_mode": None,
        "employment_type": None,
        "tags": [],
        "salary": _build_salary({}),
        "summary": None,
    }