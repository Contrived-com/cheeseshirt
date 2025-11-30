# LLM Sidecar - OpenAI implementation
#
# Extends llm-base with OpenAI client.
# Implements llm-interface.md spec and forwards requests to OpenAI's API.

# Build argument for base image (allows CI to specify exact version)
ARG LLM_BASE_IMAGE=ghcr.io/contrived-com/cheeseshirt-llm-base:latest

FROM ${LLM_BASE_IMAGE}

WORKDIR /app

# Install OpenAI-specific dependencies
COPY requirements.txt ./requirements-openai.txt
RUN pip install --no-cache-dir -r requirements-openai.txt

# Copy provider implementation
COPY provider.py .
COPY server.py .

# Environment defaults
ENV MODEL_NAME=gpt-4o
# OPENAI_API_KEY must be provided at runtime

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:11435/health').raise_for_status()"

CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "11435"]
