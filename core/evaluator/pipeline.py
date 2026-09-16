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
    )

    parsed = parse_html_like(raw_response)
    score = _parse_score(_first_or_none(parsed, "score"))

    return {
        "reasoning": _first_or_none(parsed, "reasoning"),
        "company": _first_or_none(parsed, "company"),
        "role": _first_or_none(parsed, "role"),
        "score": score,
        "location": _first_or_none(parsed, "location"),
        "work_mode": _first_or_none(parsed, "work_mode"),
        "salary": _build_salary(parsed),
        "matched_factors": _build_matched_factors(parsed, scoring_factors),
        "cons": parsed.get("con", []),
        "pros": parsed.get("pro", []),
        "summary": _first_or_none(parsed, "summary"),
        "verdict": bool(score) and score > 0,
        "raw_response": raw_response,
    }


def quick_extract_job_posting(provider, job_posting_text: str) -> dict:
    prompt = render_quick_extract_prompt(job_posting_text=job_posting_text)

    raw_response = provider.call(
        system_prompt="You extract short literal facts from a job posting as fast as possible.",
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)

    return {
        "company": _first_or_none(parsed, "company"),
        "role": _first_or_none(parsed, "role"),
        "location": _first_or_none(parsed, "location"),
        "work_mode": _first_or_none(parsed, "work_mode"),
        "employment_type": _first_or_none(parsed, "employment_type"),
        "tags": parsed.get("tag", []),
    }