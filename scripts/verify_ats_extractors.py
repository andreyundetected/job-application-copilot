"""Standalone real-network verification for core/discovery/ats_extractor.py.

Not a pytest test - it hits real, live company career boards to confirm the
extractors actually parse something, not just that the mocks in
tests/discovery/test_ats_extractor*.py are internally consistent.

Usage:
    python scripts/verify_ats_extractors.py
    python scripts/verify_ats_extractors.py --platform recruitee personio
    python scripts/verify_ats_extractors.py --recruitee-slug bunq --personio-slug personio

Each platform is verified by first calling that platform's own list/board
endpoint directly (not going through our extractor) to find one currently-open
job and build its public URL, then feeding that URL through the real
core.discovery.ats_extractor.detect_platform / extract_job_text functions -
the same code path the automation pipeline uses. Company slugs are just
reasonably-likely-to-still-be-open guesses; a platform can look "alive" via
its own API but still print SKIP here if that particular company happens to
have zero postings right now - pass a different --<platform>-slug if so.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from core.discovery import ats_extractor

TIMEOUT = 20


def _report(platform: str, ok: bool, detail: str, text: str | None = None):
    status = "PASS" if ok else ("SKIP" if text is None and "no open jobs" in detail else "FAIL")
    print(f"[{status}] {platform}: {detail}")
    if text:
        snippet = text[:200].replace("\n", " ")
        print(f"       chars={len(text)}  snippet={snippet!r}")
    print()


def verify_greenhouse(slug: str):
    try:
        response = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", timeout=TIMEOUT)
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
        if not jobs:
            _report("greenhouse", False, f"board '{slug}' has no open jobs listed")
            return
        job_id = jobs[0]["id"]
        url = f"https://boards.greenhouse.io/{slug}/jobs/{job_id}"
    except Exception as error:
        _report("greenhouse", False, f"could not reach board '{slug}': {error}")
        return
    _run(url, "greenhouse")


def verify_lever(slug: str):
    try:
        response = requests.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"}, timeout=TIMEOUT)
        response.raise_for_status()
        postings = response.json()
        if not postings:
            _report("lever", False, f"board '{slug}' has no open jobs listed")
            return
        url = postings[0].get("hostedUrl") or f"https://jobs.lever.co/{slug}/{postings[0]['id']}"
    except Exception as error:
        _report("lever", False, f"could not reach board '{slug}': {error}")
        return
    _run(url, "lever")


def verify_ashby(slug: str):
    try:
        response = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{slug}", params={"includeCompensation": "false"}, timeout=TIMEOUT
        )
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
        if not jobs:
            _report("ashby", False, f"board '{slug}' has no open jobs listed")
            return
        url = jobs[0]["jobUrl"]
    except Exception as error:
        _report("ashby", False, f"could not reach board '{slug}': {error}")
        return
    _run(url, "ashby")


def verify_workable(slug: str):
    try:
        response = requests.get(
            f"https://apply.workable.com/api/v1/widget/accounts/{slug}", params={"details": "true"}, timeout=TIMEOUT
        )
        response.raise_for_status()
        jobs = response.json().get("jobs", [])
        if not jobs:
            _report("workable", False, f"board '{slug}' has no open jobs listed")
            return
        shortcode = jobs[0]["shortcode"]
        url = f"https://apply.workable.com/{slug}/j/{shortcode}"
    except Exception as error:
        _report("workable", False, f"could not reach board '{slug}': {error}")
        return
    _run(url, "workable")


def verify_smartrecruiters(slug: str):
    try:
        response = requests.get(
            f"https://api.smartrecruiters.com/v1/companies/{slug}/postings", params={"limit": 1}, timeout=TIMEOUT
        )
        response.raise_for_status()
        content = response.json().get("content", [])
        if not content:
            _report("smartrecruiters", False, f"company '{slug}' has no open jobs listed")
            return
        posting_id = content[0]["id"]
        url = f"https://careers.smartrecruiters.com/{slug}/{posting_id}"
    except Exception as error:
        _report("smartrecruiters", False, f"could not reach company '{slug}': {error}")
        return
    _run(url, "smartrecruiters")


def verify_recruitee(slug: str):
    try:
        response = requests.get(f"https://{slug}.recruitee.com/api/offers/", timeout=TIMEOUT)
        response.raise_for_status()
        offers = response.json().get("offers", [])
        if not offers:
            _report("recruitee", False, f"board '{slug}' has no open jobs listed")
            return
        offer_slug = offers[0]["slug"]
        url = f"https://{slug}.recruitee.com/o/{offer_slug}"
    except Exception as error:
        _report("recruitee", False, f"could not reach board '{slug}': {error}")
        return
    _run(url, "recruitee")


def verify_personio(slug: str):
    import xml.etree.ElementTree as ET

    for tld in ("de", "com"):
        try:
            response = requests.get(f"https://{slug}.jobs.personio.{tld}/xml", params={"language": "en"}, timeout=TIMEOUT)
            if response.status_code != 200:
                continue
            root = ET.fromstring(response.content)
            positions = root.findall("position")
            if not positions:
                response = requests.get(f"https://{slug}.jobs.personio.{tld}/xml", timeout=TIMEOUT)
                root = ET.fromstring(response.content)
                positions = root.findall("position")
            if not positions:
                continue
            job_id = positions[0].findtext("id").strip()
            url = f"https://{slug}.jobs.personio.{tld}/job/{job_id}"
            _run(url, "personio")
            return
        except Exception:
            continue
    _report("personio", False, f"could not find any open jobs for '{slug}' on .de or .com")


def verify_breezy(slug: str):
    try:
        response = requests.get(f"https://{slug}.breezy.hr/json", params={"verbose": "true"}, timeout=TIMEOUT)
        response.raise_for_status()
        jobs = response.json()
        if not jobs:
            _report("breezy", False, f"board '{slug}' has no open jobs listed")
            return
        url = jobs[0]["url"]
    except Exception as error:
        _report("breezy", False, f"could not reach board '{slug}': {error}")
        return
    _run(url, "breezy")


def _run(url: str, expected_platform: str):
    detected = ats_extractor.detect_platform(url)
    if detected != expected_platform:
        _report(expected_platform, False, f"detect_platform({url}) returned {detected!r}, expected {expected_platform!r}")
        return

    text = ats_extractor.extract_job_text(url)
    if text is None:
        _report(expected_platform, False, f"extract_job_text returned None for {url}")
        return
    if len(text) < 50:
        _report(expected_platform, False, f"extract_job_text returned suspiciously short text ({len(text)} chars) for {url}")
        return

    _report(expected_platform, True, f"url={url}", text=text)


_VERIFIERS = {
    "greenhouse": (verify_greenhouse, "stripe"),
    "lever": (verify_lever, "netflix"),
    "ashby": (verify_ashby, "ramp"),
    "workable": (verify_workable, "workable"),
    "smartrecruiters": (verify_smartrecruiters, "Bosch"),
    "recruitee": (verify_recruitee, "bunq"),
    "personio": (verify_personio, "personio"),
    "breezy": (verify_breezy, "new-incentives"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--platform",
        nargs="+",
        choices=list(_VERIFIERS.keys()),
        default=list(_VERIFIERS.keys()),
        help="Which platforms to verify (default: all)",
    )
    for platform in _VERIFIERS:
        parser.add_argument(f"--{platform}-slug", default=None, help=f"Override the company slug used for {platform}")
    args = parser.parse_args()

    print(f"Verifying {len(args.platform)} platform(s) against live boards...\n")

    for platform in args.platform:
        func, default_slug = _VERIFIERS[platform]
        slug = getattr(args, f"{platform}_slug".replace("-", "_")) or default_slug
        func(slug)


if __name__ == "__main__":
    main()