from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    last_usage: dict | None = None

    @abstractmethod
    def call(self, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError

    def _extract_usage(self, response) -> dict:
        usage = getattr(response, "usage", None)

        if usage is None:
            return {
                "model": getattr(response, "model", None),
                "input_tokens": None,
                "output_tokens": None,
                "reasoning_tokens": None,
                "total_tokens": None,
            }

        reasoning_tokens = None
        details = getattr(usage, "completion_tokens_details", None)
        if details is not None:
            reasoning_tokens = getattr(details, "reasoning_tokens", None)

        return {
            "model": getattr(response, "model", None),
            "input_tokens": getattr(usage, "prompt_tokens", None),
            "output_tokens": getattr(usage, "completion_tokens", None),
            "reasoning_tokens": reasoning_tokens,
            "total_tokens": getattr(usage, "total_tokens", None),
        }