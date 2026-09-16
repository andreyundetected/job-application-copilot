from core.providers.base import BaseLLMProvider
from core.providers.freellmapi import FreeLLMAPIProvider
from core.providers.openai_provider import OpenAIProvider
from core.providers.gemini_provider import GeminiProvider
import config

_PROVIDERS = {
    "freellmapi": FreeLLMAPIProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}


def get_llm_provider() -> BaseLLMProvider:
    provider_cls = _PROVIDERS.get(config.LLM_PROVIDER)
    if provider_cls is None:
        raise ValueError(f"Unknown LLM_PROVIDER: {config.LLM_PROVIDER}")
    return provider_cls()