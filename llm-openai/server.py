"""
LLM Sidecar Service - OpenAI wrapper.

Implements the llm-interface.md spec so it can be swapped with llm-ollama seamlessly.

Endpoints:
  POST /chat     - Send messages, get response
  GET  /health   - Health check
  GET  /model    - Get model information
  GET  /stats    - Detailed statistics
"""
import os
import time
import logging
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import AsyncOpenAI

from stats import get_stats

# Configuration from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
DEFAULT_TEMPERATURE = float(os.getenv("DEFAULT_TEMPERATURE", "0.7"))
DEFAULT_MAX_TOKENS = int(os.getenv("DEFAULT_MAX_TOKENS", "1024"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# =============================================================================
# Models (conforming to llm-interface.md)
# =============================================================================

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    json_mode: bool = False


class ChatResponse(BaseModel):
    content: str
    model: str
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None


class HealthResponse(BaseModel):
    status: str  # "ok", "degraded", "error"
    model_name: str
    model_loaded: bool
    error: Optional[str] = None


class ModelInfo(BaseModel):
    name: str
    provider: str
    parameters: Optional[str] = None


# =============================================================================
# Application
# =============================================================================

client: Optional[AsyncOpenAI] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    global client
    
    logger.info("LLM Sidecar (OpenAI) starting up")
    logger.info("Model: %s", MODEL_NAME)
    
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set!")
    else:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        logger.info("OpenAI client initialized")
    
    yield
    
    logger.info("LLM Sidecar (OpenAI) shutting down")


app = FastAPI(
    title="LLM Sidecar (OpenAI)",
    description="OpenAI wrapper conforming to llm-interface.md",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    if client is None:
        return HealthResponse(
            status="error",
            model_name=MODEL_NAME,
            model_loaded=False,
            error="OPENAI_API_KEY not configured",
        )
    
    # For cloud API, we assume it's available if client is configured
    # Don't make an API call on every health check
    return HealthResponse(
        status="ok",
        model_name=MODEL_NAME,
        model_loaded=True,
    )


@app.get("/model", response_model=ModelInfo)
async def model_info():
    """Get information about the configured model."""
    return ModelInfo(
        name=MODEL_NAME,
        provider="openai",
        parameters=None,  # OpenAI doesn't expose this
    )


@app.get("/stats")
async def stats():
    """Get detailed statistics."""
    s = get_stats()
    return s.get_stats(
        model_name=MODEL_NAME,
        provider="openai",
        context_length=None,  # Varies by model, not exposing
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat completion endpoint."""
    if client is None:
        raise HTTPException(status_code=503, detail="OpenAI client not initialized")
    
    start_time = time.time()
    stats = get_stats()
    
    # Convert to OpenAI format
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    temperature = request.temperature if request.temperature is not None else DEFAULT_TEMPERATURE
    max_tokens = request.max_tokens if request.max_tokens is not None else DEFAULT_MAX_TOKENS
    
    logger.debug(
        "Chat request: messages=%d, temp=%.2f, max_tokens=%d, json_mode=%s",
        len(messages), temperature, max_tokens, request.json_mode
    )
    
    try:
        params = {
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if request.json_mode:
            params["response_format"] = {"type": "json_object"}
        
        completion = await client.chat.completions.create(**params)
        
        latency_ms = int((time.time() - start_time) * 1000)
        content = completion.choices[0].message.content or ""
        
        # Extract token counts
        tokens_used = None
        prompt_tokens = None
        completion_tokens = None
        if completion.usage:
            tokens_used = completion.usage.total_tokens
            prompt_tokens = completion.usage.prompt_tokens
            completion_tokens = completion.usage.completion_tokens
        
        # Record stats
        stats.record_request(
            success=True,
            latency_ms=latency_ms,
            tokens_used=tokens_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        
        logger.debug("Chat response: latency=%dms, tokens=%s", latency_ms, tokens_used)
        
        return ChatResponse(
            content=content,
            model=MODEL_NAME,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
        
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        stats.record_request(success=False, latency_ms=latency_ms)
        logger.error("OpenAI error: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "11435"))
    uvicorn.run(app, host="0.0.0.0", port=port)
