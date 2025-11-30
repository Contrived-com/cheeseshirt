"""
Abstract base class for LLM providers.

Implementations must subclass LLMProvider and implement all abstract methods.
The server module uses this interface to create a consistent API across providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ChatResult:
    """Result from a chat completion."""
    content: str
    tokens_used: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


@dataclass 
class HealthResult:
    """Result from a health check."""
    status: str  # "ok", "degraded", "error"
    model_loaded: bool
    error: Optional[str] = None


@dataclass
class ModelInfoResult:
    """Result from model info query."""
    parameters: Optional[str] = None  # e.g., "3.8B"
    context_length: Optional[int] = None


class LLMProvider(ABC):
    """
    Abstract interface that all LLM implementations must satisfy.
    
    Implementations should:
    1. Set provider_name and model_name in __init__
    2. Implement all abstract methods
    3. Handle their own client/connection lifecycle in initialize/shutdown
    """
    
    # These must be set by implementations
    provider_name: str  # e.g., "openai", "ollama"
    model_name: str     # e.g., "gpt-4o", "phi3.5"
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Called on application startup.
        
        Set up clients, pull models, establish connections, etc.
        This may be called before the first request.
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """
        Called on application shutdown.
        
        Clean up resources, close connections, etc.
        """
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> ChatResult:
        """
        Perform a chat completion.
        
        Args:
            messages: List of {"role": str, "content": str} dicts
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response
            json_mode: Request JSON-formatted output
            
        Returns:
            ChatResult with content and optional token counts
            
        Raises:
            Exception on failure (will be caught and converted to HTTP 5xx)
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> HealthResult:
        """
        Check if the provider is healthy and ready to serve requests.
        
        Should be fast (<1s). Don't do inference.
        
        Returns:
            HealthResult with status, model_loaded flag, and optional error
        """
        pass
    
    @abstractmethod
    async def get_model_info(self) -> ModelInfoResult:
        """
        Get information about the loaded model.
        
        Returns:
            ModelInfoResult with optional parameters size and context length
        """
        pass

