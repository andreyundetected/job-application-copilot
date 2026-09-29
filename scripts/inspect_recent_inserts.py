import argparse
import datetime
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.discovery_db.models import DiscoveredCompany, DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal


def bucket(posted_at, now):
    if posted_at is None:
        return "no_date"
    age = now - posted_at
    if age <= datetime.timedelta(hours=1):
        return "0-1h"
    if age <= datetime.timedelta(hours=24):
        return "1-24h"
    if age <= datetime.timedelta(days=7):
        return "1-7d"
    return "older"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=10)
    args = parser.parse_args()

    now = datetime.datetime.utcnow()
    since = now - datetime.timedelta(minutes=args.minutes)

    session = DiscoverySessionLocal()
    try:
        rows = (
            session.query(DiscoveredJobPosting.posted_at, DiscoveredCompany.ats_name)
            .join(DiscoveredCompany, DiscoveredJobPosting.company_id == DiscoveredCompany.id)
            .filter(DiscoveredJobPosting.first_seen_at >= since)
            .all()
        )
    finally:
        session.close()

    print(f"inserted in last {args.minutes} min: {len(rows)}")
    print("by age of posted_at:", dict(Counter(bucket(posted_at, now) for posted_at, _ in rows)))
    print("by ats:", dict(Counter(ats for _, ats in rows)))
    per_ats = Counter((ats, bucket(posted_at, now)) for posted_at, ats in rows)
    for key in sorted(per_ats):
        print(" ", key, per_ats[key])


if __name__ == "__main__":
    main()