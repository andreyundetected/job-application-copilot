import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from core.db import crud
from core.db.models import Evaluation, JobPosting
from core.db.session import SessionLocal
from core.gap_analysis.block_generation import generate_block_fragments
from core.gap_analysis.extraction import extract_keywords
from core.gap_analysis.keywords import classify_requirements, keywords_for_block, keywords_for_letter
from core.gap_analysis.letter import generate_cover_letter
from core.gap_analysis.title_suggestions import suggest_title_changes, with_work_context
from core.parsing.html_blocks import (
    block_fragments,
    body_block_texts,
    build_title_targets,
    normalize_elements,
    replace_block_elements,
)
from core.parsing.html_to_text import html_to_text
from core.providers.openrouter_provider import OpenRouterProvider

OUT_DIR = config.OUTPUT_DIR / "tailoring_lab"
STATIC_PATH = OUT_DIR / "static.txt"
RUNS_PATH = OUT_DIR / "runs.txt"
ALL_STAGES = ("keywords", "titles", "blocks", "letter")
LINE = "=" * 100
THIN = "-" * 100


class RecordingProvider:
    def __init__(self, model):
        self.inner = OpenRouterProvider()
        if model:
            self.inner.model = model
        self.model = self.inner.model
        self.stage = ""
        self.calls = []
        self.marks = {}

    @property
    def last_usage(self):
        return self.inner.last_usage

    def mark(self, stage, lines):
        self.marks[stage] = lines

    def call(self, system_prompt, user_prompt, max_tokens=None, reasoning_effort=None, temperature=None):
        started = time.time()
        error = None
        response = ""
        try:
            response = self.inner.call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                reasoning_effort="off",
                temperature=temperature,
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.calls.append(
                {
                    "stage": self.stage,
                    "response": response,
                    "error": error,
                    "seconds": time.time() - started,
                    "usage": self.inner.last_usage,
                }
            )
        return response


def latest_evaluations(session):
    latest = {}
    for evaluation in session.query(Evaluation).order_by(Evaluation.created_at.asc(), Evaluation.id.asc()):
        latest[evaluation.job_posting_id] = evaluation
    return latest


def cmd_list(args):
    session = SessionLocal()
    try:
        latest = latest_evaluations(session)
        jobs = {job.id: job for job in session.query(JobPosting)}
        rows = []
        for job_id, evaluation in latest.items():
            score = evaluation.fit_score
            if score is None or not args.min_score <= score <= args.max_score:
                continue
            if evaluation.triggered_blockers and not args.with_blockers:
                continue
            job = jobs.get(job_id)
            if job is None:
                continue
            rows.append((score, job_id, job.company or "?", job.title or "?"))
    finally:
        session.close()

    rows.sort(key=lambda row: (-row[0], row[1]))
    for score, job_id, company, title in rows:
        print(f"{job_id:>5} | {score:>2} | {company[:28]:<28} | {title[:60]}")
    print(f"total: {len(rows)}")
    print("ids: " + ",".join(str(row[1]) for row in rows))


def load_context(job_id):
    session = SessionLocal()
    try:
        job = crud.get_job_posting(session, job_id)
        if job is None:
            raise SystemExit(f"job {job_id} not found")
        resume = crud.get_active_resume_version(session, "resume")
        if resume is None or not resume.content_html:
            raise SystemExit("no active resume with content_html")
        if not resume.blocks:
            raise SystemExit("resume has no blocks, detect them on the Profile page first")
        linkedin = crud.get_active_resume_version(session, "linkedin")
        profile = crud.get_candidate_profile(session)
        html, blocks = normalize_elements(resume.content_html, resume.blocks)
        return {
            "job_id": job.id,
            "company": job.company,
            "title": job.title,
            "job_text": job.raw_text,
            "resume_id": resume.id,
            "html": html,
            "blocks": blocks,
            "linkedin_text": linkedin.raw_text if linkedin else "",
            "extra_info": profile.extra_info if profile else None,
            "known_skills": [skill.text for skill in crud.list_known_skills(session)],
            "title_rejections": [
                {"original": row.original, "rejected": row.rejected, "comment": row.comment or ""}
                for row in crud.list_title_rejections(session)
            ],
        }
    finally:
        session.close()


def items_lines(items):
    lines = []
    for status in ("exact", "rephrase", "can_add", "unknown"):
        group = [item for item in items if item["status"] == status]
        lines.append(f"[{status}] {len(group)}")
        for item in group:
            extra = ""
            if status == "rephrase":
                extra = f" | {item.get('resume_form')} -> {item.get('suggested_form')}"
            if status == "can_add" and item.get("evidence"):
                extra = f" | evidence: {item['evidence']}"
            where = ",".join(item.get("assigned_field_paths") or []) or item.get("original_field_path") or "-"
            why = f" | why: {item['why']}" if item.get("why") else ""
            lines.append(f"  - {item['text']} [{item.get('tier') or '-'}]{extra}{why} | where: {where}")
    return lines


def stage_keywords(provider, ctx, args):
    html = ctx["html"]
    block_texts = body_block_texts(html, ctx["blocks"])

    provider.stage = "extract_requirements"
    requirements = extract_keywords(provider, ctx["job_text"])
    provider.mark(
        "extract_requirements",
        [f"[requirements] {len(requirements)}"]
        + [
            f"  - {r['text']} | {r['priority']} | {r['category']} | {r.get('tier') or '-'}"
            for r in requirements
        ],
    )

    provider.stage = "classify_keywords"
    items = classify_requirements(
        provider,
        requirements,
        block_texts,
        html_to_text(html),
        ctx["linkedin_text"],
        ctx["extra_info"],
        ctx["known_skills"],
    )
    if args.add_unknown_to_skills:
        skills = [block["field_path"] for block in ctx["blocks"] if block["kind"] == "skills"]
        if skills:
            for item in items:
                if item["status"] == "unknown" and item.get("category") != "title":
                    item["assigned_field_paths"] = [skills[0]]
    provider.mark("classify_keywords", items_lines(items))
    return items


def stage_titles(provider, ctx, job_title):
    provider.stage = "titles"
    targets = with_work_context(
        build_title_targets(ctx["html"], ctx["blocks"]),
        body_block_texts(ctx["html"], ctx["blocks"]),
    )
    titles = suggest_title_changes(
        provider, targets, ctx["job_text"], {}, job_title, ctx["title_rejections"]
    )
    lines = [f"[titles for role: {job_title}] {len(titles)}"]
    for title in titles:
        if title["changed"]:
            lines.append(f"  - {title['key']}: {title['current']} -> {title['suggested']} | {title['reason']}")
        else:
            lines.append(f"  - {title['key']}: unchanged | {title['reason']}")
    provider.mark("titles", lines)
    return titles


def basis_text(item):
    if item.get("evidence"):
        return f'{item["text"]} (basis: "{item["evidence"]}")'
    return item["text"]


def stage_blocks(provider, ctx, items, args):
    html = ctx["html"]
    blocks = list(ctx["blocks"])
    outcomes = []
    targets = [
        block["field_path"]
        for block in sorted(
            (b for b in blocks if b["kind"] in ("summary", "skills")),
            key=lambda b: b["kind"] != "skills",
        )
    ]
    if args.blocks:
        targets = [path for path in targets if any(part.lower() in path.lower() for part in args.blocks)]

    for path in targets:
        block = next((b for b in blocks if b["field_path"] == path), None)
        if block is None:
            continue

        originals = block_fragments(html, block)
        if not originals:
            outcomes.append({"path": path, "result": "skipped: empty block"})
            continue

        block_text = "\n".join(html_to_text(fragment) for fragment in originals)
        other_path = next(
            (b["field_path"] for b in blocks if b["kind"] == ("summary" if block["kind"] == "skills" else "skills")),
            None,
        )
        chosen = keywords_for_block(items, block["kind"], path, block_text, html_to_text(html), other_path)

        add_items = [basis_text(item) for item in chosen]
        if not add_items:
            outcomes.append({"path": path, "result": "skipped: nothing to add"})
            continue

        provider.stage = f"block:{path}"
        try:
            fragments = generate_block_fragments(
                provider,
                originals,
                block["label"],
                html_to_text(html),
                ctx["job_text"],
                add_items,
                [],
                "",
                kind=block["kind"],
            )
        except ValueError as error:
            outcomes.append({"path": path, "result": f"rejected: {error}", "add": add_items})
            continue
        except Exception as error:
            outcomes.append({"path": path, "result": f"error: {type(error).__name__}: {error}"})
            continue

        if fragments == originals:
            outcomes.append({"path": path, "result": "unchanged", "add": add_items})
            continue

        html, new_block = replace_block_elements(html, block, fragments)
        blocks = [new_block if b["id"] == new_block["id"] else b for b in blocks]
        outcomes.append({"path": path, "result": "applied", "add": add_items})

    return html, outcomes


def stage_letter(provider, ctx, items):
    provider.stage = "letter"
    skills_path = next((b["field_path"] for b in ctx["blocks"] if b["kind"] == "skills"), None)
    summary_path = next((b["field_path"] for b in ctx["blocks"] if b["kind"] == "summary"), None)
    chosen = keywords_for_letter(items, skills_path, summary_path)
    chosen_texts = {item["text"] for item in chosen}
    topics = [basis_text(item) for item in chosen]
    not_proven = [
        item["text"]
        for item in items
        if item["status"] == "unknown" and item.get("category") != "title" and item["text"] not in chosen_texts
    ]
    text = generate_cover_letter(
        provider,
        ctx["company"] or "",
        ctx["title"] or "",
        ctx["job_text"],
        html_to_text(ctx["html"]),
        ctx["linkedin_text"],
        ctx["extra_info"],
        topics,
        not_proven,
        "",
    )
    return {"text": text, "topics": topics}


def run_once(ctx, args, stages):
    provider = RecordingProvider(args.model)
    parsed = {"html": None, "outcomes": None, "error": None, "letter": None}
    try:
        items = stage_keywords(provider, ctx, args) if "keywords" in stages else None
        if "titles" in stages:
            job_title = next(
                (item["text"] for item in items or [] if item.get("category") == "title"),
                ctx["title"] or "",
            )
            stage_titles(provider, ctx, job_title)
        if "blocks" in stages:
            parsed["html"], parsed["outcomes"] = stage_blocks(provider, ctx, items, args)
        if "letter" in stages:
            parsed["letter"] = stage_letter(provider, ctx, items)
    except Exception as error:
        parsed["error"] = f"{type(error).__name__}: {error}"
    return provider, parsed


def static_lines(ctx):
    lines = [
        LINE,
        f"JOB {ctx['job_id']} | {ctx['company']} | {ctx['title']} | resume_id {ctx['resume_id']}",
        LINE,
        "",
        "[job posting]",
        ctx["job_text"],
        "",
        "[resume text]",
        html_to_text(ctx["html"]),
        "",
        "[resume blocks]",
    ]
    for block in ctx["blocks"]:
        text = "\n".join(html_to_text(fragment) for fragment in block_fragments(ctx["html"], block))
        lines += [
            f"- {block['field_path']} | kind {block['kind']} | company {block.get('company') or '-'} | role {block.get('role') or '-'}",
            text,
            "",
        ]
    lines += ["[linkedin]", ctx["linkedin_text"] or "-", "", "[extra info]", ctx["extra_info"] or "-", ""]
    lines += ["[known skills]", ", ".join(ctx["known_skills"]) or "-", ""]
    return lines


def run_lines(job_header, index, provider, parsed):
    lines = [LINE, f"{job_header} | RUN {index}", LINE, ""]
    last_call_of_stage = {}
    for position, call in enumerate(provider.calls):
        last_call_of_stage[call["stage"]] = position

    for position, call in enumerate(provider.calls):
        usage = call["usage"] or {}
        lines += [
            THIN,
            f"CALL {position + 1} | {call['stage']} | {call['seconds']:.1f}s | in {usage.get('input_tokens')} out {usage.get('output_tokens')} reasoning {usage.get('reasoning_tokens')}",
            THIN,
        ]
        if call["error"]:
            lines.append(f"ERROR: {call['error']}")
        lines += [call["response"], ""]
        if last_call_of_stage[call["stage"]] == position and call["stage"] in provider.marks:
            lines += ["PARSED:"] + provider.marks[call["stage"]] + [""]

    if parsed["outcomes"] is not None:
        lines += [THIN, "BLOCKS RESULT", THIN]
        for outcome in parsed["outcomes"]:
            lines.append(f"- {outcome['path']}: {outcome['result']}")
            for text in outcome.get("add") or []:
                lines.append(f"    add: {text}")
        lines += ["", "[final resume text]", html_to_text(parsed["html"]), ""]
    if parsed.get("letter"):
        lines += [THIN, "COVER LETTER", THIN, "topics: " + (", ".join(parsed["letter"]["topics"]) or "-"), "", parsed["letter"]["text"], ""]
    if parsed["error"]:
        lines += [f"PIPELINE ERROR: {parsed['error']}", ""]
    return lines


def build_files(args, stages, jobs):
    model = jobs[0][1][0][0].model
    static = [
        LINE,
        "STATIC INPUT (does not change between runs of the same job)",
        LINE,
        "",
    ]
    runs = [
        LINE,
        f"model: {model} | reasoning: off | temperature: 0",
        f"stages: {','.join(stages)} | runs per job: {args.runs} | tag: {args.tag or '-'}",
        LINE,
        "",
    ]
    for ctx, results in jobs:
        static += static_lines(ctx)
        header = f"JOB {ctx['job_id']} | {ctx['company']} | {ctx['title']}"
        for index, (provider, parsed) in enumerate(results, start=1):
            runs += run_lines(header, index, provider, parsed)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_PATH.write_text("\n".join(static), encoding="utf-8")
    RUNS_PATH.write_text("\n".join(runs), encoding="utf-8")


def cmd_run(args):
    stages = [part.strip() for part in args.stages.split(",") if part.strip()]
    unknown = [stage for stage in stages if stage not in ALL_STAGES]
    if unknown:
        raise SystemExit(f"unknown stages: {unknown}")
    if ("blocks" in stages or "letter" in stages) and "keywords" not in stages:
        raise SystemExit("stages blocks and letter need stage keywords in the same run")

    job_ids = [int(part) for part in ",".join(args.job).split(",") if part.strip()]
    contexts = {job_id: load_context(job_id) for job_id in job_ids}

    tasks = [job_id for job_id in job_ids for _ in range(args.runs)]
    workers = args.workers or min(len(tasks), 8)
    print(f"jobs: {job_ids} | runs: {args.runs} | stages: {stages} | workers: {workers}", flush=True)

    results = {job_id: [] for job_id in job_ids}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [(job_id, pool.submit(run_once, contexts[job_id], args, stages)) for job_id in tasks]
        for job_id, future in futures:
            pair = future.result()
            results[job_id].append(pair)
            print(f"job {job_id}: {len(pair[0].calls)} calls done", flush=True)

    build_files(args, stages, [(contexts[job_id], results[job_id]) for job_id in job_ids])
    print(f"written: {STATIC_PATH}\nwritten: {RUNS_PATH}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--min-score", type=int, default=9)
    list_parser.add_argument("--max-score", type=int, default=10)
    list_parser.add_argument("--with-blockers", action="store_true")

    run_parser = sub.add_parser("run")
    run_parser.add_argument("--job", action="append", required=True)
    run_parser.add_argument("--stages", default=",".join(ALL_STAGES))
    run_parser.add_argument("--runs", type=int, default=1)
    run_parser.add_argument("--workers", type=int, default=0)
    run_parser.add_argument("--model", default="")
    run_parser.add_argument("--tag", default="")
    run_parser.add_argument("--blocks", nargs="*", default=[])
    run_parser.add_argument("--add-unknown-to-skills", action="store_true")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    main()