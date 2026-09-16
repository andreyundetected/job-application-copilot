from openai import OpenAI

from core.providers.base import BaseLLMProvider
import config


class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        self.client = OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=config.GEMINI_API_KEY,
        )
        self.model = config.GEMINI_MODEL

    def call(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content