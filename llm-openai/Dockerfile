# LLM Sidecar - OpenAI wrapper
#
# Implements llm-interface.md spec and forwards requests to OpenAI's API.
# Same interface as llm-ollama so they're interchangeable.

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY stats.py .
COPY server.py .

# Environment defaults
ENV MODEL_NAME=gpt-4o
ENV PORT=11435
ENV DEFAULT_TEMPERATURE=0.7
ENV DEFAULT_MAX_TOKENS=1024
ENV LOG_LEVEL=info
# OPENAI_API_KEY must be provided at runtime

EXPOSE 11435

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:11435/health').raise_for_status()"

CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "11435"]
