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

    def call(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content