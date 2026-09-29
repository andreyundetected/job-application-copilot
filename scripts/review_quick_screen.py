import argparse
import datetime
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.db import crud
from core.db.session import SessionLocal
from core.discovery_db.models import DiscoveredCompany, DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal

INCLUDE_WORDS = [
    "ai", "llm", "ml", "genai", "nlp", "machine learning", "generative", "python", "backend", "back-end",
    "back end", "software engineer", "software developer", "developer", "full stack", "fullstack", "full-stack",
    "data engineer", "forward deployed", "agent", "agents", "applied", "founding", "platform engineer",
    "automation", "integration", "integrations", "solutions engineer", "solutions architect", "engineer",
]

EXCLUDE_WORDS = [
    "intern", "internship", "trainee", "working student", "werkstudent", "student", "sales", "account executive",
    "recruiter", "nurse", "driver", "warehouse", "cashier", "teacher", "dentist", "dental", "chef", "cook",
    "mechanic", "electrician", "technician", "accountant", "marketing", "designer", "receptionist",
]


def compile_words(words):
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(w) for w in words) + r")(?![a-z0-9])", re.IGNORECASE)


INCLUDE_RE = compile_words(INCLUDE_WORDS)
EXCLUDE_RE = compile_words(EXCLUDE_WORDS)


def is_contested(title):
    if not title:
        return False
    return bool(INCLUDE_RE.search(title)) and not EXCLUDE_RE.search(title)


def latest_score(session, job_id):
    evaluations = crud.list_evaluations_for_job(session, job_id)
    if not evaluations:
        return None
    return evaluations[0].fit_score


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=3.0)
    args = parser.parse_args()

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=args.hours)

    discovery_session = DiscoverySessionLocal()
    main_session = SessionLocal()
    try:
        rows = (
            discovery_session.query(DiscoveredJobPosting, DiscoveredCompany)
            .join(DiscoveredCompany, DiscoveredJobPosting.company_id == DiscoveredCompany.id)
            .filter(DiscoveredJobPosting.first_seen_at >= cutoff)
            .all()
        )

        discarded = []
        passed = []
        undecided = 0

        for posting, company in rows:
            if posting.discarded_by_quick_screen:
                discarded.append((posting, company))
            elif posting.promoted_job_posting_id is not None:
                passed.append((posting, company))
            else:
                undecided += 1

        print(f"window: last {args.hours}h, found: {len(rows)}")
        print(f"skipped by quick-screen: {len(discarded)}")
        print(f"passed to evaluation: {len(passed)}")
        print(f"undecided (age filter / not screened yet): {undecided}")

        by_ats = Counter()
        skipped_by_ats = Counter()
        for posting, company in discarded + passed:
            by_ats[company.ats_name] += 1
        for posting, company in discarded:
            skipped_by_ats[company.ats_name] += 1
        for ats_name in sorted(by_ats):
            print(f"  {ats_name}: {skipped_by_ats[ats_name]} skipped of {by_ats[ats_name]} screened")

        config.OUTPUT_DIR.mkdir(exist_ok=True)

        contested = [(p, c) for p, c in discarded if is_contested(p.title)]
        seen_titles = set()
        contested_path = config.OUTPUT_DIR / "quick_screen_contested_skipped.txt"
        written = 0
        with open(contested_path, "w", encoding="utf-8") as file:
            for posting, company in contested:
                key = ((posting.title or "").strip().lower(), company.slug)
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                file.write(f"{posting.title} | {company.slug} | {company.ats_name}\n")
                written += 1
        print(f"contested skipped written: {written} -> {contested_path}")

        passed_path = config.OUTPUT_DIR / "quick_screen_passed_with_scores.txt"
        scored = []
        for posting, company in passed:
            job = crud.get_job_posting(main_session, posting.promoted_job_posting_id)
            score = latest_score(main_session, job.id) if job else None
            scored.append((score if score is not None else -1, posting, company))
        scored.sort(key=lambda item: item[0])
        with open(passed_path, "w", encoding="utf-8") as file:
            for score, posting, company in scored:
                label = "n/a" if score == -1 else str(score)
                file.write(f"{label} | {posting.title} | {company.slug} | {company.ats_name}\n")
        print(f"passed with scores written: {len(scored)} -> {passed_path}")

        all_skipped_path = config.OUTPUT_DIR / "quick_screen_all_skipped.txt"
        with open(all_skipped_path, "w", encoding="utf-8") as file:
            for posting, company in discarded:
                file.write(f"{posting.title} | {company.slug} | {company.ats_name}\n")
        print(f"all skipped written: {len(discarded)} -> {all_skipped_path}")
    finally:
        main_session.close()
        discovery_session.close()


if __name__ == "__main__":
    main()