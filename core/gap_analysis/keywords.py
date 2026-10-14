import html
import logging
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_TOKEN_RE = re.compile(r"[^\w+#.]+", re.UNICODE)
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
_K_RE = re.compile(r"<k\s+(.*?)/>")

BATCH_SIZE = 15
SKILL_CATEGORIES = {"skill", "tool", "cert"}
LETTER = "letter"


def normalize_text(text: str | None) -> str:
    tokens = [token.strip(".") for token in _TOKEN_RE.sub(" ", (text or "").lower()).split()]
    return " ".join(token for token in tokens if token)


def contains_phrase(haystack_norm: str, phrase: str | None) -> bool:
    needle = normalize_text(phrase)
    return bool(needle) and f" {needle} " in f" {haystack_norm} "


def _locate(prepared: list[dict], phrase: str) -> list[str]:
    return [block["field_path"] for block in prepared if contains_phrase(block["norm"], phrase)]


def _base_item(requirement: dict) -> dict:
    return {
        "text": requirement["text"],
        "category": requirement.get("category"),
        "priority": requirement.get("priority"),
        "tier": requirement.get("tier"),
        "source": None,
        "original_field_path": None,
        "suggested_field_paths": [],
        "suggested_reason": None,
        "recommend_keep": None,
        "assigned_field_paths": [],
        "resume_form": None,
        "suggested_form": None,
        "evidence": None,
        "why": None,
    }


def _render(batch, block_texts, linkedin_text, extra_info, known_skills) -> str:
    return _env.get_template("classify_keywords_prompt.jinja").render(
        items=batch,
        blocks=[
            {"field_path": b["field_path"], "kind": b["kind"], "label": b["label"], "text": b["text"]}
            for b in block_texts
        ],
        linkedin_text=linkedin_text or "",
        extra_info=extra_info or "",
        known_skills=known_skills,
    )


def _parse(raw: str) -> dict[int, dict]:
    parsed: dict[int, dict] = {}
    for match in _K_RE.finditer(raw or ""):
        attrs = {name: html.unescape(value) for name, value in _ATTR_RE.findall(match.group(1))}
        index = attrs.get("i", "")
        if index.isdigit():
            parsed[int(index)] = attrs
    return parsed


def _paths(verdict: dict, valid_paths: set) -> list[str]:
    return [path.strip() for path in verdict.get("where", "").split(";") if path.strip() in valid_paths]


def _resolve(base, confirmed, verdict, valid_paths, skills_paths) -> dict:
    verdict = verdict or {}
    bucket = verdict.get("bucket", "").strip().lower()
    evidence = verdict.get("evidence", "").strip() or None

    if bucket == "covered" and not confirmed:
        where = _paths(verdict, valid_paths)
        return {
            **base,
            "status": "exact",
            "evidence": evidence,
            "original_field_path": where[0] if where else None,
        }

    if bucket == "can_add" or confirmed:
        where = _paths(verdict, valid_paths)
        if not where:
            where = list(skills_paths[:1]) if base.get("category") in SKILL_CATEGORIES else [LETTER]
        return {
            **base,
            "status": "can_add",
            "evidence": evidence,
            "suggested_field_paths": list(where),
            "assigned_field_paths": list(where),
        }

    return {**base, "status": "unknown"}


def classify_requirements(
    provider,
    requirements: list[dict],
    block_texts: list[dict],
    resume_text: str,
    linkedin_text: str,
    extra_info: str | None,
    known_skills: list[str],
) -> list[dict]:
    resume_norm = normalize_text(resume_text)
    mentions_norm = normalize_text(f"{linkedin_text or ''}\n{extra_info or ''}")
    known_norms = {normalize_text(skill) for skill in known_skills}
    prepared = [{**block, "norm": normalize_text(block["text"])} for block in block_texts]
    valid_paths = {block["field_path"] for block in block_texts} | {LETTER}
    skills_paths = [block["field_path"] for block in block_texts if block["kind"] == "skills"]

    results: list[dict] = []
    pending: list[tuple[dict, bool, bool]] = []

    for requirement in requirements:
        base = _base_item(requirement)
        if contains_phrase(resume_norm, requirement["text"]):
            where = _locate(prepared, requirement["text"])
            results.append({**base, "status": "exact", "original_field_path": where[0] if where else None})
            continue
        if requirement.get("category") == "title":
            results.append({**base, "status": "unknown"})
            continue
        confirmed = normalize_text(requirement["text"]) in known_norms
        mentioned = confirmed or contains_phrase(mentions_norm, requirement["text"])
        pending.append((base, confirmed, mentioned))

    for start in range(0, len(pending), BATCH_SIZE):
        chunk = pending[start : start + BATCH_SIZE]
        batch = [
            {
                "i": index,
                "text": base["text"],
                "category": base["category"],
                "tier": base.get("tier"),
                "known": mentioned,
            }
            for index, (base, _, mentioned) in enumerate(chunk)
        ]
        try:
            raw = provider.call(
                system_prompt="You compare job posting keywords with a candidate's materials and output only <k /> tags.",
                user_prompt=_render(batch, block_texts, linkedin_text, extra_info, known_skills),
                max_tokens=4096,
            )
            parsed = _parse(raw)
        except Exception as error:
            logger.warning("[keywords] classification batch failed: %s", error)
            parsed = {}

        for index, (base, confirmed, _) in enumerate(chunk):
            verdict = parsed.get(index)
            item = _resolve(base, confirmed, verdict, valid_paths, skills_paths)
            item["why"] = (verdict or {}).get("why", "").strip() or None
            results.append(item)

    return results


def destinations_of(item: dict, skills_path: str | None, summary_path: str | None) -> set[str]:
    if item.get("category") == "title" or item["status"] not in ("can_add", "unknown"):
        return set()
    assigned = set(item.get("assigned_field_paths") or [])
    if item["status"] == "unknown" and not (assigned & {skills_path, summary_path, LETTER}):
        return set()

    found = set()
    if skills_path and skills_path in assigned:
        found.add("skills")
    if summary_path and summary_path in assigned:
        found.add("summary")
    if LETTER in assigned:
        found.add("letter")
    if not found:
        found.add("skills" if item.get("category") in SKILL_CATEGORIES else "letter")

    disabled = set(item.get("disabled_field_paths") or [])
    paths = {"skills": skills_path, "summary": summary_path, "letter": LETTER}
    return {kind for kind in found if paths[kind] not in disabled}


def keywords_for_block(items, kind, field_path, block_text, resume_text, other_path=None):
    skills_path, summary_path = (field_path, other_path) if kind == "skills" else (other_path, field_path)
    haystack = normalize_text(block_text if kind == "skills" else resume_text)
    chosen = []
    for item in items:
        if kind in destinations_of(item, skills_path, summary_path) and not contains_phrase(haystack, item["text"]):
            chosen.append(item)
    return chosen


def keywords_for_letter(items, skills_path, summary_path):
    return [item for item in items if LETTER in destinations_of(item, skills_path, summary_path)]