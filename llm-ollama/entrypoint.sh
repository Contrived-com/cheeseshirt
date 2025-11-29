#!/bin/bash
# Entrypoint script for LLM Sidecar (Ollama)
#
# Starts Ollama daemon in background, then runs the Python wrapper

set -e

echo "=== LLM Sidecar (Ollama) starting ==="
echo "Model: ${MODEL_NAME:-phi3.5}"

echo "Starting Ollama daemon..."
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready
echo "Waiting for Ollama to start..."
for i in {1..30}; do
    if curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama is ready"
        break
    fi
    echo "  Attempt $i/30..."
    sleep 1
done

echo "Starting LLM wrapper service on port ${PORT:-11435}..."
exec python3 -m uvicorn server:app --host 0.0.0.0 --port ${PORT:-11435}
