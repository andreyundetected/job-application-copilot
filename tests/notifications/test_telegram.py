import pytest

from core.notifications import telegram


class _FakeSession:
    def close(self):
        pass


class _Settings:
    telegram_notify_enabled = True
    telegram_bot_token = "token"
    telegram_chat_id = "chat"
    telegram_notify_only_successful = False
    telegram_notify_min_score = None


@pytest.fixture()
def sent(monkeypatch):
    messages = []
    monkeypatch.setattr(telegram, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(telegram.crud, "get_app_settings", lambda session: _Settings())
    monkeypatch.setattr(telegram, "_send_raw", lambda token, chat_id, text: messages.append(text))
    return messages


@pytest.mark.notifications
def test_blocked_job_is_not_sent(sent):
    telegram.notify_job_evaluated("Acme", "Engineer", 9, 1, blocked=True)

    assert sent == []


@pytest.mark.notifications
def test_unblocked_job_is_sent(sent):
    telegram.notify_job_evaluated("Acme", "Engineer", 9, 1, blocked=False)

    assert len(sent) == 1
    assert "Acme" in sent[0]