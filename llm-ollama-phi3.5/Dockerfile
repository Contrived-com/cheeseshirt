# LLM Sidecar - Ollama with phi3.5 model baked in (CPU-only)
#
# This is a "fat" image (~2.3GB) with the model pre-downloaded.
# Provides instant cold starts - no model pulling at runtime.
#
# Only rebuild when:
# - Model version changes
# - Base ollama image has security patches
# - Provider code changes significantly
#
# For development/testing, use llm-ollama (smaller, pulls model at runtime).

# =============================================================================
# Stage 1: Pull the model
# =============================================================================
FROM alpine/ollama:latest AS model-puller

# Start ollama, pull model, stop
# Model files end up in /root/.ollama
RUN ollama serve & \
    sleep 5 && \
    ollama pull phi3.5:3.8b-mini-instruct-q4_K_M && \
    sleep 2 && \
    pkill ollama || true

# =============================================================================
# Stage 2: Final image with model included
# =============================================================================
FROM alpine/ollama:latest

# Copy pre-pulled model from stage 1
COPY --from=model-puller /root/.ollama /root/.ollama

# Install Python and pip
RUN apk add --no-cache \
    python3 \
    py3-pip

WORKDIR /app

# Install base dependencies from llm-base
COPY --from=ghcr.io/contrived-com/cheeseshirt-llm-base:latest /app/llm_base /app/llm_base
COPY --from=ghcr.io/contrived-com/cheeseshirt-llm-base:latest /app/requirements.txt /app/requirements-base.txt

# Install Python dependencies
RUN pip install --no-cache-dir --break-system-packages -r requirements-base.txt

# Copy provider implementation (same as llm-ollama)
COPY provider.py .
COPY server.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Environment defaults
ENV OLLAMA_HOST=http://localhost:11434
ENV MODEL_NAME=phi3.5:3.8b-mini-instruct-q4_K_M
ENV PORT=11435
ENV DEFAULT_TEMPERATURE=0.7
ENV DEFAULT_MAX_TOKENS=1024
ENV LOG_LEVEL=info

# Model is baked in, but volume can override if needed
VOLUME /root/.ollama

# Expose both Ollama native port and our wrapper port
EXPOSE 11434 11435

# Health check - shorter start period since model is pre-loaded
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget -q -O- http://localhost:11435/health | grep -q '"status":"ok"' || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

