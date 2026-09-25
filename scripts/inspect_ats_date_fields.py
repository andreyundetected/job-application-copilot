import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from core.discovery_db.models import DiscoveredCompany
from core.discovery_db.session import DiscoverySessionLocal

TIMEOUT = 20


def _print_section(ats_name: str):
    print("\n" + "=" * 100)
    print(ats_name)
    print("=" * 100)


def inspect_greenhouse(slug: str):
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
    response = requests.get(url, params={"content": "false"}, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"status={response.status_code}")
        return False
    jobs = response.json().get("jobs") or []
    if not jobs:
        print("no jobs")
        return False
    print(json.dumps(jobs[0], indent=2, default=str)[:2000])


def inspect_lever(slug: str):
    url = f"https://api.lever.co/v0/postings/{slug}"
    response = requests.get(url, params={"mode": "json"}, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"status={response.status_code}")
        return False
    postings = response.json()
    if not isinstance(postings, list) or not postings:
        print("no postings")
        return False
    print(json.dumps(postings[0], indent=2, default=str)[:2000])


def inspect_ashby(slug: str):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    response = requests.get(url, params={"includeCompensation": "false"}, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"status={response.status_code}")
        return False
    jobs = response.json().get("jobs") or []
    if not jobs:
        print("no jobs")
        return False
    print(json.dumps(jobs[0], indent=2, default=str)[:2000])


def inspect_smartrecruiters(slug: str):
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
    response = requests.get(url, params={"limit": 5}, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"status={response.status_code}")
        return False
    content = response.json().get("content") or []
    if not content:
        print("no postings")
        return False
    print(json.dumps(content[0], indent=2, default=str)[:2000])


def inspect_workable(slug: str):
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
    response = requests.get(url, params={"details": "false"}, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"status={response.status_code}")
        return False
    jobs = response.json().get("jobs") or []
    if not jobs:
        print("no jobs")
        return False
    print(json.dumps(jobs[0], indent=2, default=str)[:2000])


def inspect_bamboohr(slug: str):
    url = f"https://{slug}.bamboohr.com/careers/list"
    response = requests.get(url, headers={"Accept": "application/json"}, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"status={response.status_code}")
        return False
    data = response.json()
    raw_list = data.get("result", data) if isinstance(data, dict) else data
    if not isinstance(raw_list, list) or not raw_list:
        print("no postings / unexpected shape:", str(data)[:500])
        return False
    print(json.dumps(raw_list[0], indent=2, default=str)[:2000])


def inspect_breezy(slug: str):
    url = f"https://{slug}.breezy.hr/json"
    response = requests.get(url, params={"verbose": "true"}, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"status={response.status_code}")
        return False
    jobs = response.json()
    if not isinstance(jobs, list) or not jobs:
        print("no postings")
        return False
    print(json.dumps(jobs[0], indent=2, default=str)[:2000])


def inspect_personio(slug: str):
    import xml.etree.ElementTree as ET

    if "." not in slug:
        print("skip, slug has no tld separator")
        return False
    subdomain, tld = slug.rsplit(".", 1)
    url = f"https://{subdomain}.jobs.personio.{tld}/xml"
    response = requests.get(url, params={"language": "en"}, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"status={response.status_code}")
        return False
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        print("parse error")
        return False
    positions = root.findall("position")
    if not positions:
        print("no positions")
        return False
    position = positions[0]
    print(ET.tostring(position, encoding="unicode")[:2000])


def inspect_recruitee(slug: str):
    url = f"https://{slug}.recruitee.com/api/offers/"
    response = requests.get(url, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"status={response.status_code}")
        return False
    offers = response.json().get("offers") or []
    if not offers:
        print("no offers")
        return False
    offer = offers[0]
    date_like_keys = {k: v for k, v in offer.items() if "date" in k.lower() or "_at" in k.lower() or "created" in k.lower() or "published" in k.lower()}
    print("date-like fields:", json.dumps(date_like_keys, indent=2, default=str))
    print("full slug/title:", offer.get("slug"), "|", offer.get("title"))


def inspect_teamtailor(slug: str):
    url = f"https://{slug}.teamtailor.com/api/v1/jobs"
    response = requests.get(url, headers={"Accept": "application/vnd.api+json"}, timeout=TIMEOUT)
    if response.status_code != 200:
        print(f"status={response.status_code} body={response.text[:300]}")
        return False
    jobs = response.json().get("data") or []
    if not jobs:
        print("no jobs, full response:", json.dumps(response.json(), indent=2, default=str)[:1000])
        return False
    job = jobs[0]
    attrs = job.get("attributes") or {}
    date_like_keys = {k: v for k, v in attrs.items() if "date" in k.lower() or "at" in k.lower()}
    print("date-like attributes:", json.dumps(date_like_keys, indent=2, default=str))
    print("title:", attrs.get("title"))


_INSPECTORS = {
    "greenhouse": inspect_greenhouse,
    "lever": inspect_lever,
    "ashby": inspect_ashby,
    "smartrecruiters": inspect_smartrecruiters,
    "workable": inspect_workable,
    "bamboohr": inspect_bamboohr,
    "breezy": inspect_breezy,
    "personio": inspect_personio,
    "recruitee": inspect_recruitee,
    "teamtailor": inspect_teamtailor,
}


def main():
    only_ats = set(sys.argv[1:]) if len(sys.argv) > 1 else None

    session = DiscoverySessionLocal()
    try:
        for ats_name, inspector in _INSPECTORS.items():
            if only_ats and ats_name not in only_ats:
                continue

            companies = (
                session.query(DiscoveredCompany)
                .filter(DiscoveredCompany.ats_name == ats_name)
                .order_by(DiscoveredCompany.id.asc())
                .limit(30)
                .all()
            )
            _print_section(ats_name)
            if not companies:
                print("no company found in DB for this ATS")
                continue

            for company in companies:
                print(f"--- trying slug={company.slug!r} ---")
                try:
                    result = inspector(company.slug)
                    if result is False:
                        continue
                    break
                except Exception as error:
                    print(f"ERROR: {error}")
    finally:
        session.close()


if __name__ == "__main__":
    main()