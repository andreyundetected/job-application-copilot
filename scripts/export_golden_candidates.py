import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from scripts.golden_common import (
    ONSITE_RE,
    describe,
    latest_evaluations,
    load_checked,
    open_readonly,
    pick_diverse,
)

OUT_DIR = config.OUTPUT_DIR / "golden"


def cut(text, max_chars, tail=1000):
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - tail]}\n\n[... cut ...]\n\n{text[-tail:]}"


def parse_scores(value):
    if not value.strip():
        return set(range(0, 11))
    return {int(part) for part in value.split(",") if part.strip()}


def load_labeled(path):
    if not Path(path).exists():
        return set()
    return {str(key) for key in json.loads(Path(path).read_text(encoding="utf-8"))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", default=str(config.DATA_DIR / "app_2.db"))
    parser.add_argument("--scores", default="")
    parser.add_argument("--per-score", type=int, default=3)
    parser.add_argument("--per-blocker", type=int, default=4)
    parser.add_argument("--max-chars", type=int, default=12000)
    parser.add_argument("--labels", default=str(OUT_DIR / "labels.json"))
    parser.add_argument("--include-labeled", action="store_true")
    parser.add_argument("--name", default="to_label")
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    wanted = parse_scores(args.scores)
    labeled = set() if args.include_labeled else load_labeled(args.labels)

    connection = open_readonly(args.app)
    latest = latest_evaluations(connection)
    jobs = {row[0]: row for row in connection.execute("select id, company, title, raw_text from job_postings")}
    connection.close()

    candidates = []
    for job_id, (score, checked) in latest.items():
        if score is None or job_id not in jobs or str(job_id) in labeled:
            continue
        text = (jobs[job_id][3] or "").strip()
        if len(text) < 300:
            continue
        candidates.append(
            {
                "id": job_id,
                "score": score,
                "company": jobs[job_id][1] or "?",
                "title": jobs[job_id][2] or "?",
                "text": text,
                "onsite_hit": bool(ONSITE_RE.search(text)),
                **describe(load_checked(checked)),
            }
        )

    rng = random.Random(args.seed)
    rng.shuffle(candidates)

    chosen = []

    for score in sorted(wanted):
        pool = [item for item in candidates if item["score"] == score]
        picked = pick_diverse(pool, args.per_score, lambda e: (e["bucket"], bool(e["blockers"]), e["onsite_hit"]))
        chosen += [(f"score {score}", item) for item in picked]
        print(f"score {score}: pool {len(pool)}, picked {sorted(item['id'] for item in picked)}")

    if args.per_blocker > 0:
        for number in range(1, 7):
            pool = [item for item in candidates if number in item["blockers"]]
            picked = pick_diverse(pool, args.per_blocker, lambda e: (tuple(e["blockers"]), e["score"], e["onsite_hit"]))
            chosen += [(f"blocker b{number}", item) for item in picked]
            print(f"blocker {number}: pool {len(pool)}, picked {sorted(item['id'] for item in picked)}")

    unique = {}
    for group, item in chosen:
        unique.setdefault(item["id"], (group, item))

    ordered = list(unique.values())
    rng.shuffle(ordered)

    if not ordered:
        print("nothing selected")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    blocks = [
        f"=== JOB {item['id']} | {item['company']} | {item['title']} ===\n{cut(item['text'], args.max_chars)}\n"
        for _, item in ordered
    ]
    text_path = OUT_DIR / f"{args.name}.txt"
    text_path.write_text("\n\n".join(blocks), encoding="utf-8")

    meta = {
        str(item["id"]): {
            "group": group,
            "score": item["score"],
            "bucket": item["bucket"],
            "blockers": item["blockers"],
        }
        for group, item in ordered
    }
    (OUT_DIR / f"{args.name}_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"jobs: {len(ordered)} -> {text_path} ({text_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()