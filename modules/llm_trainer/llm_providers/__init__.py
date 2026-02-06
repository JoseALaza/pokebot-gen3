"""LLM Providers - Interfaces for different LLM APIs"""

from modules.llm_trainer.llm_providers.base import BaseLLMProvider
from modules.llm_trainer.llm_providers.openai_provider import OpenAIProvider
from modules.llm_trainer.llm_providers.anthropic_provider import AnthropicProvider
from modules.llm_trainer.llm_providers.gemini_provider import GeminiProvider
from modules.llm_trainer.llm_providers.ollama_provider import OllamaProvider


def create_provider(provider_name: str, **kwargs) -> BaseLLMProvider:
    """
    Factory function to create an LLM provider.

    Args:
        provider_name: One of "openai", "anthropic", "gemini", "ollama"
        **kwargs: Provider-specific configuration

    Returns:
        Configured LLM provider instance
        
    Examples:
        # Cloud providers (require API keys)
        provider = create_provider("openai", model="gpt-4o-mini")
        provider = create_provider("anthropic", model="claude-sonnet-4-20250514")
        provider = create_provider("gemini", model="gemini-2.0-flash")
        
        # Local provider (no API key)
        provider = create_provider("ollama", model="llama3.1:8b")
    """
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
        "ollama": OllamaProvider,
    }

    if provider_name not in providers:
        raise ValueError(f"Unknown provider: {provider_name}. Valid: {list(providers.keys())}")

    return providers[provider_name](**kwargs)