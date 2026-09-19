from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core.parsing.html_like_parser import parse_html_like

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_DEFAULT_ATS_SITES = [
    "boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
]


def suggest_search_terms(provider, candidate_context: str) -> list[str]:
    template = _env.get_template("suggest_terms_prompt.jinja")
    prompt = template.render(candidate_context=candidate_context)

    raw_response = provider.call(
        system_prompt="You suggest concise job-title search synonyms for a job search query.",
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)
    return [term for term in parsed.get("term", []) if isinstance(term, str) and term.strip()]


def build_site_filter(sites: list[str] | None = None) -> str:
    sites = sites or _DEFAULT_ATS_SITES
    return "(" + " OR ".join(f"site:{site}" for site in sites) + ")"


def chunk_terms(terms: list[str], chunk_size: int) -> list[list[str]]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")

    return [terms[i : i + chunk_size] for i in range(0, len(terms), chunk_size)]


def build_queries(terms: list[str], chunk_size: int, sites: list[str] | None = None) -> list[str]:
    site_filter = build_site_filter(sites)
    queries = []

    for chunk in chunk_terms(terms, chunk_size):
        role_filter = "(" + " OR ".join(f'"{term}"' for term in chunk) + ")"
        queries.append(f"{site_filter} {role_filter}")

    return queries