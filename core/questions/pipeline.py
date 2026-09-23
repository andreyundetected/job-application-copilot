import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from core.parsing.html_like_parser import parse_html_like
from core.questions.text_sanitize import sanitize_generated_text

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    trim_blocks=True,
    lstrip_blocks=True,
)

_COVER_LETTER_PATTERNS = [
    r"cover letter",
    r"motivation letter",
    r"why (do you want to work|are you interested|should we hire)",
    r"why (this|our) (role|position|company|team)",
    r"what (makes|would make) you a (good|great) fit",
    r"сопроводительн\w* письм\w*",
    r"мотивационн\w* письм\w*",
    r"почему (вы хотите|вас заинтересовала|стоит нанять)",
    r"почему (эта|наша) (роль|позиция|компания|команда)",
]

_SUMMARY_PATTERNS = [
    r"tell us (a (little|bit) )?about yourself",
    r"about you\b",
    r"professional summary",
    r"introduce yourself",
    r"(brief|short|quick) (overview|summary|introduction)",
    r"summarize your (background|experience|career)",
    r"describe your (background|experience|career) in (a )?few (sentences|words)",
    r"who (are|is) you\b",
    r"расскажите о себе",
    r"немного о себе",
    r"о себе\b",
    r"краткое резюме",
    r"кратко расскажите",
    r"опишите себя",
]

_FLAG_PREFIX = "[FLAG_FOR_MANUAL_REVIEW]"

_NON_ANSWER_PATTERNS = [
    r"^\s*(user\s+)?safety\s*:",
    r"^\s*content\s+polic",
    r"^\s*as an ai",
    r"^\s*i (cannot|can't|am unable to)\s+(help|assist|answer)\b",
    r"^\s*i'm (sorry|unable)",
]


def _match_template_pattern(question_text: str) -> str | None:
    lowered = question_text.lower()
    for pattern in _COVER_LETTER_PATTERNS:
        if re.search(pattern, lowered):
            return "cover_letter"
    for pattern in _SUMMARY_PATTERNS:
        if re.search(pattern, lowered):
            return "summary"
    return None


def _looks_like_non_answer(text: str) -> bool:
    if not text or len(text.strip()) < 2:
        return True
    lowered = text.strip().lower()
    for pattern in _NON_ANSWER_PATTERNS:
        if re.match(pattern, lowered):
            return True
    return False


def _parse_flag(raw_text: str) -> tuple[str | None, str | None]:
    stripped = raw_text.strip()

    if stripped.startswith(_FLAG_PREFIX):
        reason = stripped[len(_FLAG_PREFIX):].strip()
        return None, reason or "The agent could not answer this confidently."

    if _looks_like_non_answer(stripped):
        return None, "The model returned an unexpected non-answer - please review and answer this one yourself."

    return stripped, None


def split_and_classify_questions(provider, raw_text: str) -> list[dict]:
    """Split-only phase. Only extracts open-ended, written-answer questions
    (see split_questions_prompt.jinja) - short/choice/yes-no fields are meant
    to be answered by the candidate directly and are never sent here."""
    template = _env.get_template("split_questions_prompt.jinja")
    prompt = template.render(raw_text=raw_text)

    raw_response = provider.call(
        system_prompt="You split a pasted job application form into individual open-ended written-answer questions.",
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)

    questions = []
    for item in parsed.get("question", []):
        if isinstance(item, str):
            questions.append({"question_text": item.strip(), "char_limit": None})
            continue

        text = (item.get("text") or "").strip()
        if not text:
            continue

        char_limit_raw = (item.get("char_limit") or "").strip()
        char_limit = int(char_limit_raw) if char_limit_raw.isdigit() else None
        questions.append({"question_text": text, "char_limit": char_limit})

    return questions


def classify_template_category(provider, question_text: str) -> str:
    pattern_match = _match_template_pattern(question_text)
    if pattern_match:
        return pattern_match

    template = _env.get_template("template_match_prompt.jinja")
    prompt = template.render(question_text=question_text)

    raw_response = provider.call(
        system_prompt="You classify a job application question into a small fixed set of categories.",
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)
    values = parsed.get("category", [])
    category = values[0] if values and isinstance(values[0], str) else None

    if category not in ("cover_letter", "summary"):
        return "general"
    return category


def split_and_prepare_questions(provider, raw_text: str, custom_templates: list | None = None) -> list[dict]:
    """custom_templates: list of QuestionTemplate rows (label, trigger_phrases, instructions),
    checked against each extracted question before falling back to the built-in
    cover_letter/summary/general classification."""
    from core.db.crud.question_templates import match_question_template

    questions = split_and_classify_questions(provider, raw_text)
    custom_templates = custom_templates or []

    results = []
    for question in questions:
        matched_template = match_question_template(custom_templates, question["question_text"])
        template_label = matched_template.label if matched_template else None
        template_instructions = matched_template.instructions if matched_template else None

        category = classify_template_category(provider, question["question_text"])

        results.append(
            {
                "question_text": question["question_text"],
                "answer_type": "document",
                "category": category,
                "options": None,
                "char_limit": question.get("char_limit"),
                "needs_manual_input": False,
                "flag_reason": None,
                "template_label": template_label,
                "template_instructions": template_instructions,
            }
        )

    return results


def _render(template_name: str, **kwargs) -> str:
    template = _env.get_template(template_name)
    return template.render(**kwargs)


def _parse_single_flagged_response(raw_response: str) -> dict:
    answer_text, flag_reason = _parse_flag(raw_response)
    return {
        "answer_text": sanitize_generated_text(answer_text),
        "needs_manual_input": answer_text is None,
        "flag_reason": flag_reason,
    }


def generate_cover_letter_answers(
    provider,
    questions: list[dict],
    job_posting_text: str,
    resume_text: str,
    linkedin_text: str,
    extra_info: str | None = None,
    writing_preferences: str | None = None,
    links: list[str] | None = None,
) -> dict[int, dict]:
    """questions: list of {"id": int, "question_text": str, "char_limit": int|None}."""
    results = {}
    for question in questions:
        prompt = _render(
            "cover_letter_prompt.jinja",
            question_text=question["question_text"],
            job_posting_text=job_posting_text,
            resume_text=resume_text,
            linkedin_text=linkedin_text,
            extra_info=extra_info or "",
            writing_preferences=writing_preferences or "",
            links=links or [],
            char_limit=question.get("char_limit"),
        )
        raw_response = provider.call(
            system_prompt="You write a truthful, specific cover letter for the candidate, in the first person.",
            user_prompt=prompt,
        )
        results[question["id"]] = _parse_single_flagged_response(raw_response)
    return results


def generate_summary_answers(
    provider,
    questions: list[dict],
    job_posting_text: str,
    resume_text: str,
    linkedin_text: str,
    extra_info: str | None = None,
    writing_preferences: str | None = None,
    links: list[str] | None = None,
) -> dict[int, dict]:
    results = {}
    for question in questions:
        prompt = _render(
            "summary_prompt.jinja",
            question_text=question["question_text"],
            job_posting_text=job_posting_text,
            resume_text=resume_text,
            linkedin_text=linkedin_text,
            extra_info=extra_info or "",
            writing_preferences=writing_preferences or "",
            links=links or [],
            char_limit=question.get("char_limit"),
        )
        raw_response = provider.call(
            system_prompt="You write a truthful, concise professional summary for the candidate, in the first person.",
            user_prompt=prompt,
        )
        results[question["id"]] = _parse_single_flagged_response(raw_response)
    return results


def generate_general_answers_initial(
    provider,
    questions: list[dict],
    job_posting_text: str,
    resume_text: str,
    linkedin_text: str,
    extra_info: str | None = None,
    writing_preferences: str | None = None,
    links: list[str] | None = None,
) -> dict[int, dict]:
    """One batched call answering every 'general' (non cover_letter/summary)
    open-ended question at once. questions may carry an optional
    'template_instructions' key (from a matched custom QuestionTemplate),
    surfaced per-question in the prompt."""
    if not questions:
        return {}

    prompt = _render(
        "general_batch_prompt.jinja",
        questions=questions,
        job_posting_text=job_posting_text,
        resume_text=resume_text,
        linkedin_text=linkedin_text,
        extra_info=extra_info or "",
        writing_preferences=writing_preferences or "",
        links=links or [],
    )

    raw_response = provider.call(
        system_prompt=(
            "You answer several job application form questions at once, as the candidate, in the first "
            "person, each grounded only in the candidate's real background. Never invent facts."
        ),
        user_prompt=prompt,
    )

    parsed = parse_html_like(raw_response)
    results = {}
    for item in parsed.get("answer", []):
        if isinstance(item, str):
            continue
        qid_raw = item.get("question_id")
        if not qid_raw or not str(qid_raw).isdigit():
            continue
        qid = int(qid_raw)
        results[qid] = _parse_single_flagged_response(item.get("text", ""))

    for question in questions:
        if question["id"] not in results:
            results[question["id"]] = {
                "answer_text": None,
                "needs_manual_input": True,
                "flag_reason": "The agent did not return an answer for this question - please answer it yourself.",
            }

    return results


def run_advisor_chat(
    provider,
    user_message: str,
    conversation_history: list[dict],
    questions: list[dict],
    job_posting_text: str,
    resume_text: str,
    linkedin_text: str,
    extra_info: str | None = None,
) -> str:
    """Runs when the candidate hasn't selected a specific answer card. Sees
    everything but structurally cannot propose changes - just talks."""
    prompt = _render(
        "advisor_chat_prompt.jinja",
        user_message=user_message,
        conversation_history=conversation_history,
        questions=questions,
        job_posting_text=job_posting_text,
        resume_text=resume_text,
        linkedin_text=linkedin_text,
        extra_info=extra_info or "",
    )

    raw_response = provider.call(
        system_prompt=(
            "You are a helpful copilot discussing the candidate's job application questions and answers. "
            "You cannot edit any answer right now - only talk, explain, and advise."
        ),
        user_prompt=prompt,
    )

    return raw_response.strip()


def run_targeted_revision(
    provider,
    category: str,
    question_text: str,
    current_answer: str,
    user_message: str,
    conversation_history: list[dict],
    job_posting_text: str,
    resume_text: str,
    linkedin_text: str,
    char_limit: int | None = None,
    extra_info: str | None = None,
    links: list[str] | None = None,
) -> dict:
    """Runs when the candidate has one specific answer card selected."""
    template_name = {
        "cover_letter": "revise_cover_letter_prompt.jinja",
        "summary": "revise_summary_prompt.jinja",
    }.get(category, "revise_general_prompt.jinja")

    prompt = _render(
        template_name,
        question_text=question_text,
        current_answer=current_answer,
        user_message=user_message,
        conversation_history=conversation_history,
        job_posting_text=job_posting_text,
        resume_text=resume_text,
        linkedin_text=linkedin_text,
        char_limit=char_limit,
        extra_info=extra_info or "",
        links=links or [],
    )

    raw_response = provider.call(
        system_prompt=(
            "You revise a job application answer based on the candidate's feedback, in the first person. "
            "Never output meta-commentary, safety labels, or policy notes."
        ),
        user_prompt=prompt,
    )

    message_match = re.search(r"<message>(.*?)</message>", raw_response, re.DOTALL)
    answer_match = re.search(r"<answer>(.*?)</answer>", raw_response, re.DOTALL)

    message_text = message_match.group(1).strip() if message_match else ""
    raw_answer = answer_match.group(1).strip() if answer_match else ""

    answer_text, flag_reason = _parse_flag(raw_answer) if raw_answer else (None, "No answer returned.")

    return {
        "message": message_text,
        "answer_text": sanitize_generated_text(answer_text),
        "needs_manual_input": answer_text is None,
        "flag_reason": flag_reason,
    }