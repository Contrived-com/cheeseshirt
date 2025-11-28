"""
Abstract base class for LLM providers.

This abstraction allows swapping out the underlying LLM (OpenAI, local models, etc.)
without changing the rest of the codebase.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMMessage:
    """A message in a conversation with the LLM."""
    role: str  # "system", "user", or "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of this provider (e.g., 'openai', 'local')."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model being used."""
        pass
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Generate a chat completion.
        
        Args:
            messages: List of messages in the conversation
            json_mode: If True, request JSON-formatted response
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            LLMResponse with the generated content
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> tuple[bool, Optional[str], Optional[int]]:
        """
        Test the connection to the LLM provider.
        
        Returns:
            Tuple of (success, error_message, latency_ms)
        """
        pass

