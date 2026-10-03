from openai import BadRequestError, OpenAI

from core.providers.base import BaseLLMProvider
import config


class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        self.client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=config.GEMINI_API_KEY,
            timeout=60.0,
            max_retries=1,
        )
        self.model = config.GEMINI_MODEL

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
        temperature: float | None = None,
    ) -> str:
        base_kwargs = {}
        if max_tokens is not None:
            base_kwargs["max_tokens"] = max_tokens
        if temperature is not None:
            base_kwargs["temperature"] = temperature

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = None
        if reasoning_effort is not None:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    extra_body={"reasoning_effort": reasoning_effort},
                    **base_kwargs,
                )
            except Exception:
                response = None

        used_fallback = response is None
        if response is None:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **base_kwargs,
            )

        self.last_usage = self._extract_usage(response)
        self.last_usage["fallback"] = used_fallback
        content = response.choices[0].message.content
        reasoning = getattr(response.choices[0].message, "reasoning", None) or getattr(
            response.choices[0].message, "reasoning_content", None
        )
        if reasoning and not (content or "").strip():
            return ""
        return content or ""