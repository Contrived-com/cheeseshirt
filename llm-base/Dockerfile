# LLM Base - Abstract base image for LLM sidecars
#
# This image provides:
# - Python 3.12 runtime
# - FastAPI + uvicorn
# - Shared LLM interface code (llm_base package)
#
# Implementations extend this image and add their provider-specific code.

FROM python:3.12-slim

WORKDIR /app

# Install base dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install the llm_base package
COPY llm_base/ /app/llm_base/

# Environment defaults (can be overridden by implementations)
ENV PORT=11435
ENV DEFAULT_TEMPERATURE=0.7
ENV DEFAULT_MAX_TOKENS=1024
ENV LOG_LEVEL=info

EXPOSE 11435

# Base image doesn't run anything by itself
# Implementations provide their own CMD

