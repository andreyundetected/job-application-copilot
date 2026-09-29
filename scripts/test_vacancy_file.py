import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.db import crud
from core.db.session import SessionLocal
from core.evaluator.pipeline import evaluate_job_posting
from core.providers.factory import get_llm_provider

VACANCIES_DIR = Path(__file__).resolve().parent.parent / "test_vacancies"
DEFAULT_FILE = VACANCIES_DIR / "vacancy.txt"
OUTPUT_PATH = config.OUTPUT_DIR / "vacancy_test.txt"

CHECK_RE = re.compile(r"<check>(.*?)</check>", re.DOTALL)
BUCKET_RE = re.compile(r"<(bucket|prep)>\s*([a-z]+)\s*</\1>")
TRIGGERED_RE = re.compile(r"result:\s*triggered", re.IGNORECASE)


def triggered_blockers(raw_response):
    return [" ".join(line.split()) for line in CHECK_RE.findall(raw_response) if TRIGGERED_RE.search(line)]


def bucket_of(raw_response):
    matches = BUCKET_RE.findall(raw_response)
    return matches[-1][1] if matches else None


def write_section(file, title):
    file.write("\n" + "=" * 100 + "\n" + title + "\n" + "=" * 100 + "\n\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", default=str(DEFAULT_FILE))
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        VACANCIES_DIR.mkdir(exist_ok=True)
        print(f"File not found: {path}")
        print(f"Put the vacancy text into {DEFAULT_FILE} (folder is created and git-ignored).")
        return

    job_text = path.read_text(encoding="utf-8").strip()
    if not job_text:
        print("Vacancy file is empty.")
        return

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
    finally:
        session.close()

    if resume is None:
        print("No active resume.")
        return

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    provider = get_llm_provider()
    scores = []

    print(f"vacancy file: {path} ({len(job_text)} chars)")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        file.write(f"provider: {config.LLM_PROVIDER}\nvacancy file: {path}\nruns: {args.runs}\n")
        write_section(file, "VACANCY TEXT")
        file.write(job_text + "\n")

        for index in range(1, args.runs + 1):
            try:
                result = evaluate_job_posting(
                    provider,
                    job_posting_text=job_text,
                    resume_text=resume.raw_text,
                    linkedin_text=linkedin.raw_text if linkedin else "",
                    blockers=blockers,
                    scoring_factors=scoring_factors,
                    extra_info=profile.extra_info if profile else None,
                )
            except Exception as error:
                write_section(file, f"RUN {index}: FAILED")
                file.write(f"{error!r}\n")
                print(f"run {index}: FAILED {error!r}")
                scores.append(None)
                continue

            raw_response = result["raw_response"]
            scores.append(result["score"])

            write_section(file, f"RUN {index}: RAW MODEL RESPONSE")
            file.write(raw_response + "\n")
            write_section(file, f"RUN {index}: PARSED")
            file.write(f"score: {result['score']}\ncons: {result['cons']}\npros: {result['pros']}\n")
            file.flush()

            print(
                f"run {index}: score={result['score']} bucket={bucket_of(raw_response)} "
                f"triggered={triggered_blockers(raw_response) or 'none'}"
            )
            print(f"  cons: {result['cons']}")
            print(f"  pros: {result['pros']}")

    print(f"scores: {scores}")
    print(f"full answers: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()