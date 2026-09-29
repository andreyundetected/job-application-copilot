import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.discovery.ats import all_extractors
from core.discovery_db.models import DiscoveredCompany
from core.discovery_db.session import DiscoverySessionLocal

MIN_LENGTH = 300
COMPANIES_TO_TRY = 25
POSTINGS_PER_ATS = 3
HTML_MARKERS = ("<p>", "<li>", "<div", "<br", "&lt;", "&amp;nbsp")


def flags_for(text):
    if text is None:
        return ["NONE"]
    flags = []
    if not text.strip():
        flags.append("EMPTY")
    elif len(text) < MIN_LENGTH:
        flags.append("SHORT")
    if any(marker in text for marker in HTML_MARKERS):
        flags.append("HTML_LEAK")
    return flags


def find_postings(session, extractor):
    companies = (
        session.query(DiscoveredCompany)
        .filter(DiscoveredCompany.ats_name == extractor.name, DiscoveredCompany.is_deleted.is_(False))
        .order_by(DiscoveredCompany.id.asc())
        .limit(COMPANIES_TO_TRY)
        .all()
    )
    for company in companies:
        try:
            postings = extractor.list_active_postings(company.slug)
        except Exception as error:
            print(f"  list failed for {company.slug}: {error}")
            continue
        if postings:
            return company.slug, postings
    return None, []


def main():
    only = set(sys.argv[1:])
    session = DiscoverySessionLocal()
    try:
        for extractor in all_extractors():
            if only and extractor.name not in only:
                continue

            print("=" * 90)
            print(extractor.name)
            slug, postings = find_postings(session, extractor)
            if not postings:
                print("  no company with postings found in db")
                continue

            print(f"  slug={slug} postings_listed={len(postings)}")
            for posting in postings[:POSTINGS_PER_ATS]:
                url = posting["url"]
                try:
                    text = extractor.extract(url)
                except Exception as error:
                    print(f"  ERROR {url}: {error!r}")
                    continue

                flags = flags_for(text)
                posted_at = posting.get("posted_at")
                if posted_at is None and extractor.supports_posted_at_lookup:
                    try:
                        posted_at = extractor.fetch_posted_at(slug, posting["external_id"])
                    except Exception as error:
                        posted_at = f"lookup error {error!r}"

                print(f"  url={url}")
                print(f"  length={len(text) if text else 0} posted_at={posted_at} flags={flags or 'ok'}")
                if text:
                    print("  start: " + text[:320].replace("\n", " | "))
                print()
    finally:
        session.close()


if __name__ == "__main__":
    main()