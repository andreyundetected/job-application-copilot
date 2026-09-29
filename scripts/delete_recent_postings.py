import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import crud
from core.db.session import SessionLocal
from core.discovery_db.models import DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=float, default=1.0)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=args.hours)

    discovery_session = DiscoverySessionLocal()
    session = SessionLocal()
    try:
        rows = (
            discovery_session.query(DiscoveredJobPosting)
            .filter(DiscoveredJobPosting.posted_at.isnot(None), DiscoveredJobPosting.posted_at >= cutoff)
            .all()
        )
        undated_count = (
            discovery_session.query(DiscoveredJobPosting).filter(DiscoveredJobPosting.posted_at.is_(None)).count()
        )

        discovered_ids = [row.id for row in rows]
        job_ids = sorted({row.promoted_job_posting_id for row in rows if row.promoted_job_posting_id is not None})

        print(f"cutoff (utc): {cutoff.isoformat()}")
        print(f"discovered postings in window: {len(discovered_ids)}")
        print(f"linked job postings: {len(job_ids)}")
        print(f"undated postings left untouched: {undated_count}")

        protected_job_ids = {job_id for job_id in job_ids if crud.is_job_applied(session, job_id)}
        if protected_job_ids:
            print(f"protected (marked as applied), will be kept: {sorted(protected_job_ids)}")

        if not args.apply:
            print("dry run, pass --apply to delete")
            return

        deleted_jobs = 0
        for job_id in job_ids:
            if job_id in protected_job_ids:
                continue
            if crud.delete_job_posting(session, job_id):
                deleted_jobs += 1

        deletable_ids = [row.id for row in rows if row.promoted_job_posting_id not in protected_job_ids]
        deleted_discovered = 0
        if deletable_ids:
            deleted_discovered = (
                discovery_session.query(DiscoveredJobPosting)
                .filter(DiscoveredJobPosting.id.in_(deletable_ids))
                .delete(synchronize_session=False)
            )
            discovery_session.commit()

        print(f"deleted job postings: {deleted_jobs}")
        print(f"deleted discovered postings: {deleted_discovered}")
    finally:
        session.close()
        discovery_session.close()


if __name__ == "__main__":
    main()