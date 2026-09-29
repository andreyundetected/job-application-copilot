import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func

from core.db import crud
from core.db.models import JobPosting
from core.db.session import SessionLocal
from core.discovery_db.models import DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        empty_jobs = (
            session.query(JobPosting).filter(func.length(func.trim(JobPosting.raw_text)) == 0).all()
        )
        job_ids = [job.id for job in empty_jobs]

        print(f"jobs with empty raw_text: {len(job_ids)}")
        for job in empty_jobs:
            print(job.id, job.source, job.source_url)

        if not job_ids:
            return

        if not args.apply:
            print("dry run, pass --apply to delete")
            return

        discovery_session = DiscoverySessionLocal()
        try:
            unlinked = (
                discovery_session.query(DiscoveredJobPosting)
                .filter(DiscoveredJobPosting.promoted_job_posting_id.in_(job_ids))
                .update({DiscoveredJobPosting.promoted_job_posting_id: None}, synchronize_session=False)
            )
            discovery_session.commit()
            print(f"unlinked discovered postings: {unlinked}")
        finally:
            discovery_session.close()

        deleted = 0
        for job_id in job_ids:
            if crud.delete_job_posting(session, job_id):
                deleted += 1
        print(f"deleted jobs: {deleted}")
    finally:
        session.close()


if __name__ == "__main__":
    main()