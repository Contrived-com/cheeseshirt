# LLM Sidecar - Ollama wrapper
#
# Implements llm-interface.md spec for local models via Ollama.
# Same interface as llm-openai so they're interchangeable.
#
# This container runs both Ollama and a thin Python wrapper.

FROM ollama/ollama:latest

# Install Python for the wrapper service
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create and activate virtual environment
RUN python3 -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy wrapper service
COPY stats.py .
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

# Ollama stores models here
VOLUME /root/.ollama

# Expose both Ollama native port and our wrapper port
EXPOSE 11434 11435

# Health check against our wrapper
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -sf http://localhost:11435/health | grep -q '"status":"ok"' || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
