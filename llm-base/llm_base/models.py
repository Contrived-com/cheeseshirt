"""
Pydantic models conforming to llm-interface.md spec.

These models define the API contract that all LLM sidecars must implement.
"""

from typing import Optional
from pydantic import BaseModel


class Message(BaseModel):
    """A single message in a conversation."""
    role: str  # "system", "user", or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request body for POST /chat."""
    messages: list[Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    json_mode: bool = False


class ChatResponse(BaseModel):
    """Response body for POST /chat."""
    content: str
    model: str
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None


class HealthResponse(BaseModel):
    """Response body for GET /health."""
    status: str  # "ok", "degraded", "error"
    model_name: str
    model_loaded: bool
    error: Optional[str] = None


class ModelInfo(BaseModel):
    """Response body for GET /model."""
    name: str
    provider: str  # "openai", "ollama", "anthropic", etc.
    parameters: Optional[str] = None  # e.g., "3.8B"

