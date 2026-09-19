from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core.parsing.html_like_parser import parse_html_like

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_VALID_VERDICTS = {"skip", "proceed"}


def render_quick_filter_prompt(
    search_results: list[dict],
    resume_text: str,
    linkedin_text: str,
    blockers: list[str],
    extra_info: str | None = None,
) -> str:
    template = _env.get_template("quick_filter_prompt.jinja")
    return template.render(
        search_results=search_results,
        resume_text=resume_text,
        linkedin_text=linkedin_text,
        blockers=blockers,
        extra_info=extra_info or "",
    )


def quick_filter_search_results(
    provider,
    search_results: list[dict],
    resume_text: str,
    linkedin_text: str,
    blockers: list[str],
    extra_info: str | None = None,
) -> dict[int, str]:
    """search_results: list of {"id": int, "title": str, "snippet": str, "url": str}.
    Returns {id: "skip" | "proceed"} - every id gets a verdict, missing/invalid ones
    default to "proceed" since this filter is meant to fail open."""
    if not search_results:
        return {}

    prompt = render_quick_filter_prompt(
        search_results, resume_text, linkedin_text, blockers, extra_info
    )

    raw_response = provider.call(
        system_prompt=(
            "You are a fast, lenient pre-filter for job search results. Your only job is to "
            "rule out results that are clearly irrelevant - anything uncertain proceeds to a "
            "more thorough evaluator."
        ),
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)
    verdicts: dict[int, str] = {}

    for item in parsed.get("verdict", []):
        if isinstance(item, str):
            continue
        id_raw = item.get("id")
        if not id_raw or not str(id_raw).isdigit():
            continue
        result_id = int(id_raw)
        verdict = (item.get("text") or "").strip().lower()
        verdicts[result_id] = verdict if verdict in _VALID_VERDICTS else "proceed"

    for result in search_results:
        if result["id"] not in verdicts:
            verdicts[result["id"]] = "proceed"

    return verdicts