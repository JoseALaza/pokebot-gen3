"""OpenAI LLM Provider - GPT-4 and variants"""

import os
import time
import json
import logging
from typing import Optional

import requests

from modules.llm_trainer.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """
    OpenAI API provider (GPT-4, GPT-4o, GPT-4o-mini, etc.)

    Requires OPENAI_API_KEY environment variable.
    """

    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 200
    ):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        super().__init__(model=model, api_key=api_key)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }

        for attempt in range(3):
            try:
                response = self.session.post(
                    self.API_URL,
                    data=json.dumps(payload),
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()

                # Track tokens
                usage = data.get("usage", {})
                self.total_input_tokens += usage.get("prompt_tokens", 0)
                self.total_output_tokens += usage.get("completion_tokens", 0)

                return data["choices"][0]["message"]["content"]

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:
                    wait = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))

        raise RuntimeError("OpenAI API call failed after retries")
