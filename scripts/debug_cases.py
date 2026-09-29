import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

import config
from core.db import crud
from core.db.models import JobPosting
from core.db.session import SessionLocal
from core.evaluator.pipeline import evaluate_job_posting
from core.providers.factory import get_llm_provider

ASHBY_RE = re.compile(r"jobs\.ashbyhq\.com/([^/]+)/([^/?#]+)")
ASHBY_KEYS = ("location", "secondaryLocations", "address", "isRemote", "workplaceType", "employmentType")
REMOTE_RE = re.compile(r"remote", re.IGNORECASE)
ONSITE_RE = re.compile(r"on-?site|in-?office|in the office|hybrid|office", re.IGNORECASE)
OUTPUT_DIR = config.OUTPUT_DIR / "debug_cases"


def ashby_raw(url):
    match = ASHBY_RE.search(url or "")
    if not match:
        return None
    slug, job_id = match.groups()
    response = requests.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{slug}", params={"includeCompensation": "false"}, timeout=20
    )
    if response.status_code != 200:
        return {"error": response.status_code}
    for posting in response.json().get("jobs") or []:
        if posting.get("id") == job_id or str(posting.get("jobUrl", "")).rstrip("/").endswith(job_id):
            return {key: posting.get(key) for key in ASHBY_KEYS}
    return {"error": "posting not found in board"}


def safe_name(value):
    return re.sub(r"[^\w-]+", "_", value or "unknown")[:40]


def pick_jobs(session, name, limit, min_score):
    jobs = (
        session.query(JobPosting).filter(JobPosting.company.ilike(f"%{name}%")).order_by(JobPosting.id.desc()).all()
    )
    picked = []
    for job in jobs:
        evaluations = crud.list_evaluations_for_job(session, job.id)
        score = evaluations[0].fit_score if evaluations else None
        if score is not None and score >= min_score:
            picked.append((job, score))
        if len(picked) >= limit:
            break
    return picked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("companies", nargs="+")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--min-score", type=int, default=7)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    session = SessionLocal()
    try:
        resume = crud.get_active_resume_version(session, "resume")
        linkedin = crud.get_active_resume_version(session, "linkedin")
        profile = crud.get_candidate_profile(session)
        blockers = [rule.text for rule in crud.list_blocker_rules(session)]
        scoring_factors = [
            {"id": f.id, "text": f.text, "direction": f.direction, "weight": f.weight}
            for f in crud.list_scoring_factors(session)
        ]
        if resume is None:
            print("no active resume")
            return

        print("BLOCKERS:")
        for index, text in enumerate(blockers, start=1):
            print(f"  {index}. {text}")

        provider = get_llm_provider()

        for name in args.companies:
            picked = pick_jobs(session, name, args.jobs, args.min_score)
            print("\n" + "=" * 90)
            print(f"{name}: {len(picked)} jobs with score >= {args.min_score}")

            for job, stored_score in picked:
                text = job.raw_text or ""
                print("-" * 90)
                print(f"job_id={job.id} company={job.company} title={job.title}")
                print(f"url={job.source_url}")
                print(f"stored: score={stored_score} work_mode={job.work_mode} location={job.location}")
                print(
                    f"raw_text length={len(text)} has_remote_word={bool(REMOTE_RE.search(text))} "
                    f"has_onsite_or_office_word={bool(ONSITE_RE.search(text))}"
                )
                print("head: " + text[:500].replace("\n", " | "))

                raw = ashby_raw(job.source_url)
                if raw is not None:
                    print(f"ashby api fields: {raw}")

                scores = []
                lines = [f"JOB {job.id} {job.company} | {job.title}", f"URL {job.source_url}", "", text[:1500], ""]
                for run in range(1, args.runs + 1):
                    result = evaluate_job_posting(
                        provider,
                        job_posting_text=text,
                        resume_text=resume.raw_text,
                        linkedin_text=linkedin.raw_text if linkedin else "",
                        blockers=blockers,
                        scoring_factors=scoring_factors,
                        extra_info=profile.extra_info if profile else None,
                    )
                    scores.append(result["score"])
                    lines += [f"===== RUN {run} score={result['score']} =====", result["raw_response"], ""]

                path = OUTPUT_DIR / f"{job.id}_{safe_name(job.company)}.txt"
                path.write_text("\n".join(lines), encoding="utf-8")
                print(f"scores over {args.runs} runs: {scores} -> {path}")
    finally:
        session.close()


if __name__ == "__main__":
    main()