import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import crud
from core.db.session import SessionLocal


def main():
    session = SessionLocal()
    try:
        jobs = crud.list_job_postings(session, include_archived=True)
        created = 0
        for job in jobs:
            evaluations = crud.list_evaluations_for_job(session, job.id)
            if not evaluations:
                continue
            existing = [a for a in crud.list_applications(session) if a.job_posting_id == job.id]
            if existing:
                continue
            crud.create_application(session, job_posting_id=job.id, source_platform="backfill")
            created += 1
        print(f"created {created} missing applications")
    finally:
        session.close()


if __name__ == "__main__":
    main()