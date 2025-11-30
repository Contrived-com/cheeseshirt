"""
LLM Base - Abstract interface for LLM sidecar implementations.

This package provides the common infrastructure for all LLM sidecars:
- Abstract LLMProvider interface
- Shared Pydantic models
- Statistics tracking
- FastAPI app factory with standard endpoints

Implementations only need to subclass LLMProvider and implement the abstract methods.
"""

from .models import Message, ChatRequest, ChatResponse, HealthResponse, ModelInfo
from .provider import LLMProvider, ChatResult, HealthResult, ModelInfoResult
from .stats import LLMStats, get_stats
from .server import create_app

__all__ = [
    # API models
    "Message",
    "ChatRequest", 
    "ChatResponse",
    "HealthResponse",
    "ModelInfo",
    # Provider interface
    "LLMProvider",
    "ChatResult",
    "HealthResult", 
    "ModelInfoResult",
    # Stats
    "LLMStats",
    "get_stats",
    # App factory
    "create_app",
]

