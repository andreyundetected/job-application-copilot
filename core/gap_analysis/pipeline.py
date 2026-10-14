from core.gap_analysis.extraction import extract_keywords
from core.gap_analysis.keywords import classify_requirements


def run_full_gap_analysis(
    provider,
    job_posting_text: str,
    resume_html: str,
    linkedin_text: str,
    extra_info: str | None,
    max_attempts: int = 3,
    blocks: list[dict] | None = None,
    known_skills: list[str] | None = None,
) -> dict:
    from core.parsing.html_blocks import body_block_texts
    from core.parsing.html_to_text import html_to_text

    requirements = extract_keywords(provider, job_posting_text, max_attempts=max_attempts)
    block_texts = body_block_texts(resume_html, blocks or [])
    gap_items = classify_requirements(
        provider,
        requirements,
        block_texts,
        html_to_text(resume_html),
        linkedin_text,
        extra_info,
        known_skills or [],
    )

    return {"gap_items": gap_items, "resume_items": []}