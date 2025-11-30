# Monger Service - Character logic for the Monger
#
# This service handles the Monger's personality, conversation state,
# and character logic. It talks to an LLM sidecar (llm-openai, llm-ollama)
# via HTTP, so it doesn't need any LLM dependencies itself.
#
# This keeps the image small and allows updating the character
# without re-downloading large LLM images.

FROM python:3.12-slim

WORKDIR /app

# Install dependencies (no LLM libs needed - that's the sidecar's job)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/

# Create non-root user (UID 1002 to match host cheeseshirt user)
RUN groupadd -g 1002 monger && \
    useradd -u 1002 -g monger -s /bin/bash monger

# Create logs directory
RUN mkdir -p /app/logs && chown -R monger:monger /app/logs

USER monger

# Environment defaults
ENV HOST=0.0.0.0
ENV PORT=3002
ENV LOG_LEVEL=info
ENV CHARACTER_CONFIG_PATH=/app/config/monger.json
ENV REFERRALS_PATH=/app/config/referrals.json
ENV LLM_SERVICE_URL=http://llm:11435
ENV LLM_SERVICE_TIMEOUT=120.0

# Expose the service port
EXPOSE 3002

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:3002/health').raise_for_status()"

# Run the service
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3002"]
