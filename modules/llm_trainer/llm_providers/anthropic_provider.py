"""Anthropic LLM Provider - Claude models"""

import os
import time
import json
import logging
from typing import Optional

import requests

from modules.llm_trainer.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """
    Anthropic API provider (Claude 3.5 Sonnet, Claude 3 Opus, etc.)

    Requires ANTHROPIC_API_KEY environment variable.
    """

    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 200
    ):
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Anthropic API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )
        super().__init__(model=model, api_key=api_key)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.session = requests.Session()
        self.session.headers.update({
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        })

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [
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
                self.total_input_tokens += usage.get("input_tokens", 0)
                self.total_output_tokens += usage.get("output_tokens", 0)

                # Extract text from content blocks
                content = data.get("content", [])
                text_parts = [block["text"] for block in content if block.get("type") == "text"]
                return " ".join(text_parts)

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

        raise RuntimeError("Anthropic API call failed after retries")
