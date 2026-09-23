from openai import OpenAI

from core.providers.base import BaseLLMProvider
import config


class FreeLLMAPIProvider(BaseLLMProvider):
    def __init__(self):
        self.client = OpenAI(
            base_url=config.FREELLMAPI_BASE_URL,
            api_key=config.FREELLMAPI_KEY or "unused",
        )
        self.model = config.FREELLMAPI_MODEL

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
    ) -> str:
        base_kwargs = {}
        if max_tokens is not None:
            base_kwargs["max_tokens"] = max_tokens

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
                # Whatever model answered this "auto" request may not support
                # (or may reject as an unknown field) reasoning_effort - fall
                # back to a plain call rather than hard-failing the request.
                response = None

        if response is None:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                **base_kwargs,
            )

        self.last_usage = self._extract_usage(response)
        content = response.choices[0].message.content
        reasoning = getattr(response.choices[0].message, "reasoning", None) or getattr(
            response.choices[0].message, "reasoning_content", None
        )
        if reasoning and not (content or "").strip():
            return ""
        return content or ""