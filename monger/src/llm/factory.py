"""
Factory for creating LLM provider instances.
"""
import logging
from functools import lru_cache

from .base import LLMProvider
from ..config import get_settings

logger = logging.getLogger(__name__)


@lru_cache()
def get_llm_provider() -> LLMProvider:
    """
    Get the configured LLM provider.
    
    The provider is determined by the LLM_PROVIDER environment variable.
    Currently supported: "openai"
    Future: "local" for self-hosted models
    """
    settings = get_settings()
    provider = settings.llm_provider.lower()
    
    logger.info("Initializing LLM provider: %s", provider)
    
    if provider == "openai":
        from .openai_provider import OpenAIProvider
        return OpenAIProvider()
    
    # Future: add more providers here
    # elif provider == "local":
    #     from .local_provider import LocalProvider
    #     return LocalProvider()
    
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider}. "
            f"Supported providers: openai"
        )

