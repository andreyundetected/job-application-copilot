import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.discovery.ats import all_extractors
from core.discovery.rate_limiter import throttle
from core.discovery_db.models import DiscoveredCompany, DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal

_TARGET_ATS = {"personio", "recruitee"}


def main():
    extractors = {e.name: e for e in all_extractors() if e.name in _TARGET_ATS}

    session = DiscoverySessionLocal()
    try:
        companies = (
            session.query(DiscoveredCompany)
            .filter(DiscoveredCompany.ats_name.in_(_TARGET_ATS), DiscoveredCompany.is_deleted.is_(False))
            .all()
        )
        print(f"found {len(companies)} companies to backfill across {list(_TARGET_ATS)}")

        updated_total = 0
        for index, company in enumerate(companies, start=1):
            extractor = extractors.get(company.ats_name)
            if extractor is None:
                continue

            try:
                throttle(company.ats_name)
                postings = extractor.list_active_postings(company.slug)
            except Exception as error:
                print(f"[{index}/{len(companies)}] {company.ats_name}/{company.slug}: fetch failed: {error}")
                continue

            if not postings:
                continue

            posted_at_by_external_id = {p["external_id"]: p["posted_at"] for p in postings if p.get("posted_at")}
            if not posted_at_by_external_id:
                continue

            existing_rows = (
                session.query(DiscoveredJobPosting)
                .filter(
                    DiscoveredJobPosting.company_id == company.id,
                    DiscoveredJobPosting.posted_at.is_(None),
                    DiscoveredJobPosting.external_id.in_(posted_at_by_external_id.keys()),
                )
                .all()
            )

            for row in existing_rows:
                row.posted_at = posted_at_by_external_id[row.external_id]
                updated_total += 1

            if existing_rows:
                session.commit()
                print(f"[{index}/{len(companies)}] {company.ats_name}/{company.slug}: backfilled {len(existing_rows)} postings")

        print(f"done, {updated_total} postings backfilled total")
    finally:
        session.close()


if __name__ == "__main__":
    main()