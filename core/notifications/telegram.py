import logging

import requests

from core.db import crud
from core.db.session import SessionLocal

logger = logging.getLogger(__name__)

_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _send_raw(token: str, chat_id: str, text: str) -> None:
    try:
        response = requests.post(
            _API_URL.format(token=token),
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        if response.status_code != 200:
            logger.warning("[telegram] sendMessage failed: status=%s body=%s", response.status_code, response.text[:300])
    except requests.RequestException as error:
        logger.warning("[telegram] sendMessage request failed: %s", error)


def notify_job_evaluated(company: str | None, role: str | None, score: int | None, job_id: int) -> None:
    session = SessionLocal()
    try:
        settings = crud.get_app_settings(session)
    finally:
        session.close()

    if settings is None or not settings.telegram_notify_enabled:
        return
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return

    if settings.telegram_notify_only_successful and (score is None or score <= 0):
        return

    if settings.telegram_notify_min_score is not None and (score is None or score < settings.telegram_notify_min_score):
        return

    text = (
        f"🆕 Новая вакансия оценена: <b>{score if score is not None else '?'}</b>\n"
        f"{company or 'Unknown company'} — {role or 'Unknown role'}"
    )
    _send_raw(settings.telegram_bot_token, settings.telegram_chat_id, text)