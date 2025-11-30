# LLM Sidecar - Ollama implementation (CPU-only, runtime model pull)
#
# Uses alpine/ollama for minimal CPU-only image (~22MB base).
# Model is pulled at runtime on first startup.
# For pre-baked model, see llm-ollama-phi3.5/Dockerfile.

FROM alpine/ollama:latest

# Install Python and pip
# Note: alpine/ollama uses wolfi-base which has apk
RUN apk add --no-cache \
    python3 \
    py3-pip

WORKDIR /app

# Install base dependencies
COPY --from=ghcr.io/contrived-com/cheeseshirt-llm-base:latest /app/llm_base /app/llm_base
COPY --from=ghcr.io/contrived-com/cheeseshirt-llm-base:latest /app/requirements.txt /app/requirements-base.txt

# Install Python dependencies
# Using --break-system-packages because we're in a container
RUN pip install --no-cache-dir --break-system-packages -r requirements-base.txt

# Copy provider implementation
COPY provider.py .
COPY server.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Environment defaults
ENV OLLAMA_HOST=http://localhost:11434
ENV MODEL_NAME=phi3.5
ENV PORT=11435
ENV DEFAULT_TEMPERATURE=0.7
ENV DEFAULT_MAX_TOKENS=1024
ENV LOG_LEVEL=info

# Ollama stores models here - mount a volume for persistence
VOLUME /root/.ollama

# Expose both Ollama native port and our wrapper port
EXPOSE 11434 11435

# Health check against our wrapper
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD wget -q -O- http://localhost:11435/health | grep -q '"status":"ok"' || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
