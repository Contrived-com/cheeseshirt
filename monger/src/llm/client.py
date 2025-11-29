"""
LLM Client - Simple HTTP client for the LLM sidecar service.

The Monger talks to an LLM sidecar (llm-openai, llm-ollama, etc.)
via a simple HTTP interface. This client handles that communication.
"""
import time
import logging
from dataclasses import dataclass
from typing import Optional
from functools import lru_cache

import httpx

from ..config import get_settings
from ..stats import get_llm_stats

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    """A message in a conversation with the LLM."""
    role: str  # "system", "user", or "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from the LLM service."""
    content: str
    model: str
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None


class LLMClient:
    """HTTP client for the LLM sidecar service."""
    
    def __init__(self, base_url: str, timeout: float = 120.0):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)
        self._model_name: Optional[str] = None
        
        logger.info("LLM client initialized: %s", self._base_url)
    
    @property
    def model_name(self) -> str:
        """Return the model name (fetched from sidecar)."""
        return self._model_name or "unknown"
    
    async def chat(
        self,
        messages: list[LLMMessage],
        json_mode: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Send a chat request to the LLM sidecar.
        
        Args:
            messages: Conversation history
            json_mode: If True, request JSON-formatted response
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            LLMResponse with the generated content
        """
        start_time = time.time()
        
        payload = {
            "messages": [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ],
            "json_mode": json_mode,
        }
        
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        
        logger.debug(
            "LLM request: messages=%d, json_mode=%s",
            len(messages), json_mode
        )
        
        stats = get_llm_stats()
        
        try:
            response = await self._client.post(
                f"{self._base_url}/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            
            latency_ms = int((time.time() - start_time) * 1000)
            content = data.get("content", "")
            tokens_used = data.get("tokens_used")
            model = data.get("model", "unknown")
            
            # Cache model name
            if self._model_name is None:
                self._model_name = model
            
            stats.record_success(latency_ms, tokens_used)
            
            logger.debug(
                "LLM response: latency=%dms, tokens=%s, len=%d",
                latency_ms, tokens_used, len(content)
            )
            
            return LLMResponse(
                content=content,
                model=model,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
            )
            
        except httpx.HTTPStatusError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            stats.record_failure(latency_ms, error_msg)
            logger.error("LLM error after %dms: %s", latency_ms, error_msg)
            raise
            
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            stats.record_failure(latency_ms, error_msg)
            logger.error("LLM error after %dms: %s", latency_ms, error_msg)
            raise
    
    async def health_check(self) -> tuple[bool, Optional[str], Optional[int]]:
        """
        Check if the LLM sidecar is healthy.
        
        Returns:
            Tuple of (is_healthy, error_message, latency_ms)
        """
        start_time = time.time()
        
        try:
            response = await self._client.get(f"{self._base_url}/health")
            response.raise_for_status()
            data = response.json()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            if data.get("status") == "ok":
                # Fetch model name
                try:
                    model_resp = await self._client.get(f"{self._base_url}/model")
                    model_resp.raise_for_status()
                    self._model_name = model_resp.json().get("name", "unknown")
                except Exception:
                    pass
                
                logger.info("LLM health check OK: %dms, model=%s", latency_ms, self._model_name)
                return (True, None, latency_ms)
            else:
                error = data.get("error", "Service not ready")
                logger.warning("LLM health check degraded: %s", error)
                return (False, error, latency_ms)
                
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            logger.error("LLM health check failed: %s", error_msg)
            return (False, error_msg, latency_ms)


# Singleton client instance
_client: Optional[LLMClient] = None


@lru_cache()
def get_llm_client() -> LLMClient:
    """Get the LLM client instance."""
    settings = get_settings()
    return LLMClient(
        base_url=settings.llm_service_url,
        timeout=settings.llm_service_timeout,
    )

