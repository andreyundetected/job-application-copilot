import argparse
import datetime
import json
import random
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.evaluator.pipeline import evaluate_job_posting
from core.providers.factory import get_llm_provider
from scripts.golden_common import describe_raw, open_readonly

GOLDEN_DIR = config.OUTPUT_DIR / "golden"


def percent(part, whole):
    return f"{part / whole * 100:.1f}%" if whole else "n/a"


def fmt_blockers(values):
    return ",".join(str(number) for number in sorted(values)) or "-"


def load_context(connection):
    def one(sql):
        row = connection.execute(sql).fetchone()
        return row[0] if row and row[0] else ""

    context = {
        "resume_text": one(
            "select raw_text from resume_versions where source_type = 'resume' and is_active = 1 order by id desc limit 1"
        ),
        "linkedin_text": one(
            "select raw_text from resume_versions where source_type = 'linkedin' and is_active = 1 order by id desc limit 1"
        ),
        "extra_info": one("select extra_info from candidate_profile limit 1") or None,
        "blockers": [row[0] for row in connection.execute('select text from blocker_rules order by "order" asc')],
        "scoring_factors": [
            {"id": row[0], "text": row[1], "direction": row[2], "weight": row[3]}
            for row in connection.execute('select id, text, direction, weight from scoring_factors order by "order" asc')
        ],
    }
    if not context["resume_text"]:
        raise SystemExit("no active resume in this database")
    return context


def format_usage(usage):
    if not usage:
        return "usage n/a"
    return (
        f"in {usage.get('input_tokens')} out {usage.get('output_tokens')} "
        f"reasoning {usage.get('reasoning_tokens')} fallback {usage.get('fallback')}"
    )


def run_one(job_id, run, text, context, reasoning):
    started = time.time()
    provider = get_llm_provider()
    try:
        result = evaluate_job_posting(
            provider,
            job_posting_text=text,
            resume_text=context["resume_text"],
            linkedin_text=context["linkedin_text"],
            blockers=context["blockers"],
            scoring_factors=context["scoring_factors"],
            extra_info=context["extra_info"],
            reasoning_effort=reasoning,
        )
    except Exception as error:
        return {
            "id": job_id,
            "run": run,
            "score": None,
            "raw": repr(error),
            "info": describe_raw(""),
            "seconds": time.time() - started,
            "usage": provider.last_usage,
        }
    return {
        "id": job_id,
        "run": run,
        "score": result["score"],
        "raw": result["raw_response"],
        "info": describe_raw(result["raw_response"]),
        "seconds": time.time() - started,
        "usage": provider.last_usage,
    }


def select_cases(args):
    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    cases = {job_id: item for job_id, item in labels.items() if item.get("score") is not None}

    if args.ids:
        wanted = {part.strip() for part in args.ids.split(",") if part.strip()}
        cases = {job_id: item for job_id, item in cases.items() if job_id in wanted}
    if args.scores:
        allowed = {int(part) for part in args.scores.split(",") if part.strip()}
        cases = {job_id: item for job_id, item in cases.items() if item["score"] in allowed}
    if args.only_blocked:
        cases = {job_id: item for job_id, item in cases.items() if item.get("blockers")}

    rng = random.Random(args.seed)
    if args.per_score > 0:
        grouped = defaultdict(list)
        for job_id in sorted(cases, key=int):
            grouped[cases[job_id]["score"]].append(job_id)
        picked = []
        for ids in grouped.values():
            rng.shuffle(ids)
            picked += ids[: args.per_score]
        cases = {job_id: cases[job_id] for job_id in picked}
    if args.limit > 0 and len(cases) > args.limit:
        cases = {job_id: cases[job_id] for job_id in rng.sample(sorted(cases), args.limit)}
    return cases


def load_jobs(connection, cases, app_path):
    jobs = {}
    for job_id in list(cases):
        row = connection.execute(
            "select company, title, raw_text from job_postings where id = ?", (int(job_id),)
        ).fetchone()
        if row and (row[2] or "").strip():
            jobs[job_id] = {"company": row[0] or "?", "title": row[1] or "?", "text": row[2]}
        else:
            print(f"id {job_id}: no text in {app_path}, skipped")
            del cases[job_id]
    return jobs


def execute(tasks, jobs, cases, context, workers, reasoning):
    results = []
    started_all = time.time()
    executor = ThreadPoolExecutor(max_workers=workers)
    futures = {
        executor.submit(run_one, job_id, run, jobs[job_id]["text"], context, reasoning): (job_id, run)
        for job_id, run in tasks
    }
    try:
        for done, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            label = cases[result["id"]]["score"]
            want = set(cases[result["id"]].get("blockers") or [])
            got = set(result["info"]["blockers"])
            mark = "!" if result["score"] != label or got != want else " "
            print(
                f"[{done}/{len(tasks)}] {mark} id {result['id']:>4} run {result['run']} | "
                f"label {label:>2} | model {result['score']} | b {fmt_blockers(got)} vs {fmt_blockers(want)} | "
                f"{result['seconds']:.0f}s | {format_usage(result['usage'])}",
                flush=True,
            )
            if done % 10 == 0:
                elapsed = time.time() - started_all
                left = elapsed / done * (len(tasks) - done)
                print(f"    elapsed {elapsed:.0f}s, about {left:.0f}s left", flush=True)
    except KeyboardInterrupt:
        print("interrupted, summarizing finished calls", flush=True)
        for future in futures:
            future.cancel()
    executor.shutdown(wait=False, cancel_futures=True)

    usage_total = {}
    for result in results:
        usage = result.get("usage")
        if isinstance(usage, dict):
            for key, value in usage.items():
                if isinstance(value, (int, float)):
                    usage_total[key] = usage_total.get(key, 0) + value
    print(f"finished calls: {len(results)}/{len(tasks)} in {time.time() - started_all:.0f}s")
    print(f"usage: {usage_total if usage_total else 'no usage data'}")
    if results and usage_total.get("output_tokens"):
        print(f"avg output tokens per call: {usage_total['output_tokens'] / len(results):.0f}")
    total_cost = usage_total.get("cost")
    if total_cost and results:
        per_call = total_cost / len(results)
        print(f"cost: ${total_cost:.4f} total | ${per_call:.5f} per call | {1 / per_call:.0f} calls per $1")
    else:
        print("cost: not reported by provider")
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", default=str(config.DATA_DIR / "app_2.db"))
    parser.add_argument("--labels", default=str(GOLDEN_DIR / "labels.json"))
    parser.add_argument("--scores", default="")
    parser.add_argument("--per-score", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--ids", default="")
    parser.add_argument("--only-blocked", action="store_true")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--raw-all", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--reasoning", choices=["off", "low", "medium", "high"], default="off")
    args = parser.parse_args()

    cases = select_cases(args)

    connection = open_readonly(args.app)
    context = load_context(connection)
    jobs = load_jobs(connection, cases, args.app)
    connection.close()

    if not cases:
        print("no cases for this selection")
        return

    tasks = [(job_id, run) for job_id in cases for run in range(1, args.runs + 1)]
    print(f"cases: {len(cases)} | runs: {args.runs} | calls: {len(tasks)} | workers: {args.workers} | provider: {config.LLM_PROVIDER}")
    if args.dry_run:
        return

    results = execute(tasks, jobs, cases, context, args.workers, args.reasoning)

    done_ids = {result["id"] for result in results}
    cases = {job_id: item for job_id, item in cases.items() if job_id in done_ids}

    by_case = defaultdict(list)
    for result in results:
        by_case[result["id"]].append(result)

    totals = {
        "pairs": 0,
        "exact": 0,
        "within_one": 0,
        "failed": 0,
        "blocker_exact": 0,
        "blocker_false": 0,
        "blocker_missed": 0,
        "score_diff": 0,
    }
    per_label = defaultdict(lambda: [0, 0])
    report = []

    print("=" * 100)
    for job_id in sorted(cases, key=lambda key: (cases[key]["score"], int(key))):
        label = cases[job_id]["score"]
        want = set(cases[job_id].get("blockers") or [])
        runs = by_case[job_id]
        scores = [run["score"] for run in runs]
        wrong = False

        for run in runs:
            score = run["score"]
            got = set(run["info"]["blockers"])
            totals["pairs"] += 1
            per_label[label][1] += 1

            if score is None:
                totals["failed"] += 1
                wrong = True
                continue

            if got == want:
                totals["blocker_exact"] += 1
            else:
                wrong = True
            totals["blocker_false"] += len(got - want)
            totals["blocker_missed"] += len(want - got)

            if score == label:
                totals["exact"] += 1
                per_label[label][0] += 1
            else:
                wrong = True
            if abs(score - label) <= 1:
                totals["within_one"] += 1
            totals["score_diff"] += score - label

        info = runs[0]["info"]
        job = jobs[job_id]
        mark = "!" if wrong else " "
        print(
            f"{mark} id {job_id:>4} | label {label:>2} | runs {scores} | {info['bucket']} | "
            f"b: got {fmt_blockers(info['blockers'])} want {fmt_blockers(want)} | "
            f"{job['company'][:18]} - {job['title'][:36]} | {cases[job_id].get('note', '')[:50]}"
        )
        if wrong or args.raw_all:
            report += [
                "=" * 100,
                f"id {job_id} | label {label} | blockers {fmt_blockers(want)} | runs {scores} | {job['company']} - {job['title']} | {cases[job_id].get('note', '')}",
            ]
            for run in sorted(runs, key=lambda item: item["run"]):
                report += [
                    "-" * 100,
                    f"run {run['run']} | score {run['score']} | blockers {fmt_blockers(run['info']['blockers'])}",
                    run["raw"],
                    "",
                ]

    print("=" * 100)
    print("by label (exact / total):")
    for label in sorted(per_label):
        exact, total = per_label[label]
        print(f"  {label:>2}: {exact}/{total} ({percent(exact, total)})")

    pairs = totals["pairs"]
    scored = pairs - totals["failed"]
    print("-" * 100)
    print(f"score exact: {totals['exact']}/{pairs} ({percent(totals['exact'], pairs)})")
    print(f"score within +-1: {totals['within_one']}/{pairs} ({percent(totals['within_one'], pairs)})")
    print(f"score bias (model - label, avg): {totals['score_diff'] / scored:.2f}" if scored else "score bias: n/a")
    print(f"blockers exact set: {totals['blocker_exact']}/{scored} ({percent(totals['blocker_exact'], scored)})")
    print(f"blockers falsely triggered: {totals['blocker_false']}")
    print(f"blockers missed: {totals['blocker_missed']}")
    print(f"failed / no score: {totals['failed']}")

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = GOLDEN_DIR / f"run_{stamp}.txt"
    report_path.write_text("\n".join(report), encoding="utf-8")
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()