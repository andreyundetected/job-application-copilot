"""Standalone diagnostic run of the gap-analysis pipeline against real data
from the local DB. Dumps only the LLM calls (prompts kept short/omitted,
raw responses in full) and parsed results, so the output stays small enough
to paste back for debugging.

Usage:
    python scripts/debug_gap_analysis.py [job_posting_id]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import crud
from core.db.session import SessionLocal
from core.gap_analysis.pipeline import (
    extract_job_requirements,
    extract_resume_items,
)
from core.gap_analysis.prompt import render_match_gap_items_prompt
from core.providers.factory import get_llm_provider
from core.providers.freellmapi import FreeLLMAPIProvider

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "gap_analysis_debug.txt"


class _LoggingProvider:
    def __init__(self, inner):
        self.inner = inner
        self.calls: list[dict] = []

    def call(self, system_prompt: str, user_prompt: str, max_tokens=None, reasoning_effort=None) -> str:
        raw_response = self.inner.call(
            system_prompt, user_prompt, max_tokens=max_tokens, reasoning_effort=reasoning_effort
        )
        self.calls.append({"prompt_len": len(user_prompt), "raw_response": raw_response})
        return raw_response


def _write_section(f, title: str):
    f.write("\n" + "=" * 100 + "\n" + title + "\n" + "=" * 100 + "\n\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("job_posting_id", nargs="?", type=int, default=None)
    parser.add_argument("--skip-match", action="store_true")
    parser.add_argument(
        "--model",
        default=None,
        help='Force a specific model instead of "auto" routing, e.g. --model gemini-2.5-flash',
    )
    args = parser.parse_args()

    session = SessionLocal()
    try:
        if args.job_posting_id is not None:
            job = crud.get_job_posting(session, args.job_posting_id)
        else:
            jobs = crud.list_job_postings(session, include_archived=True)
            job = jobs[0] if jobs else None

        if job is None:
            print("No job posting found in DB.")
            return

        resume = crud.get_active_resume_version(session, "resume")
        linkedin = crud.get_active_resume_version(session, "linkedin")
        profile = crud.get_candidate_profile(session)

        if resume is None or not resume.content_html:
            print("No active resume with content_html found.")
            return

        resume_html = resume.content_html
        linkedin_text = linkedin.raw_text if linkedin else ""
        extra_info = profile.extra_info if profile else None

        if args.model:
            inner_provider = FreeLLMAPIProvider()
            inner_provider.model = args.model
        else:
            inner_provider = get_llm_provider()

        provider = _LoggingProvider(inner_provider)

        print(f"Running against job_posting_id={job.id}, resume_version_id={resume.id}, model={args.model or 'auto'}...")

        requirements = extract_job_requirements(provider, job.raw_text)
        resume_items = extract_resume_items(provider, resume_html, linkedin_text, extra_info)

        gap_items = []
        if not args.skip_match:
            from core.gap_analysis.pipeline import match_gap_items

            gap_items = match_gap_items(provider, requirements, resume_items)
        print(f"requirements={len(requirements)} resume_items={len(resume_items)}")

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write(f"JOB POSTING ID: {job.id}\nRESUME VERSION ID: {resume.id}\n")

            for index, call in enumerate(provider.calls):
                if index == 0:
                    label = "extract_job_requirements"
                elif index == 1:
                    label = "extract_resume_items"
                else:
                    label = f"match_gap_items (batch {index - 1})"
                _write_section(f, f"CALL: {label} (prompt was {call['prompt_len']} chars, omitted)")
                f.write(f"RAW RESPONSE ({len(call['raw_response'])} chars):\n\n")
                f.write(call["raw_response"] + "\n")

            _write_section(f, "PARSED SUMMARY")
            f.write(f"requirements: {len(requirements)}\n")
            for r in requirements:
                f.write(f"  - {r}\n")
            f.write(f"\nresume_items: {len(resume_items)}\n")
            for r in resume_items:
                f.write(f"  - {r}\n")
            f.write(f"\ngap_items: {len(gap_items)}\n")
            for g in gap_items:
                f.write(f"  - {g}\n")

        print(f"Done. Wrote debug output to {OUTPUT_PATH}")
        print(f"requirements={len(requirements)} resume_items={len(resume_items)} gap_items={len(gap_items)}")

    finally:
        session.close()


if __name__ == "__main__":
    main()