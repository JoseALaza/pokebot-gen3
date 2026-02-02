"""LLM Providers - Interfaces for different LLM APIs"""

from modules.llm_trainer.llm_providers.base import BaseLLMProvider
from modules.llm_trainer.llm_providers.openai_provider import OpenAIProvider
from modules.llm_trainer.llm_providers.anthropic_provider import AnthropicProvider
from modules.llm_trainer.llm_providers.gemini_provider import GeminiProvider


def create_provider(provider_name: str, **kwargs) -> BaseLLMProvider:
    """
    Factory function to create an LLM provider.

    Args:
        provider_name: One of "openai", "anthropic", "gemini"
        **kwargs: Provider-specific configuration

    Returns:
        Configured LLM provider instance
    """
    providers = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "gemini": GeminiProvider,
    }

    if provider_name not in providers:
        raise ValueError(f"Unknown provider: {provider_name}. Valid: {list(providers.keys())}")

    return providers[provider_name](**kwargs)
