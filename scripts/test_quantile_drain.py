import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.discovery import run_control
from core.discovery.poll_cycle import run_one_live_quantile_cycle
from core.discovery.quantile_queue import LIVE_QUANTILE_COUNT
from core.discovery_db import crud as discovery_crud
from core.discovery_db.session import DiscoverySessionLocal


def main():
    session = DiscoverySessionLocal()
    try:
        sizes = discovery_crud.get_quantile_sizes(session, LIVE_QUANTILE_COUNT)
    finally:
        session.close()

    print(f"quantile sizes before cycle: {sizes}")

    run_control.reset_run()
    t0 = time.monotonic()
    found = run_one_live_quantile_cycle()
    elapsed = time.monotonic() - t0

    processed = run_control.get_tier_processed_counts()
    print(f"cycle took {elapsed:.1f}s, found {found} new postings")
    print(f"processed per quantile: {processed}")

    for i in range(LIVE_QUANTILE_COUNT):
        expected = sizes[i]
        actual = processed.get(i, 0)
        status = "OK" if actual >= expected else "MISMATCH"
        print(f"  quantile {i}: expected>={expected}, processed={actual}  [{status}]")


if __name__ == "__main__":
    main()