import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from scripts.golden_common import open_readonly

GOLDEN_DIR = config.OUTPUT_DIR / "golden"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", required=True)
    parser.add_argument("--app", default=str(config.DATA_DIR / "app_2.db"))
    parser.add_argument("--labels", default=str(GOLDEN_DIR / "labels.json"))
    parser.add_argument("--name", default="review")
    args = parser.parse_args()

    ids = [part.strip() for part in args.ids.split(",") if part.strip()]
    labels_path = Path(args.labels)
    labels = json.loads(labels_path.read_text(encoding="utf-8")) if labels_path.exists() else {}

    connection = open_readonly(args.app)
    blocks = []
    missing = []
    for job_id in ids:
        row = connection.execute(
            "select company, title, raw_text from job_postings where id = ?", (int(job_id),)
        ).fetchone()
        if not row or not (row[2] or "").strip():
            missing.append(job_id)
            continue
        label = labels.get(job_id, {})
        header = (
            f"{'=' * 100}\n"
            f"JOB {job_id} | {row[0] or '?'} | {row[1] or '?'}\n"
            f"label: {label.get('score')} | blockers: {label.get('blockers')} | note: {label.get('note', '')}\n"
            f"{'=' * 100}"
        )
        blocks.append(f"{header}\n{row[2].strip()}\n")
    connection.close()

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    path = GOLDEN_DIR / f"{args.name}.txt"
    path.write_text("\n\n".join(blocks), encoding="utf-8")

    print(f"jobs: {len(blocks)} -> {path} ({path.stat().st_size // 1024} KB)")
    if missing:
        print(f"no text for: {missing}")


if __name__ == "__main__":
    main()