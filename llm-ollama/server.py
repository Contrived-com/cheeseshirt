"""
LLM Sidecar Service - Ollama wrapper.

Implements the llm-interface.md spec for local models via Ollama.

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

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from stats import get_stats

# Configuration from environment
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "phi3.5")
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
# Ollama Client
# =============================================================================

class OllamaClient:
    """Async client for Ollama API."""
    
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = httpx.AsyncClient(timeout=120.0)
        self._model_info: Optional[dict] = None
    
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> dict:
        """Send a chat completion request to Ollama."""
        payload = {
            "model": self.model,
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
            f"{self.base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        return response.json()
    
    async def is_healthy(self) -> tuple[bool, Optional[str]]:
        """Check if Ollama is running."""
        try:
            response = await self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            return True, None
        except Exception as e:
            return False, str(e)
    
    async def is_model_loaded(self) -> bool:
        """Check if our model is available."""
        try:
            response = await self._client.get(f"{self.base_url}/api/tags", timeout=5.0)
            response.raise_for_status()
            data = response.json()
            models = [m["name"] for m in data.get("models", [])]
            return self.model in models or f"{self.model}:latest" in models
        except Exception:
            return False
    
    async def pull_model(self) -> bool:
        """Pull the model if not already available."""
        logger.info("Pulling model %s...", self.model)
        try:
            response = await self._client.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model, "stream": False},
                timeout=600.0,
            )
            response.raise_for_status()
            logger.info("Model %s pulled successfully", self.model)
            return True
        except Exception as e:
            logger.error("Failed to pull model %s: %s", self.model, e)
            return False
    
    async def get_model_info(self) -> Optional[dict]:
        """Get information about the loaded model."""
        if self._model_info:
            return self._model_info
        try:
            response = await self._client.post(
                f"{self.base_url}/api/show",
                json={"name": self.model},
                timeout=10.0,
            )
            response.raise_for_status()
            self._model_info = response.json()
            return self._model_info
        except Exception:
            return None


# =============================================================================
# Application
# =============================================================================

ollama: Optional[OllamaClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    global ollama
    
    logger.info("LLM Sidecar (Ollama) starting up")
    logger.info("Ollama host: %s", OLLAMA_HOST)
    logger.info("Model: %s", MODEL_NAME)
    
    ollama = OllamaClient(OLLAMA_HOST, MODEL_NAME)
    
    # Wait for Ollama to be ready
    import asyncio
    for attempt in range(30):
        ok, error = await ollama.is_healthy()
        if ok:
            logger.info("Ollama is healthy")
            break
        logger.info("Waiting for Ollama... (attempt %d)", attempt + 1)
        await asyncio.sleep(1)
    else:
        logger.error("Ollama not available after 30 seconds")
    
    # Check if model is loaded, pull if not
    if not await ollama.is_model_loaded():
        logger.info("Model not found, pulling...")
        await ollama.pull_model()
    
    yield
    
    logger.info("LLM Sidecar (Ollama) shutting down")


app = FastAPI(
    title="LLM Sidecar (Ollama)",
    description="Ollama wrapper conforming to llm-interface.md",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    if ollama is None:
        return HealthResponse(
            status="error",
            model_name=MODEL_NAME,
            model_loaded=False,
            error="Client not initialized",
        )
    
    ollama_ok, error = await ollama.is_healthy()
    model_loaded = await ollama.is_model_loaded() if ollama_ok else False
    
    if ollama_ok and model_loaded:
        status = "ok"
    elif ollama_ok:
        status = "degraded"
    else:
        status = "error"
    
    return HealthResponse(
        status=status,
        model_name=MODEL_NAME,
        model_loaded=model_loaded,
        error=error,
    )


@app.get("/model", response_model=ModelInfo)
async def model_info():
    """Get information about the loaded model."""
    parameters = None
    if ollama:
        info = await ollama.get_model_info()
        if info and "details" in info:
            parameters = info["details"].get("parameter_size")
    
    return ModelInfo(
        name=MODEL_NAME,
        provider="ollama",
        parameters=parameters,
    )


@app.get("/stats")
async def stats_endpoint():
    """Get detailed statistics."""
    s = get_stats()
    
    # Try to get context length from model info
    context_length = None
    if ollama:
        info = await ollama.get_model_info()
        if info and "model_info" in info:
            # Ollama returns context length in model_info
            context_length = info.get("model_info", {}).get("context_length")
    
    return s.get_stats(
        model_name=MODEL_NAME,
        provider="ollama",
        context_length=context_length,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat completion endpoint."""
    if ollama is None:
        raise HTTPException(status_code=503, detail="Ollama client not initialized")
    
    start_time = time.time()
    stats = get_stats()
    
    # Convert to Ollama format
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    temperature = request.temperature if request.temperature is not None else DEFAULT_TEMPERATURE
    max_tokens = request.max_tokens if request.max_tokens is not None else DEFAULT_MAX_TOKENS
    
    logger.debug(
        "Chat request: messages=%d, temp=%.2f, max_tokens=%d, json_mode=%s",
        len(messages), temperature, max_tokens, request.json_mode
    )
    
    try:
        result = await ollama.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=request.json_mode,
        )
        
        latency_ms = int((time.time() - start_time) * 1000)
        content = result.get("message", {}).get("content", "")
        
        # Extract token counts
        tokens_used = None
        prompt_tokens = None
        completion_tokens = None
        if "prompt_eval_count" in result or "eval_count" in result:
            prompt_tokens = result.get("prompt_eval_count", 0)
            completion_tokens = result.get("eval_count", 0)
            tokens_used = prompt_tokens + completion_tokens
        
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
        
    except httpx.HTTPStatusError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        stats.record_request(success=False, latency_ms=latency_ms)
        logger.error("Ollama error: %s", e)
        raise HTTPException(status_code=502, detail=f"Ollama error: {e}")
    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        stats.record_request(success=False, latency_ms=latency_ms)
        logger.error("Chat error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "11435"))
    uvicorn.run(app, host="0.0.0.0", port=port)
