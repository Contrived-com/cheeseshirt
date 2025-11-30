#!/bin/sh
# Entrypoint script for LLM Sidecar (Ollama with baked-in model)
#
# Starts Ollama daemon in background, then runs the Python wrapper.
# Model is already present - no pulling needed.

set -e

echo "=== LLM Sidecar (Ollama phi3.5) starting ==="
echo "Model: ${MODEL_NAME:-phi3.5:3.8b-mini-instruct-q4_K_M}"

echo "Starting Ollama daemon..."
ollama serve &
OLLAMA_PID=$!

# Wait for Ollama to be ready (should be quick since model is baked in)
echo "Waiting for Ollama to start..."
for i in $(seq 1 30); do
    if wget -q -O- http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "Ollama is ready"
        break
    fi
    echo "  Attempt $i/30..."
    sleep 1
done

echo "Starting LLM wrapper service on port ${PORT:-11435}..."
exec python3 -m uvicorn server:app --host 0.0.0.0 --port ${PORT:-11435}

