import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

GOLDEN_DIR = config.OUTPUT_DIR / "golden"
SEPARATOR = "=" * 100
RUN_SEPARATOR = "-" * 100
FAST = {"exact", "close"}
PRESETS = {
    "low": [63, 229, 366, 80, 181, 118, 135, 119],
    "mid": [18, 71, 162, 87, 426, 398, 332],
}
HEADER_RE = re.compile(r"id (\d+) \| label (\d+) \| blockers ([^|]*)\| runs \[([^\]]*)\] \| (.*)")
RUN_RE = re.compile(r"run (\d+) \| score (\S+) \| blockers ([^\n]*)")
ROW_RE = re.compile(r"^(.*?) \| asks: (.*?) \| candidate has: (.*) \| match: ([^|]*)$", re.S)


def norm(text):
    return " ".join((text or "").split())


def parse_blockers(text):
    return {int(part) for part in re.findall(r"\d+", text or "")}


def parse_score(text):
    return int(text) if text.strip().lstrip("-").isdigit() else None


def parse_report(text):
    cases = {}
    for chunk in re.split(rf"^{SEPARATOR}$", text, flags=re.M):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = re.split(rf"^{RUN_SEPARATOR}$", chunk, flags=re.M)
        header = HEADER_RE.search(parts[0])
        if header is None:
            continue
        runs = []
        for part in parts[1:]:
            part = part.strip()
            match = RUN_RE.match(part)
            if match is None:
                continue
            runs.append(
                {
                    "run": int(match.group(1)),
                    "score": parse_score(match.group(2)),
                    "got": parse_blockers(match.group(3)),
                    "raw": part[match.end():].strip(),
                }
            )
        cases[int(header.group(1))] = {
            "id": int(header.group(1)),
            "label": int(header.group(2)),
            "want": parse_blockers(header.group(3)),
            "title": header.group(5).strip(),
            "runs": runs,
        }
    return cases


def grab(raw, tag):
    match = re.search(rf"<{tag}>(.*?)(?=</?[a-z_]+>)", raw, re.S)
    return norm(match.group(1)) if match else ""


def parse_rows(raw):
    rows = []
    for body in re.findall(r"<req>(.*?)</req>", raw, re.S):
        match = ROW_RE.match(norm(body))
        if match is None:
            rows.append({"requirement": norm(body)[:160], "has": "", "optional": False, "value": "?"})
            continue
        value = match.group(4).strip()
        optional = value.startswith("optional:")
        rows.append(
            {
                "requirement": match.group(1).strip(),
                "has": match.group(3).strip(),
                "optional": optional,
                "value": value.replace("optional:", "").strip(),
            }
        )
    return rows


def short(text, limit):
    return text if len(text) <= limit else text[: limit - 3] + "..."


def render_rows(rows, mode):
    if mode == "none":
        return []
    fast = sum(1 for row in rows if not row["optional"] and row["value"] in FAST)
    optional = sum(1 for row in rows if row["optional"])
    lines = [f"rows: {len(rows)} total | {fast} exact/close | {optional} optional"]
    for row in rows:
        if mode == "slow" and (row["optional"] or row["value"] in FAST):
            continue
        marker = "opt " if row["optional"] else ""
        lines.append(f"  [{marker}{row['value']}] {short(row['requirement'], 110)} || {short(row['has'], 240)}")
    return lines


def render_run(case, run, rows_mode, blocker_mode):
    raw = run["raw"]
    lines = [
        f"--- run {run['run']} | score {run['score']} | bucket {grab(raw, 'bucket')} | "
        f"blockers got {sorted(run['got']) or '-'} want {sorted(case['want']) or '-'}",
        f"hiring: {grab(raw, 'hiring')}",
        f"center: {grab(raw, 'center')}",
    ]
    lines += render_rows(parse_rows(raw), rows_mode)
    lines.append(f"prep: {grab(raw, 'prep_thinking')}")
    if blocker_mode:
        lines.append(f"blockers_thinking: {grab(raw, 'blockers_thinking')}")
        for check in re.findall(r"<check>(.*?)</check>", raw, re.S):
            check = norm(check)
            if "result: triggered" in check:
                lines.append(f"  {check}")
    cons = [norm(item) for item in re.findall(r"<con>(.*?)</con>", raw, re.S)]
    if cons:
        lines.append("cons: " + " / ".join(cons))
    return lines


def pick_runs(case, extremes, blocker_diff):
    runs = case["runs"]
    if blocker_diff:
        return [run for run in runs if run["got"] != case["want"]]
    if extremes:
        scored = [run for run in runs if run["score"] is not None]
        if not scored:
            return runs
        low = min(scored, key=lambda run: run["score"])
        high = max(scored, key=lambda run: run["score"])
        return [low] if low is high else [low, high]
    return runs


def spread(case):
    scores = [run["score"] for run in case["runs"] if run["score"] is not None]
    return max(scores) - min(scores) if scores else 0


def latest_report():
    files = sorted(GOLDEN_DIR.glob("run_*.txt"))
    if not files:
        raise SystemExit("no run_*.txt in output/golden")
    return files[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="")
    parser.add_argument("--ids", default="")
    parser.add_argument("--preset", choices=sorted(PRESETS), action="append", default=[])
    parser.add_argument("--auto-unstable", action="store_true")
    parser.add_argument("--blocker-diff", action="store_true")
    parser.add_argument("--min-spread", type=int, default=3)
    parser.add_argument("--extremes", action="store_true")
    parser.add_argument("--rows", choices=["slow", "all", "none"], default="slow")
    parser.add_argument("--name", default="extract")
    args = parser.parse_args()

    report_path = Path(args.report) if args.report else latest_report()
    cases = parse_report(report_path.read_text(encoding="utf-8"))

    selected = {int(part) for part in args.ids.split(",") if part.strip().isdigit()}
    for preset in args.preset:
        selected.update(PRESETS[preset])
    if args.auto_unstable:
        selected.update(case_id for case_id, case in cases.items() if spread(case) >= args.min_spread)
    if args.blocker_diff:
        selected.update(
            case_id for case_id, case in cases.items() if any(run["got"] != case["want"] for run in case["runs"])
        )
    if not selected:
        raise SystemExit("nothing selected: use --ids, --preset, --auto-unstable or --blocker-diff")

    blocks = []
    missing = []
    for case_id in sorted(selected):
        case = cases.get(case_id)
        if case is None:
            missing.append(case_id)
            continue
        runs = pick_runs(case, args.extremes, args.blocker_diff)
        if not runs:
            continue
        header = [
            "=" * 100,
            f"id {case['id']} | label {case['label']} | scores {[run['score'] for run in case['runs']]} | {case['title']}",
            "=" * 100,
        ]
        body = []
        for run in runs:
            body += render_run(case, run, args.rows, args.blocker_diff)
            body.append("")
        blocks.append("\n".join(header + body))

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = GOLDEN_DIR / f"{args.name}.txt"
    out_path.write_text("\n\n".join(blocks), encoding="utf-8")
    print(f"report: {report_path.name} | cases: {len(blocks)} -> {out_path} ({out_path.stat().st_size // 1024} KB)")
    if missing:
        print(f"not in report (correct cases are not saved there): {missing}")


if __name__ == "__main__":
    main()