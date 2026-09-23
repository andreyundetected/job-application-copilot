from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core.discovery.ats import default_target_sites
from core.parsing.html_like_parser import parse_html_like

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

DEFAULT_TARGET_SITES = default_target_sites()

PLANNED_TARGET_SITES = [
    "jobs.gem.com",
    "ats.rippling.com",
]

DEFAULT_MAX_QUERY_WORDS = 32


def build_site_filter(sites: list[str] | None = None) -> str:
    sites = sites or DEFAULT_TARGET_SITES
    return "(" + " OR ".join(f"site:{site}" for site in sites) + ")"


def count_words(text: str) -> int:
    return len(text.split())


def build_query_string(terms: list[str], sites: list[str] | None = None) -> str:
    site_filter = build_site_filter(sites)
    if not terms:
        return site_filter
    role_filter = "(" + " OR ".join(f'"{term}"' for term in terms) + ")"
    return f"{site_filter} {role_filter}"


def validate_query_length(query: str, max_words: int = DEFAULT_MAX_QUERY_WORDS) -> bool:
    return count_words(query) <= max_words


def fit_query_to_word_limit(
    terms: list[str], sites: list[str] | None = None, max_words: int = DEFAULT_MAX_QUERY_WORDS
) -> str | None:
    for count in range(len(terms), 0, -1):
        candidate = build_query_string(terms[:count], sites)
        if validate_query_length(candidate, max_words):
            return candidate
    return None


def build_catch_all_queries(sites: list[str] | None = None) -> list[str]:
    sites = sites or DEFAULT_TARGET_SITES
    return [f"site:{site}" for site in sites]


def suggest_search_queries(
    provider,
    candidate_context: str,
    sites: list[str] | None = None,
    max_query_words: int = DEFAULT_MAX_QUERY_WORDS,
) -> list[list[str]]:
    site_filter = build_site_filter(sites)
    site_filter_word_count = count_words(site_filter)
    terms_budget = max(1, max_query_words - site_filter_word_count)

    template = _env.get_template("suggest_queries_prompt.jinja")
    prompt = template.render(
        candidate_context=candidate_context,
        max_query_words=max_query_words,
        site_filter_word_count=site_filter_word_count,
        terms_budget=terms_budget,
        site_filter_preview=site_filter,
    )

    raw_response = provider.call(
        system_prompt=(
            "You suggest job-title search terms for a job search, split into separate "
            "queries that each respect a strict word limit."
        ),
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)
    groups: list[list[str]] = []

    for item in parsed.get("query", []):
        if isinstance(item, str):
            continue
        terms = [term for term in item.get("term", []) if isinstance(term, str) and term.strip()]
        if terms:
            groups.append(terms)

    return groups