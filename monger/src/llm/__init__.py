"""
LLM client for talking to the sidecar service.

The Monger doesn't care what LLM is behind the sidecar -
it just sends messages and gets responses via HTTP.
"""
from .client import LLMClient, LLMMessage, LLMResponse, get_llm_client

__all__ = ["LLMClient", "LLMMessage", "LLMResponse", "get_llm_client"]
