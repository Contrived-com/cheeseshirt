"""
FastAPI application factory for LLM sidecars.

Creates a standardized FastAPI app with all endpoints from llm-interface.md.
Implementations just need to provide an LLMProvider instance.
"""

import os
import time
import logging
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, HTTPException

from .models import ChatRequest, ChatResponse, HealthResponse, ModelInfo
from .provider import LLMProvider
from .stats import get_stats


# Environment config
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "1024"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("llm-base")


def create_app(
    provider_factory: Callable[[], LLMProvider],
    title: str = "LLM Sidecar",
    description: str = "LLM sidecar conforming to llm-interface.md",
    version: str = "1.0.0",
) -> FastAPI:
    """
    Create a FastAPI application for an LLM sidecar.
    
    Args:
        provider_factory: Callable that creates the LLMProvider instance.
                         Called during app startup.
        title: OpenAPI title
        description: OpenAPI description  
        version: OpenAPI version
        
    Returns:
        Configured FastAPI application
        
    Example:
        ```python
        from llm_base import create_app, LLMProvider
        
        class MyProvider(LLMProvider):
            # ... implement abstract methods ...
        
        app = create_app(lambda: MyProvider())
        ```
    """
    
    # Provider instance, set during startup
    provider: LLMProvider | None = None
    
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal provider
        
        logger.info("LLM Sidecar starting up")
        
        # Create and initialize provider
        provider = provider_factory()
        logger.info("Provider: %s", provider.provider_name)
        logger.info("Model: %s", provider.model_name)
        
        await provider.initialize()
        logger.info("Provider initialized")
        
        yield
        
        logger.info("LLM Sidecar shutting down")
        if provider:
            await provider.shutdown()
    
    app = FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=lifespan,
    )
    
    @app.get("/health", response_model=HealthResponse)
    async def health():
        """Health check endpoint."""
        if provider is None:
            return HealthResponse(
                status="error",
                model_name="unknown",
                model_loaded=False,
                error="Provider not initialized",
            )
        
        result = await provider.health_check()
        return HealthResponse(
            status=result.status,
            model_name=provider.model_name,
            model_loaded=result.model_loaded,
            error=result.error,
        )
    
    @app.get("/model", response_model=ModelInfo)
    async def model_info():
        """Get information about the loaded model."""
        if provider is None:
            return ModelInfo(
                name="unknown",
                provider="unknown",
                parameters=None,
            )
        
        result = await provider.get_model_info()
        return ModelInfo(
            name=provider.model_name,
            provider=provider.provider_name,
            parameters=result.parameters,
        )
    
    @app.get("/stats")
    async def stats_endpoint():
        """Get detailed statistics."""
        if provider is None:
            return {"error": "Provider not initialized"}
        
        info = await provider.get_model_info()
        s = get_stats()
        return s.get_stats(
            model_name=provider.model_name,
            provider=provider.provider_name,
            context_length=info.context_length,
        )
    
    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest):
        """Chat completion endpoint."""
        if provider is None:
            raise HTTPException(status_code=503, detail="Provider not initialized")
        
        start_time = time.time()
        stats = get_stats()
        
        # Convert Pydantic models to dicts
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        
        temperature = request.temperature if request.temperature is not None else DEFAULT_TEMPERATURE
        max_tokens = request.max_tokens if request.max_tokens is not None else DEFAULT_MAX_TOKENS
        
        logger.debug(
            "Chat request: messages=%d, temp=%.2f, max_tokens=%d, json_mode=%s",
            len(messages), temperature, max_tokens, request.json_mode
        )
        
        try:
            result = await provider.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=request.json_mode,
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Record stats
            stats.record_request(
                success=True,
                latency_ms=latency_ms,
                tokens_used=result.tokens_used,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
            )
            
            logger.debug("Chat response: latency=%dms, tokens=%s", latency_ms, result.tokens_used)
            
            return ChatResponse(
                content=result.content,
                model=provider.model_name,
                tokens_used=result.tokens_used,
                latency_ms=latency_ms,
            )
            
        except HTTPException:
            raise
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            stats.record_request(success=False, latency_ms=latency_ms)
            logger.error("Chat error: %s", e, exc_info=True)
            raise HTTPException(status_code=502, detail=f"{provider.provider_name} error: {e}")
    
    return app

