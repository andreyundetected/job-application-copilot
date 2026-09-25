import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.discovery.quantile_queue import LIVE_QUANTILE_COUNT
from core.discovery_db import crud as discovery_crud
from core.discovery_db.models import DiscoveredCompany
from core.discovery_db.session import DiscoverySessionLocal


def main():
    session = DiscoverySessionLocal()
    try:
        cold_company = (
            session.query(DiscoveredCompany)
            .filter(DiscoveredCompany.has_ever_had_postings.is_(True), DiscoveredCompany.last_activity_at.isnot(None))
            .order_by(DiscoveredCompany.last_activity_at.asc())
            .first()
        )
        if cold_company is None:
            print("no company with a dated last_activity_at found, aborting")
            return

        print(f"picked coldest company: id={cold_company.id} slug={cold_company.slug} last_activity_at={cold_company.last_activity_at}")

        before = discovery_crud.list_companies_in_rank_quantile(session, 0, LIVE_QUANTILE_COUNT, 100000)
        was_in_q0 = any(c.id == cold_company.id for c in before)
        print(f"before: in quantile 0? {was_in_q0}")

        cold_company.last_activity_at = datetime.datetime.utcnow()
        session.commit()
        print("simulated a brand-new posting for this company (set last_activity_at = now)")

        after = discovery_crud.list_companies_in_rank_quantile(session, 0, LIVE_QUANTILE_COUNT, 100000)
        is_in_q0_now = any(c.id == cold_company.id for c in after)
        print(f"after: in quantile 0? {is_in_q0_now}")

        if not was_in_q0 and is_in_q0_now:
            print("PASS: company moved into quantile 0 immediately after becoming the freshest")
        else:
            print("FAIL: ranking did not update as expected")
    finally:
        session.close()


if __name__ == "__main__":
    main()