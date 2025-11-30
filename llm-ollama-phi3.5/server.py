"""
LLM Sidecar - Ollama with phi3.5 baked in.

This is the entry point. It creates the FastAPI app using the base framework
and the Ollama provider implementation.
"""

import os
from llm_base import create_app
from provider import OllamaProvider

# Create the app with Ollama provider
app = create_app(
    provider_factory=OllamaProvider,
    title="LLM Sidecar (Ollama phi3.5)",
    description="Ollama with phi3.5 model baked in, conforming to llm-interface.md",
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "11435"))
    uvicorn.run(app, host="0.0.0.0", port=port)

