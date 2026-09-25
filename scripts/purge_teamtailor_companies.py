import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.discovery_db.models import DiscoveredCompany, DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal


def main():
    session = DiscoverySessionLocal()
    try:
        company_ids = [
            row[0]
            for row in session.query(DiscoveredCompany.id)
            .filter(DiscoveredCompany.ats_name == "teamtailor")
            .all()
        ]
        print(f"found {len(company_ids)} teamtailor companies")

        if not company_ids:
            return

        deleted_postings = (
            session.query(DiscoveredJobPosting)
            .filter(DiscoveredJobPosting.company_id.in_(company_ids))
            .delete(synchronize_session=False)
        )
        deleted_companies = (
            session.query(DiscoveredCompany)
            .filter(DiscoveredCompany.ats_name == "teamtailor")
            .delete(synchronize_session=False)
        )
        session.commit()

        print(f"deleted {deleted_postings} postings, {deleted_companies} companies")
    finally:
        session.close()


if __name__ == "__main__":
    main()