import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from core.db.models import JobPosting
from core.db.session import SessionLocal

URL_RE = re.compile(r"([a-z0-9-]+)\.bamboohr\.com/careers/(\d+)")


def describe(value, depth=0, max_depth=3):
    pad = "  " * depth
    if isinstance(value, dict) and depth < max_depth:
        for key, item in value.items():
            kind = type(item).__name__
            preview = ""
            if isinstance(item, str):
                preview = f" len={len(item)} {item[:60]!r}"
            print(f"{pad}{key}: {kind}{preview}")
            describe(item, depth + 1, max_depth)


def main():
    session = SessionLocal()
    try:
        jobs = (
            session.query(JobPosting)
            .filter(JobPosting.source_url.like("%bamboohr.com%"))
            .order_by(JobPosting.id.desc())
            .all()
        )
    finally:
        session.close()

    print(f"bamboohr jobs in db: {len(jobs)}")
    empty = [job for job in jobs if len((job.raw_text or "").strip()) < 200]
    print(f"with raw_text shorter than 200 chars: {len(empty)}")
    for job in jobs[:15]:
        print(job.id, len(job.raw_text or ""), job.company, job.title, job.source_url)

    if not jobs:
        return

    match = URL_RE.search(jobs[0].source_url)
    if not match:
        print("cannot parse url", jobs[0].source_url)
        return

    slug, job_id = match.groups()
    api_url = f"https://{slug}.bamboohr.com/careers/{job_id}/detail"
    response = requests.get(api_url, headers={"Accept": "application/json"}, timeout=20)
    print("\nGET", api_url, "->", response.status_code)

    try:
        data = response.json()
    except ValueError:
        print(response.text[:1500])
        return

    print("\nstructure:")
    describe(data)
    print("\nraw json (first 3000 chars):")
    print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()