import argparse
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR.parent))
sys.path.insert(0, str(SCRIPTS_DIR))

import config
from core.db import crud
from core.db.session import SessionLocal
from core.gap_analysis.keywords import keywords_for_letter
from core.gap_analysis.letter import generate_cover_letter
from core.parsing.html_to_text import html_to_text
from tailoring_lab import RecordingProvider, basis_text, cmd_list, items_lines, load_context, stage_keywords

OUT_DIR = config.OUTPUT_DIR / "letter_lab"
STATIC_PATH = OUT_DIR / "static.txt"
RUNS_PATH = OUT_DIR / "runs.txt"
LINE = "=" * 100
THIN = "-" * 100


class LabProvider(RecordingProvider):
    def __init__(self, model):
        super().__init__(model)
        self.prompts = []

    def call(self, system_prompt, user_prompt, max_tokens=None, temperature=None, **kwargs):
        if self.stage == "letter":
            self.prompts.append(user_prompt)
        return super().call(system_prompt, user_prompt, max_tokens=max_tokens, temperature=temperature)


def load_profile():
    session = SessionLocal()
    try:
        profile = crud.get_candidate_profile(session)
        if profile is None:
            return {"name": "", "contacts": [], "writing_preferences": "", "standing_note": ""}
        return {
            "name": profile.full_name or "",
            "contacts": [value for value in (profile.email, profile.github_url, profile.linkedin_url) if value],
            "writing_preferences": profile.writing_preferences or "",
            "standing_note": profile.letter_note or "",
        }
    finally:
        session.close()


def resolve_notes(args, profile):
    if args.no_notes:
        return ""
    if args.notes_file:
        return Path(args.notes_file).read_text(encoding="utf-8").strip()
    if args.notes:
        return args.notes.strip()
    return profile["standing_note"].strip()


def build_evidence(items, ctx):
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
    return topics, not_proven


def compute_keywords(ctx, model):
    provider = LabProvider(model)
    return stage_keywords(provider, ctx, SimpleNamespace(add_unknown_to_skills=False))


def run_once(ctx, profile, settings, evidence, args):
    provider = LabProvider(args.model)
    topics, not_proven = evidence if evidence else ([], [])
    text = None
    error = None
    try:
        if args.fresh_keywords:
            items = stage_keywords(provider, ctx, SimpleNamespace(add_unknown_to_skills=False))
            topics, not_proven = build_evidence(items, ctx)
        claims = [part.strip() for part in args.claim.split(",") if part.strip()]
        claim_keys = {claim.lower() for claim in claims}
        topics = list(topics) + [claim for claim in claims if claim not in topics]
        not_proven = [item for item in not_proven if item.lower() not in claim_keys]
        provider.stage = "letter"
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
            settings["notes"],
            contacts=profile["contacts"],
            candidate_name=profile["name"],
            writing_preferences=settings["writing_preferences"],
            temperature=args.temperature,
            comment=args.comment.strip(),
            previous_letter=Path(args.previous_file).read_text(encoding="utf-8").strip() if args.previous_file else "",
        )
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return {"provider": provider, "text": text, "error": error, "topics": topics, "not_proven": not_proven}


def static_lines(ctx, profile, settings, keyword_lines, evidence, first_prompt):
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
        "[linkedin]",
        ctx["linkedin_text"] or "-",
        "",
        "[extra info]",
        ctx["extra_info"] or "-",
        "",
        "[candidate]",
        f"name: {profile['name'] or '-'}",
        "contacts: " + (", ".join(profile["contacts"]) or "-"),
        "",
        "[writing preferences]",
        settings["writing_preferences"] or "-",
        "",
        "[notes for the letter]",
        settings["notes"] or "-",
        "",
    ]
    if keyword_lines is None:
        lines += ["[keywords]", "recomputed in every run, topics are listed in the runs file", ""]
    else:
        topics, not_proven = evidence
        lines += ["[keyword classification, shared by all runs]"] + keyword_lines + [""]
        lines += ["[topics given to the letter]"] + ([f"- {topic}" for topic in topics] or ["-"]) + [""]
        lines += ["[not proven]"] + ([f"- {item}" for item in not_proven] or ["-"]) + [""]
    lines += [THIN, "PROMPT (run 1)", THIN, first_prompt or "-", ""]
    return lines


def run_lines(header, index, run, fresh_keywords):
    provider = run["provider"]
    lines = [LINE, f"{header} | RUN {index}", LINE, ""]
    if run["error"]:
        lines += [f"ERROR: {run['error']}", ""]
    if run["text"] is None:
        return lines
    if fresh_keywords:
        lines += ["topics: " + ("; ".join(run["topics"]) or "-"), "not proven: " + ("; ".join(run["not_proven"]) or "-"), ""]
    letter_calls = [call for call in provider.calls if call["stage"] == "letter"]
    call = letter_calls[-1] if letter_calls else None
    if call:
        usage = call["usage"] or {}
        lines.append(
            f"words: {len(run['text'].split())} | {call['seconds']:.1f}s | in {usage.get('input_tokens')} out {usage.get('output_tokens')}"
        )
        lines += ["", THIN, "MODEL ANSWER (plan and letter)", THIN, call["response"] or "", ""]
    lines += [THIN, "FINAL LETTER", THIN, run["text"], ""]
    return lines


def build_files(args, settings, jobs):
    first = jobs[0]["runs"][0]["provider"]
    temperature = config.LETTER_TEMPERATURE if args.temperature is None else args.temperature
    static = [LINE, "STATIC INPUT (does not change between runs of the same job)", LINE, ""]
    runs = [
        LINE,
        f"model: {first.model} | letter temperature: {temperature} | reasoning: off",
        f"runs per job: {args.runs} | fresh keywords: {'yes' if args.fresh_keywords else 'no'} | tag: {args.tag or '-'}",
        LINE,
        "",
    ]
    for job in jobs:
        ctx = job["ctx"]
        header = f"JOB {ctx['job_id']} | {ctx['company']} | {ctx['title']}"
        first_run = job["runs"][0]
        first_prompt = first_run["provider"].prompts[0] if first_run["provider"].prompts else ""
        static += static_lines(ctx, job["profile"], settings, job["keyword_lines"], job["evidence"], first_prompt)
        for index, run in enumerate(job["runs"], start=1):
            runs += run_lines(header, index, run, args.fresh_keywords)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATIC_PATH.write_text("\n".join(static), encoding="utf-8")
    RUNS_PATH.write_text("\n".join(runs), encoding="utf-8")


def cmd_run(args):
    job_ids = [int(part) for part in ",".join(args.job).split(",") if part.strip()]
    profile = load_profile()
    settings = {
        "notes": resolve_notes(args, profile),
        "writing_preferences": "" if args.no_writing_prefs else profile["writing_preferences"],
    }
    contexts = {job_id: load_context(job_id) for job_id in job_ids}

    evidence = {job_id: None for job_id in job_ids}
    keyword_lines = {job_id: None for job_id in job_ids}
    if not args.fresh_keywords:
        print(f"keywords for jobs {job_ids} ...", flush=True)
        with ThreadPoolExecutor(max_workers=min(len(job_ids), 8)) as pool:
            computed = list(pool.map(lambda job_id: compute_keywords(contexts[job_id], args.model), job_ids))
        for job_id, items in zip(job_ids, computed):
            evidence[job_id] = build_evidence(items, contexts[job_id])
            keyword_lines[job_id] = items_lines(items)

    tasks = [job_id for job_id in job_ids for _ in range(args.runs)]
    workers = args.workers or min(len(tasks), 8)
    print(f"jobs: {job_ids} | runs: {args.runs} | workers: {workers}", flush=True)

    results = {job_id: [] for job_id in job_ids}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            (job_id, pool.submit(run_once, contexts[job_id], profile, settings, evidence[job_id], args))
            for job_id in tasks
        ]
        for job_id, future in futures:
            run = future.result()
            results[job_id].append(run)
            print(f"job {job_id}: {run['error'] or 'ok'}", flush=True)

    jobs = [
        {
            "ctx": contexts[job_id],
            "profile": profile,
            "keyword_lines": keyword_lines[job_id],
            "evidence": evidence[job_id],
            "runs": results[job_id],
        }
        for job_id in job_ids
    ]
    build_files(args, settings, jobs)
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
    run_parser.add_argument("--runs", type=int, default=1)
    run_parser.add_argument("--workers", type=int, default=0)
    run_parser.add_argument("--model", default="")
    run_parser.add_argument("--tag", default="")
    run_parser.add_argument("--temperature", type=float, default=None)
    run_parser.add_argument("--fresh-keywords", action="store_true")
    run_parser.add_argument("--notes", default="")
    run_parser.add_argument("--notes-file", default="")
    run_parser.add_argument("--no-notes", action="store_true")
    run_parser.add_argument("--no-writing-prefs", action="store_true")
    run_parser.add_argument("--claim", default="")
    run_parser.add_argument("--comment", default="")
    run_parser.add_argument("--previous-file", default="")

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    else:
        cmd_run(args)


if __name__ == "__main__":
    main()