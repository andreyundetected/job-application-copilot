import json
import re
import sqlite3
from pathlib import Path

from core.evaluator.checks import parse_blocker_checks, parse_bucket

ONSITE_RE = re.compile(r"hybrid|on-?site|in[- ]office|in the office|relocat", re.IGNORECASE)


def open_readonly(path):
    return sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)


def load_checked(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return None
    return value


def describe_raw(raw):
    raw = raw or ""
    return {
        "bucket": parse_bucket(raw),
        "blockers": [item["number"] for item in parse_blocker_checks(raw)],
    }


def describe(checked):
    return describe_raw((checked or {}).get("raw_response"))


def latest_evaluations(connection):
    latest = {}
    for job_id, score, checked in connection.execute(
        "select job_posting_id, fit_score, checked_keywords from evaluations order by created_at asc, id asc"
    ):
        latest[job_id] = (score, checked)
    return latest


def pick_diverse(candidates, limit, key):
    groups = {}
    for candidate in candidates:
        groups.setdefault(key(candidate), []).append(candidate)
    queues = [items for _, items in sorted(groups.items(), key=lambda pair: -len(pair[1]))]

    picked = []
    used_companies = set()
    for unique_only in (True, False):
        progressed = True
        while progressed and len(picked) < limit:
            progressed = False
            for queue in queues:
                if len(picked) >= limit:
                    break
                index = next(
                    (i for i, item in enumerate(queue) if not unique_only or item["company"] not in used_companies),
                    None,
                )
                if index is None:
                    continue
                item = queue.pop(index)
                picked.append(item)
                used_companies.add(item["company"])
                progressed = True
    return picked