import pytest

from core.providers.freellmapi import FreeLLMAPIProvider


class _FakeMessage:
    content = "fake response text"


class _FakeChoice:
    message = _FakeMessage()


class _FakeResponse:
    choices = [_FakeChoice()]


def _capture(monkeypatch, provider):
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        return _FakeResponse()

    monkeypatch.setattr(provider.client.chat.completions, "create", fake_create)
    return calls


@pytest.mark.providers
def test_temperature_is_not_sent_by_default(monkeypatch):
    provider = FreeLLMAPIProvider()
    calls = _capture(monkeypatch, provider)

    provider.call("system", "user")

    assert "temperature" not in calls[0]


@pytest.mark.providers
def test_temperature_zero_is_sent(monkeypatch):
    provider = FreeLLMAPIProvider()
    calls = _capture(monkeypatch, provider)

    provider.call("system", "user", temperature=0)

    assert calls[0]["temperature"] == 0


@pytest.mark.providers
def test_temperature_is_sent_together_with_reasoning_effort(monkeypatch):
    provider = FreeLLMAPIProvider()
    calls = _capture(monkeypatch, provider)

    provider.call("system", "user", reasoning_effort="low", temperature=0)

    assert calls[0]["temperature"] == 0
    assert calls[0]["extra_body"] == {"reasoning_effort": "low"}