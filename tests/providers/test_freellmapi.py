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


class _FakeUsageDetails:
    def __init__(self, reasoning_tokens):
        self.reasoning_tokens = reasoning_tokens


class _FakeUsage:
    def __init__(self, prompt_tokens, completion_tokens, total_tokens, reasoning_tokens=None):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.completion_tokens_details = _FakeUsageDetails(reasoning_tokens)


class _FakeResponseWithUsage(_FakeResponse):
    def __init__(self, content, model, usage):
        super().__init__(content)
        self.model = model
        self.usage = usage


@pytest.mark.providers
def test_freellmapi_call_records_usage(monkeypatch):
    provider = FreeLLMAPIProvider()

    usage = _FakeUsage(prompt_tokens=120, completion_tokens=45, total_tokens=165, reasoning_tokens=10)
    response = _FakeResponseWithUsage("fake response text", "gpt-test", usage)

    def fake_create(model, messages):
        return response

    monkeypatch.setattr(provider.client.chat.completions, "create", fake_create)

    provider.call("system prompt", "user prompt")

    assert provider.last_usage == {
        "model": "gpt-test",
        "input_tokens": 120,
        "output_tokens": 45,
        "reasoning_tokens": 10,
        "total_tokens": 165,
    }


@pytest.mark.providers
def test_freellmapi_call_handles_missing_usage_gracefully(monkeypatch):
    provider = FreeLLMAPIProvider()

    def fake_create(model, messages):
        return _FakeResponse("fake response text")

    monkeypatch.setattr(provider.client.chat.completions, "create", fake_create)

    provider.call("system prompt", "user prompt")

    assert provider.last_usage == {
        "model": None,
        "input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "total_tokens": None,
    }