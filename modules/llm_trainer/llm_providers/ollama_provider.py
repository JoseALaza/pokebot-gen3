"""Ollama LLM Provider - Local models via Ollama"""

import time
import json
import logging
from typing import Optional

import requests

from modules.llm_trainer.llm_providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """
    Ollama API provider for local LLMs.
    
    Supports any model available through Ollama:
    - llama3.2:3b (fast, lightweight)
    - llama3.1:8b (good balance)
    - llama3.1:70b (highest quality, slow)
    - codellama:13b (coding-focused)
    - mistral:7b (good alternative)
    
    No API key required - runs locally!
    
    Install Ollama from: https://ollama.com
    Then: ollama pull llama3.1:8b
    """
    
    def __init__(
        self,
        model: str = "llama3.1:8b",
        host: str = "http://localhost:11434",
        temperature: float = 0.3,
        max_tokens: int = 200
    ):
        # No API key needed for local models
        super().__init__(model=model, api_key=None)
        self.host = host
        self.api_url = f"{host}/api/generate"
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Test connection
        try:
            response = requests.get(f"{host}/api/tags", timeout=2)
            if response.status_code == 200:
                logger.info(f"Connected to Ollama at {host}")
            else:
                logger.warning(f"Ollama returned status {response.status_code}")
        except requests.exceptions.RequestException:
            logger.warning(
                f"Could not connect to Ollama at {host}. "
                f"Make sure Ollama is running!"
            )
    
    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call Ollama API with system + user prompts.
        
        Ollama uses a different format than OpenAI/Anthropic:
        - Combines system and user into single prompt
        - Streams response by default
        """
        # Combine system and user prompts
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,  # Get full response at once
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens
            }
        }
        
        for attempt in range(3):
            try:
                response = requests.post(
                    self.api_url,
                    json=payload,
                    timeout=60  # Local models can be slow
                )
                response.raise_for_status()
                data = response.json()
                
                # Ollama returns tokens in a different format
                # We'll estimate based on response length
                response_text = data.get("response", "")
                self.total_output_tokens += len(response_text.split()) * 1.3  # Rough estimate
                self.total_input_tokens += len(full_prompt.split()) * 1.3
                
                return response_text
                
            except requests.exceptions.Timeout:
                logger.warning(f"Ollama timeout on attempt {attempt + 1}/3")
                if attempt == 2:
                    raise
                time.sleep(1)
                
            except requests.exceptions.ConnectionError:
                logger.error(
                    "Could not connect to Ollama. "
                    "Make sure Ollama is running: ollama serve"
                )
                raise
                
            except Exception as e:
                if attempt == 2:
                    raise
                logger.warning(f"Ollama error: {e}, retrying...")
                time.sleep(1)
        
        raise RuntimeError("Ollama API call failed after retries")
    
    def list_models(self) -> list[str]:
        """List available models in Ollama"""
        try:
            response = requests.get(f"{self.host}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
        except Exception as e:
            logger.error(f"Could not list Ollama models: {e}")
        return []
    
    def pull_model(self, model_name: str):
        """
        Download a model from Ollama registry.
        This can take a while for large models!
        """
        logger.info(f"Pulling model {model_name} from Ollama...")
        
        payload = {"name": model_name, "stream": False}
        
        try:
            response = requests.post(
                f"{self.host}/api/pull",
                json=payload,
                timeout=600  # 10 minutes for download
            )
            response.raise_for_status()
            logger.info(f"Successfully pulled {model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False


def test_ollama():
    """Test function to verify Ollama is working"""
    print("Testing Ollama connection...")
    
    provider = OllamaProvider(model="llama3.1:8b")
    
    print(f"\nAvailable models: {provider.list_models()}")
    
    print("\nTesting simple prompt...")
    response = provider._call_api(
        "You are a helpful Pokemon expert.",
        "In one sentence, what is a good starter Pokemon in FireRed?"
    )
    
    print(f"\nResponse: {response}")
    print(f"\nStats: {provider.get_usage_stats()}")


if __name__ == "__main__":
    test_ollama()