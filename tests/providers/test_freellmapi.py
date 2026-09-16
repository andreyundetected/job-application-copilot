import pytest

from core.providers.freellmapi import FreeLLMAPIProvider


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


@pytest.mark.providers
def test_freellmapi_call_returns_content(monkeypatch):
    provider = FreeLLMAPIProvider()

    def fake_create(model, messages):
        assert model == provider.model
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        return _FakeResponse("fake response text")

    monkeypatch.setattr(provider.client.chat.completions, "create", fake_create)

    result = provider.call("system prompt", "user prompt")

    assert result == "fake response text"