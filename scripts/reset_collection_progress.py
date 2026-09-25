import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.discovery_db.models import DiscoveredCompany, DiscoveredJobPosting
from core.discovery_db.session import DiscoverySessionLocal
from core.discovery_db import crud as discovery_crud


def main():
    session = DiscoverySessionLocal()
    try:
        deleted_postings = session.query(DiscoveredJobPosting).delete(synchronize_session=False)
        session.commit()
        print(f"deleted {deleted_postings} discovered postings")

        updated_companies = session.query(DiscoveredCompany).update(
            {
                DiscoveredCompany.last_checked_at: None,
                DiscoveredCompany.next_check_at: None,
                DiscoveredCompany.last_activity_at: None,
                DiscoveredCompany.has_ever_had_postings: False,
                DiscoveredCompany.is_deleted: False,
                DiscoveredCompany.assigned_tier: None,
                DiscoveredCompany.consecutive_failures: 0,
            },
            synchronize_session=False,
        )
        session.commit()
        print(f"reset progress fields on {updated_companies} companies")

        discovery_crud.update_settings(session, initial_collection_done_at=None)
        session.commit()
        print("cleared initial_collection_done_at")

        remaining_companies = session.query(DiscoveredCompany).count()
        print(f"companies preserved: {remaining_companies}")
    finally:
        session.close()


if __name__ == "__main__":
    main()