import pytest

from core.providers.factory import get_llm_provider
from core.providers.freellmapi import FreeLLMAPIProvider
from core.providers.openai_provider import OpenAIProvider
from core.providers.gemini_provider import GeminiProvider
import config


@pytest.mark.providers
def test_get_llm_provider_freellmapi(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "freellmapi")
    provider = get_llm_provider()
    assert isinstance(provider, FreeLLMAPIProvider)


@pytest.mark.providers
def test_get_llm_provider_openai(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(config, "OPENAI_API_KEY", "fake-key")
    provider = get_llm_provider()
    assert isinstance(provider, OpenAIProvider)


@pytest.mark.providers
def test_get_llm_provider_gemini(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(config, "GEMINI_API_KEY", "fake-key")
    provider = get_llm_provider()
    assert isinstance(provider, GeminiProvider)


@pytest.mark.providers
def test_get_llm_provider_unknown(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "not_a_real_provider")
    with pytest.raises(ValueError):
        get_llm_provider()