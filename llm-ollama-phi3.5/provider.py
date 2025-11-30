"""
Ollama provider implementation.

Implements LLMProvider for local models via Ollama.
This is identical to llm-ollama/provider.py - kept separate for build isolation.
"""

import os
import logging
from typing import Optional

import httpx

from llm_base import LLMProvider, ChatResult, HealthResult, ModelInfoResult


logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """LLM provider using Ollama for local inference."""
    
    def __init__(self):
        self.provider_name = "ollama"
        self.model_name = os.getenv("MODEL_NAME", "phi3.5:3.8b-mini-instruct-q4_K_M")
        self._ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self._client: Optional[httpx.AsyncClient] = None
        self._model_info: Optional[dict] = None
    
    async def initialize(self) -> None:
        """Initialize the Ollama client and wait for Ollama to be ready."""
        import asyncio
        
        self._client = httpx.AsyncClient(timeout=120.0)
        
        # Wait for Ollama to be ready
        logger.info("Waiting for Ollama at %s...", self._ollama_host)
        for attempt in range(30):
            try:
                response = await self._client.get(
                    f"{self._ollama_host}/api/tags",
                    timeout=5.0
                )
                response.raise_for_status()
                logger.info("Ollama is ready")
                break
            except Exception:
                logger.debug("Attempt %d/30...", attempt + 1)
                await asyncio.sleep(1)
        else:
            logger.error("Ollama not available after 30 seconds")
            return
        
        # Model should already be present (baked in), but verify
        if not await self._is_model_loaded():
            logger.warning("Model %s not found - this image should have it baked in!", self.model_name)
            # Try pulling anyway as fallback
            await self._pull_model()
    
    async def shutdown(self) -> None:
        """Clean up resources."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def _is_model_loaded(self) -> bool:
        """Check if our model is available."""
        if not self._client:
            return False
        try:
            response = await self._client.get(
                f"{self._ollama_host}/api/tags",
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            # Check both with and without tag
            base_name = self.model_name.split(":")[0]
            return (
                self.model_name in models or 
                f"{self.model_name}:latest" in models or
                base_name in models or
                f"{base_name}:latest" in models
            )
        except Exception:
            return False
    
    async def _pull_model(self) -> bool:
        """Pull the model if not already available."""
        if not self._client:
            return False
        logger.info("Pulling model %s...", self.model_name)
        try:
            response = await self._client.post(
                f"{self._ollama_host}/api/pull",
                json={"name": self.model_name, "stream": False},
                timeout=600.0,
            )
            response.raise_for_status()
            logger.info("Model %s pulled successfully", self.model_name)
            return True
        except Exception as e:
            logger.error("Failed to pull model %s: %s", self.model_name, e)
            return False
    
    async def _get_ollama_model_info(self) -> Optional[dict]:
        """Get information about the loaded model from Ollama."""
        if self._model_info:
            return self._model_info
        if not self._client:
            return None
        try:
            response = await self._client.post(
                f"{self._ollama_host}/api/show",
                json={"name": self.model_name},
                timeout=10.0,
            )
            response.raise_for_status()
            self._model_info = response.json()
            return self._model_info
        except Exception:
            return None
    
    async def chat(
        self,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> ChatResult:
        """Send a chat completion request to Ollama."""
        if self._client is None:
            raise RuntimeError("Ollama client not initialized")
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        
        if json_mode:
            payload["format"] = "json"
        
        response = await self._client.post(
            f"{self._ollama_host}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
        
        content = result.get("message", {}).get("content", "")
        
        # Extract token counts
        tokens_used = None
        prompt_tokens = None
        completion_tokens = None
        if "prompt_eval_count" in result or "eval_count" in result:
            prompt_tokens = result.get("prompt_eval_count", 0)
            completion_tokens = result.get("eval_count", 0)
            tokens_used = prompt_tokens + completion_tokens
        
        return ChatResult(
            content=content,
            tokens_used=tokens_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    
    async def health_check(self) -> HealthResult:
        """Check if Ollama and model are ready."""
        if self._client is None:
            return HealthResult(
                status="error",
                model_loaded=False,
                error="Client not initialized",
            )
        
        # Check Ollama health
        try:
            response = await self._client.get(
                f"{self._ollama_host}/api/tags",
                timeout=5.0
            )
            response.raise_for_status()
            ollama_ok = True
            error = None
        except Exception as e:
            ollama_ok = False
            error = str(e)
        
        model_loaded = await self._is_model_loaded() if ollama_ok else False
        
        if ollama_ok and model_loaded:
            status = "ok"
        elif ollama_ok:
            status = "degraded"
        else:
            status = "error"
        
        return HealthResult(
            status=status,
            model_loaded=model_loaded,
            error=error,
        )
    
    async def get_model_info(self) -> ModelInfoResult:
        """Get information about the loaded model."""
        parameters = None
        context_length = None
        
        info = await self._get_ollama_model_info()
        if info:
            if "details" in info:
                parameters = info["details"].get("parameter_size")
            if "model_info" in info:
                context_length = info.get("model_info", {}).get("context_length")
        
        return ModelInfoResult(
            parameters=parameters,
            context_length=context_length,
        )

