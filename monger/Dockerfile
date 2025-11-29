# Monger Service - Python LLM service
# Handles all LLM interactions for the Monger character

FROM python:3.12-slim

WORKDIR /app

# Install dependencies
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
ENV LLM_PROVIDER=openai
ENV CHARACTER_CONFIG_PATH=/app/config/monger.json

# Expose the service port
EXPOSE 3002

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:3002/health').raise_for_status()"

# Run the service
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "3002"]
