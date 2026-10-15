import pytest

import config
from core.providers.freellmapi_provider import FreeLLMAPIProvider
from core.providers.gemini_provider import GeminiProvider
from core.providers.openai_provider import OpenAIProvider
from core.providers.openrouter_provider import OpenRouterProvider


@pytest.mark.providers
@pytest.mark.parametrize("provider_cls", [OpenRouterProvider, OpenAIProvider, GeminiProvider, FreeLLMAPIProvider])
def test_explicit_temperature_is_used(provider_cls):
    provider = object.__new__(provider_cls)

    temperature, _ = provider._enforce_determinism(temperature=0.8)

    assert temperature == 0.8


@pytest.mark.providers
@pytest.mark.parametrize("provider_cls", [OpenRouterProvider, OpenAIProvider, GeminiProvider, FreeLLMAPIProvider])
def test_missing_temperature_falls_back_to_the_global_default(provider_cls):
    provider = object.__new__(provider_cls)

    temperature, _ = provider._enforce_determinism()

    assert temperature == config.LLM_TEMPERATURE


@pytest.mark.providers
def test_explicit_zero_is_not_replaced_by_the_default(monkeypatch):
    monkeypatch.setattr(config, "LLM_TEMPERATURE", 0.5)
    provider = object.__new__(OpenRouterProvider)

    temperature, _ = provider._enforce_determinism(temperature=0)

    assert temperature == 0