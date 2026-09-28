import argparse
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


class _LoggingProvider:
    def __init__(self, inner):
        self.inner = inner
        self.calls: list[dict] = []

    def call(self, system_prompt, user_prompt, max_tokens=None, reasoning_effort=None):
        raw_response = self.inner.call(
            system_prompt, user_prompt, max_tokens=max_tokens, reasoning_effort=reasoning_effort
        )
        self.calls.append(
            {
                "prompt": user_prompt,
                "raw_response": raw_response,
                "usage": dict(getattr(self.inner, "last_usage", None) or {}),
            }
        )
        return raw_response


def _write_section(f, title: str):
    f.write("\n" + "=" * 100 + "\n" + title + "\n" + "=" * 100 + "\n\n")


def _find_job(session, job_id, company):
    if job_id is not None:
        return crud.get_job_posting(session, job_id)
    return (
        session.query(JobPosting)
        .filter(JobPosting.company.ilike(f"%{company}%"))
        .order_by(JobPosting.id.desc())
        .first()
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", type=int, default=None)
    parser.add_argument("--company", default="Dwelly")
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    session = SessionLocal()
    try:
        job = _find_job(session, args.job_id, args.company)
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
        results = []

        for _ in range(args.runs):
            results.append(
                evaluate_job_posting(
                    provider,
                    job_posting_text=job.raw_text,
                    resume_text=resume.raw_text,
                    linkedin_text=linkedin.raw_text if linkedin else "",
                    blockers=blockers,
                    scoring_factors=scoring_factors,
                    extra_info=profile.extra_info if profile else None,
                )
            )

        first_prompt = provider.calls[0]["prompt"]
        tail = job.raw_text.strip()[-200:]

        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write(f"JOB ID: {job.id}\nCOMPANY: {job.company}\nROLE: {job.title}\n")
            f.write(f"LLM_PROVIDER: {config.LLM_PROVIDER}\n")
            f.write(f"GEMINI_MODEL: {config.GEMINI_MODEL}\nFREELLMAPI_MODEL: {config.FREELLMAPI_MODEL}\n")

            _write_section(f, "INPUT CHECK")
            f.write(f"raw_text length: {len(job.raw_text)} chars\n")
            f.write(f"prompt length: {len(first_prompt)} chars\n")
            f.write(f"posting tail present in prompt: {tail in first_prompt}\n")
            f.write(f"'Bachelor' in raw_text: {'Bachelor' in job.raw_text}\n")
            f.write(f"'Bachelor' in prompt: {'Bachelor' in first_prompt}\n")
            f.write(f"'TypeScript' in raw_text: {'TypeScript' in job.raw_text}\n")
            f.write(f"'TypeScript' in resume raw_text: {'TypeScript' in resume.raw_text}\n")
            f.write(f"'TypeScript' in linkedin raw_text: {'TypeScript' in (linkedin.raw_text if linkedin else '')}\n")
            f.write(f"'TypeScript' in extra_info: {'TypeScript' in ((profile.extra_info or '') if profile else '')}\n")
            f.write(f"\nlast 700 chars of raw_text:\n{job.raw_text[-700:]}\n")

            _write_section(f, "BLOCKERS")
            for index, text in enumerate(blockers, start=1):
                f.write(f"{index}. {text}\n")

            for index, (call, result) in enumerate(zip(provider.calls, results), start=1):
                _write_section(f, f"RUN {index}: RAW MODEL RESPONSE (usage: {call['usage']})")
                f.write(call["raw_response"] + "\n")

                _write_section(f, f"RUN {index}: PARSED")
                f.write(f"score: {result['score']}\n")
                f.write(f"verdict: {result['verdict']}\n")
                f.write(f"cons: {result['cons']}\n")
                f.write(f"pros: {result['pros']}\n")
                f.write(f"matched_factors: {[m['text'] for m in result['matched_factors']]}\n")

            _write_section(f, "FULL PROMPT OF RUN 1")
            f.write(first_prompt + "\n")

        print(f"Done. Scores: {[r['score'] for r in results]}")
        print(f"Wrote {OUTPUT_PATH}")
    finally:
        session.close()


if __name__ == "__main__":
    main()