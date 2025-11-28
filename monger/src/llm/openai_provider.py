"""
OpenAI implementation of the LLM provider.
"""
import time
import logging
from typing import Optional

from openai import AsyncOpenAI

from .base import LLMProvider, LLMMessage, LLMResponse
from ..config import get_settings

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI-based LLM provider."""
    
    def __init__(self):
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._temperature = settings.openai_temperature
        self._max_tokens = settings.openai_max_tokens
    
    @property
    def provider_name(self) -> str:
        return "openai"
    
    @property
    def model_name(self) -> str:
        return self._model
    
    async def chat_completion(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Generate a chat completion using OpenAI."""
        start_time = time.time()
        
        # Convert to OpenAI message format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Build request params
        params = {
            "model": self._model,
            "messages": openai_messages,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
        }
        
        if json_mode:
            params["response_format"] = {"type": "json_object"}
        
        logger.debug(
            "OpenAI request: model=%s, messages=%d, json_mode=%s",
            self._model, len(messages), json_mode
        )
        
        try:
            completion = await self._client.chat.completions.create(**params)
            
            latency_ms = int((time.time() - start_time) * 1000)
            content = completion.choices[0].message.content or ""
            tokens_used = completion.usage.total_tokens if completion.usage else None
            
            logger.debug(
                "OpenAI response: latency=%dms, tokens=%s, content_len=%d",
                latency_ms, tokens_used, len(content)
            )
            
            return LLMResponse(
                content=content,
                model=completion.model,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error("OpenAI error after %dms: %s", latency_ms, str(e))
            raise
    
    async def test_connection(self) -> tuple[bool, Optional[str], Optional[int]]:
        """Test the OpenAI connection with a minimal request."""
        start_time = time.time()
        
        try:
            completion = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "Say 'ok' and nothing else."}],
                max_tokens=5,
                temperature=0,
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            logger.info("OpenAI connection test successful: %dms", latency_ms)
            
            return (True, None, latency_ms)
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            logger.error("OpenAI connection test failed: %s", error_msg)
            
            return (False, error_msg, latency_ms)

