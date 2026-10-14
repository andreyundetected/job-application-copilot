import pytest

from core.discovery import run_control
from core.notifications import telegram


class _FakeSession:
    def close(self):
        pass


class _Settings:
    telegram_notify_enabled = True
    telegram_bot_token = "token"
    telegram_chat_id = "chat"
    telegram_notify_only_successful = True
    telegram_notify_min_score = 7


@pytest.fixture()
def env(monkeypatch):
    run_control.reset_run()
    state = {"result": True, "messages": []}
    monkeypatch.setattr(telegram, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(telegram.crud, "get_app_settings", lambda session: _Settings())

    def fake_send(token, chat_id, text):
        state["messages"].append(text)
        return state["result"]

    monkeypatch.setattr(telegram, "_send_raw", fake_send)
    return state


@pytest.mark.notifications
def test_sent_is_counted(env):
    telegram.notify_job_evaluated("Acme", "Engineer", 9, 1)

    assert run_control.get_flow()["telegram"]["sent"] == 1


@pytest.mark.notifications
def test_failed_send_is_not_counted(env):
    env["result"] = False

    telegram.notify_job_evaluated("Acme", "Engineer", 9, 1)

    assert run_control.get_flow()["telegram"]["sent"] == 0


@pytest.mark.notifications
def test_blocked_is_counted_and_not_sent(env):
    telegram.notify_job_evaluated("Acme", "Engineer", 9, 1, blocked=True)

    assert env["messages"] == []
    assert run_control.get_flow()["telegram"]["blocked"] == 1


@pytest.mark.notifications
def test_low_score_is_counted_as_below_threshold(env):
    telegram.notify_job_evaluated("Acme", "Engineer", 5, 1)

    assert env["messages"] == []
    assert run_control.get_flow()["telegram"]["below_score"] == 1