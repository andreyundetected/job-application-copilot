import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.db import crud
from core.db.models import JobPosting
from core.db.session import SessionLocal
from core.evaluator.pipeline import evaluate_job_posting
from core.providers.factory import get_llm_provider

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "evaluation_debug.txt"
CONTEXT_PATH = config.OUTPUT_DIR / "evaluation_context.txt"

REMOTE_RE = re.compile(r"remote", re.IGNORECASE)
ONSITE_RE = re.compile(r"on-?site|in-?office|in the office|hybrid|office", re.IGNORECASE)


class _LoggingProvider:
    def __init__(self, inner):
        self.inner = inner
        self.calls: list[dict] = []

    def call(self, system_prompt, user_prompt, max_tokens=None, reasoning_effort=None, temperature=None):
        raw_response = self.inner.call(
            system_prompt,
            user_prompt,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
        )
        self.calls.append(
            {
                "prompt_length": len(user_prompt),
                "raw_response": raw_response,
                "usage": dict(getattr(self.inner, "last_usage", None) or {}),
            }
        )
        return raw_response


def write_section(file, title):
    file.write("\n" + "=" * 100 + "\n" + title + "\n" + "=" * 100 + "\n\n")


def active_model():
    return {
        "freellmapi": config.FREELLMAPI_MODEL,
        "openai": config.OPENAI_MODEL,
        "gemini": config.GEMINI_MODEL,
    }.get(config.LLM_PROVIDER)


def find_job(session, job_id, company):
    if job_id is not None:
        return crud.get_job_posting(session, job_id)
    return (
        session.query(JobPosting)
        .filter(JobPosting.company.ilike(f"%{company}%"))
        .order_by(JobPosting.id.desc())
        .first()
    )


def write_job_section(file, job, resume, linkedin, profile, blockers, scoring_factors, session):
    text = job.raw_text or ""

    write_section(file, "JOB")
    file.write(f"job_id: {job.id}\n")
    file.write(f"company: {job.company}\n")
    file.write(f"title: {job.title}\n")
    file.write(f"source_url: {job.source_url}\n")
    file.write(f"source: {job.source}\n")
    file.write(f"created_at: {job.created_at}\n")
    file.write(f"pipeline_stage: {job.pipeline_stage}\n")
    file.write(f"archived: {job.archived}\n")

    write_section(file, "STORED METADATA (extracted separately by quick-extract, the evaluator did NOT see this)")
    file.write(f"location: {job.location}\n")
    file.write(f"location_country: {job.location_country}\n")
    file.write(f"location_state: {job.location_state}\n")
    file.write(f"location_city: {job.location_city}\n")
    file.write(f"work_mode: {job.work_mode}\n")
    file.write(f"employment_type: {job.employment_type}\n")
    file.write(f"tags: {job.tags}\n")

    evaluations = crud.list_evaluations_for_job(session, job.id)
    if evaluations:
        latest = evaluations[0]
        checked = latest.checked_keywords or {}
        write_section(file, "PREVIOUS STORED EVALUATION (for comparison, not part of the input)")
        file.write(f"evaluation_id: {latest.id} created_at: {latest.created_at}\n")
        file.write(f"fit_score: {latest.fit_score}\n")
        file.write(f"pros: {(latest.fit_bullets or {}).get('pros')}\n")
        file.write(f"cons: {(latest.blocker_bullets or {}).get('cons')}\n")
        file.write(f"quick work_mode: {checked.get('work_mode')}\n")
        file.write(f"quick location: {checked.get('location')}\n")
        file.write(f"quick salary: {checked.get('salary')}\n")
        file.write(f"quick summary: {checked.get('summary')}\n")

    write_section(file, "SHARED CONTEXT USED (full text in " + str(CONTEXT_PATH) + ")")
    file.write(f"resume: id={resume.id} label={resume.label} length={len(resume.raw_text or '')}\n")
    if linkedin:
        file.write(f"linkedin: id={linkedin.id} label={linkedin.label} length={len(linkedin.raw_text or '')}\n")
    else:
        file.write("linkedin: none\n")
    file.write(f"extra_info length: {len((profile.extra_info or '') if profile else '')}\n")
    file.write(f"blockers: {len(blockers)}\n")
    file.write(f"scoring factors: {len(scoring_factors)}\n")

    write_section(file, "JOB POSTING TEXT (exactly what the evaluator received as the posting)")
    file.write(f"length: {len(text)} chars\n")
    file.write(f"contains a 'remote' word: {bool(REMOTE_RE.search(text))}\n")
    file.write(f"contains on-site / office / hybrid word: {bool(ONSITE_RE.search(text))}\n\n")
    file.write(text + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=int, default=None)
    parser.add_argument("--company", default="Dwelly")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        job = find_job(session, args.job_id, args.company)
        if job is None:
            print("Job not found.")
            return

        resume = crud.get_active_resume_version(session, "resume")
        linkedin = crud.get_active_resume_version(session, "linkedin")
        profile = crud.get_candidate_profile(session)
        blockers = [rule.text for rule in crud.list_blocker_rules(session)]
        scoring_factors = [
            {"id": f.id, "text": f.text, "direction": f.direction, "weight": f.weight}
            for f in crud.list_scoring_factors(session)
        ]

        if resume is None:
            print("No active resume.")
            return

        provider = _LoggingProvider(get_llm_provider())
        scores = []

        with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
            file.write(f"LLM_PROVIDER: {config.LLM_PROVIDER}\nMODEL: {active_model()}\nRUNS: {args.runs}\n")
            write_job_section(file, job, resume, linkedin, profile, blockers, scoring_factors, session)
            file.flush()

            for index in range(1, args.runs + 1):
                try:
                    result = evaluate_job_posting(
                        provider,
                        job_posting_text=job.raw_text,
                        resume_text=resume.raw_text,
                        linkedin_text=linkedin.raw_text if linkedin else "",
                        blockers=blockers,
                        scoring_factors=scoring_factors,
                        extra_info=profile.extra_info if profile else None,
                    )
                except Exception as error:
                    write_section(file, f"RUN {index}: FAILED")
                    file.write(f"{error!r}\n")
                    file.flush()
                    scores.append(None)
                    continue

                call = provider.calls[-1]
                scores.append(result["score"])

                write_section(
                    file, f"RUN {index}: RAW MODEL RESPONSE (prompt {call['prompt_length']} chars, usage: {call['usage']})"
                )
                file.write(call["raw_response"] + "\n")

                write_section(file, f"RUN {index}: PARSED")
                file.write(f"score: {result['score']}\n")
                file.write(f"verdict: {result['verdict']}\n")
                file.write(f"cons: {result['cons']}\n")
                file.write(f"pros: {result['pros']}\n")
                file.write(f"matched_factors: {[m['text'] for m in result['matched_factors']]}\n")
                file.flush()

        print(f"Job {job.id} {job.company} | {job.title}")
        print(f"Scores: {scores}")
        print(f"Wrote {OUTPUT_PATH}")
    finally:
        session.close()


if __name__ == "__main__":
    main()