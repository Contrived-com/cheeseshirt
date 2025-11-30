"""
OpenAI provider implementation.

Implements LLMProvider for OpenAI's chat completions API.
"""

import os
import logging
from typing import Optional

from openai import AsyncOpenAI

from llm_base import LLMProvider, ChatResult, HealthResult, ModelInfoResult


logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """LLM provider using OpenAI's API."""
    
    def __init__(self):
        self.provider_name = "openai"
        self.model_name = os.getenv("MODEL_NAME", "gpt-4o")
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._client: Optional[AsyncOpenAI] = None
    
    async def initialize(self) -> None:
        """Initialize the OpenAI client."""
        if not self._api_key:
            logger.error("OPENAI_API_KEY not set!")
            return
        
        self._client = AsyncOpenAI(api_key=self._api_key)
        logger.info("OpenAI client initialized")
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        self._client = None
    
    async def chat(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> ChatResult:
        """Send a chat completion request to OpenAI."""
        if self._client is None:
            raise RuntimeError("OpenAI client not initialized")
        
        params = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if json_mode:
            params["response_format"] = {"type": "json_object"}
        
        completion = await self._client.chat.completions.create(**params)
        
        content = completion.choices[0].message.content or ""
        
        # Extract token counts
        tokens_used = None
        prompt_tokens = None
        completion_tokens = None
        if completion.usage:
            tokens_used = completion.usage.total_tokens
            prompt_tokens = completion.usage.prompt_tokens
            completion_tokens = completion.usage.completion_tokens
        
        return ChatResult(
            content=content,
            tokens_used=tokens_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    
    async def health_check(self) -> HealthResult:
        """Check if OpenAI client is configured."""
        if self._client is None:
            return HealthResult(
                status="error",
                model_loaded=False,
                error="OPENAI_API_KEY not configured",
            )
        
        # For cloud API, we assume it's available if client is configured
        # Don't make an API call on every health check
        return HealthResult(
            status="ok",
            model_loaded=True,
        )
    
    async def get_model_info(self) -> ModelInfoResult:
        """Get model info (limited for cloud API)."""
        # OpenAI doesn't expose parameter counts or context length via API
        return ModelInfoResult(
            parameters=None,
            context_length=None,
        )

