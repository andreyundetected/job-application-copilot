from openai import BadRequestError, OpenAI

from core.providers.base import BaseLLMProvider
import config


class OpenRouterProvider(BaseLLMProvider):
    def __init__(self):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=config.OPENROUTER_API_KEY,
            timeout=120.0,
            max_retries=1,
        )
        self.model = config.OPENROUTER_MODEL

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

        extra_body = {"usage": {"include": True}}
        if reasoning_effort == "off":
            extra_body["reasoning"] = {"enabled": False}
        elif reasoning_effort is not None:
            extra_body["reasoning"] = {"effort": reasoning_effort}

        response = None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_body=extra_body,
                **base_kwargs,
            )
        except BadRequestError:
            response = None

        used_fallback = response is None
        if response is None:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                extra_body={"usage": {"include": True}},
                **base_kwargs,
            )

        self.last_usage = self._extract_usage(response)
        self.last_usage["fallback"] = used_fallback
        content = response.choices[0].message.content
        return content or ""