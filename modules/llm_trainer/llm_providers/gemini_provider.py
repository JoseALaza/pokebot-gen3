"""Google Gemini LLM Provider"""

import os
import time
import json
import logging
from typing import Optional

import requests

from modules.llm_trainer.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini API provider (Gemini Pro, Gemini Flash, etc.)

    Requires GEMINI_API_KEY environment variable.
    """

    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 200
    ):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "Gemini API key required. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        super().__init__(model=model, api_key=api_key)
        self.temperature = temperature
        self.max_tokens = max_tokens

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self.API_BASE}/{self.model}:generateContent?key={self.api_key}"

        payload = {
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "parts": [{"text": user_prompt}]
                }
            ],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_tokens
            }
        }

        for attempt in range(3):
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()

                # Track tokens
                usage = data.get("usageMetadata", {})
                self.total_input_tokens += usage.get("promptTokenCount", 0)
                self.total_output_tokens += usage.get("candidatesTokenCount", 0)

                # Extract text
                candidates = data.get("candidates", [])
                if candidates:
                    content = candidates[0].get("content", {})
                    parts = content.get("parts", [])
                    text_parts = [p["text"] for p in parts if "text" in p]
                    return " ".join(text_parts)

                return ""

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

        raise RuntimeError("Gemini API call failed after retries")
