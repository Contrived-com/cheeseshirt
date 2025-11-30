"""
LLM Sidecar - OpenAI implementation.

This is the entry point. It creates the FastAPI app using the base framework
and the OpenAI provider implementation.
"""

import os
from llm_base import create_app
from provider import OpenAIProvider

# Create the app with OpenAI provider
app = create_app(
    provider_factory=OpenAIProvider,
    title="LLM Sidecar (OpenAI)",
    description="OpenAI wrapper conforming to llm-interface.md",
)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "11435"))
    uvicorn.run(app, host="0.0.0.0", port=port)
