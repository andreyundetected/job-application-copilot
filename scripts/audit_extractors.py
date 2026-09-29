import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func

from core.discovery.ats import all_extractors, is_usable_job_text
from core.discovery.rate_limiter import throttle
from core.discovery_db.models import DiscoveredCompany
from core.discovery_db.session import DiscoverySessionLocal

HTML_MARKERS = ("<p>", "<li>", "<div", "<br", "&lt;", "&nbsp;", "&amp;nbsp")


def pick_companies(session, ats_name, limit):
    return (
        session.query(DiscoveredCompany)
        .filter(
            DiscoveredCompany.ats_name == ats_name,
            DiscoveredCompany.is_deleted.is_(False),
            DiscoveredCompany.has_ever_had_postings.is_(True),
        )
        .order_by(func.random())
        .limit(limit)
        .all()
    )


def audit_ats(session, extractor, companies_limit, per_company):
    stats = {
        "companies": 0,
        "companies_with_postings": 0,
        "extracted": 0,
        "none": 0,
        "unusable": 0,
        "html_leak": 0,
        "no_date": 0,
        "errors": 0,
    }
    examples = []

    for company in pick_companies(session, extractor.name, companies_limit):
        stats["companies"] += 1
        try:
            throttle(extractor.name)
            postings = extractor.list_active_postings(company.slug)
        except Exception as error:
            stats["errors"] += 1
            examples.append(f"list error {company.slug}: {error!r}")
            continue

        if not postings:
            continue
        stats["companies_with_postings"] += 1

        for posting in random.sample(postings, min(per_company, len(postings))):
            stats["extracted"] += 1
            if posting.get("posted_at") is None and not extractor.supports_posted_at_lookup:
                stats["no_date"] += 1

            try:
                throttle(extractor.name)
                text = extractor.extract(posting["url"])
            except Exception as error:
                stats["errors"] += 1
                examples.append(f"extract error {posting['url']}: {error!r}")
                continue

            if text is None:
                stats["none"] += 1
                examples.append(f"NONE {posting['url']}")
                continue

            if not is_usable_job_text(text):
                stats["unusable"] += 1
                examples.append(f"SHORT({len(text.strip())}) {posting['url']}")

            if any(marker in text for marker in HTML_MARKERS):
                stats["html_leak"] += 1
                examples.append(f"HTML_LEAK {posting['url']}")

    return stats, examples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ats", nargs="*")
    parser.add_argument("--companies", type=int, default=12)
    parser.add_argument("--per-company", type=int, default=2)
    args = parser.parse_args()

    session = DiscoverySessionLocal()
    try:
        for extractor in all_extractors():
            if args.ats and extractor.name not in args.ats:
                continue

            print("=" * 80)
            print(extractor.name, flush=True)
            stats, examples = audit_ats(session, extractor, args.companies, args.per_company)
            print(" ", stats)
            for line in examples[:8]:
                print("   ", line)
    finally:
        session.close()


if __name__ == "__main__":
    main()