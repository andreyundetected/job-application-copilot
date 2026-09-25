import datetime
import logging
import threading
import time

from core.db import crud
from core.db.session import SessionLocal
from core.tasks.executor import submit_task

logger = logging.getLogger(__name__)

STUCK_TIMEOUT_SECONDS = 180
CHECK_INTERVAL_SECONDS = 30
MAX_JOB_RETRIES = 3
MAX_QUESTION_RETRIES = 3

_lock = threading.Lock()
_error_events: list[dict] = []
_started = False


def push_error_event(job_id: int | None, company: str | None, role: str | None, reason: str) -> None:
    with _lock:
        _error_events.append({"job_id": job_id, "company": company, "role": role, "reason": reason})


def pop_error_events() -> list[dict]:
    with _lock:
        events = _error_events[:]
        _error_events.clear()
    return events


def _check_stuck_jobs() -> None:
    from core.automation.recovery import retry_stuck_job

    session = SessionLocal()
    try:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(seconds=STUCK_TIMEOUT_SECONDS)
        stuck_jobs = crud.list_stuck_jobs(session, cutoff)
    finally:
        session.close()

    for job_id, company, role, retry_count in stuck_jobs:
        if retry_count >= MAX_JOB_RETRIES:
            delete_session = SessionLocal()
            try:
                crud.delete_job_posting(delete_session, job_id)
            finally:
                delete_session.close()
            push_error_event(job_id, company, role, "evaluation_failed")
            logger.warning("[watchdog] job %s exceeded %s retries, deleted", job_id, MAX_JOB_RETRIES)
        else:
            logger.info("[watchdog] job %s stuck, retrying (%s/%s)", job_id, retry_count + 1, MAX_JOB_RETRIES)
            submit_task(retry_stuck_job, job_id)


def _check_stuck_questions() -> None:
    from core.questions.recovery import retry_stuck_question

    session = SessionLocal()
    try:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(seconds=STUCK_TIMEOUT_SECONDS)
        stuck_questions = crud.list_stuck_questions(session, cutoff)
    finally:
        session.close()

    for question_id, retry_count in stuck_questions:
        if retry_count >= MAX_QUESTION_RETRIES:
            flag_session = SessionLocal()
            try:
                crud.set_question_generation_result(
                    flag_session,
                    question_id,
                    answer_text=None,
                    selected_option=None,
                    needs_manual_input=True,
                    flag_reason="Auto-generation kept failing - please answer this one yourself.",
                )
                crud.set_question_pending_task(flag_session, question_id, None)
            finally:
                flag_session.close()
            logger.warning("[watchdog] question %s exceeded %s retries, flagged for manual input", question_id, MAX_QUESTION_RETRIES)
        else:
            logger.info("[watchdog] question %s stuck, retrying (%s/%s)", question_id, retry_count + 1, MAX_QUESTION_RETRIES)
            submit_task(retry_stuck_question, question_id)


def _loop() -> None:
    while True:
        time.sleep(CHECK_INTERVAL_SECONDS)
        try:
            _check_stuck_jobs()
            _check_stuck_questions()
        except Exception as error:
            logger.error("[watchdog] loop error: %s", error)


def start_watchdog() -> None:
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, daemon=True, name="stuck-job-watchdog").start()