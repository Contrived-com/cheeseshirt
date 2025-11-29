# LLM Sidecar Interface Specification

Any LLM sidecar (llm-openai, llm-ollama, future implementations) must implement this interface.

## Endpoints

### `POST /chat`
Main chat completion endpoint.

**Request:**
```json
{
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "temperature": 0.7,        // optional, default varies by impl
  "max_tokens": 1024,        // optional, default varies by impl
  "json_mode": false         // optional, request JSON output
}
```

**Response:**
```json
{
  "content": "...",
  "model": "gpt-4o",
  "tokens_used": 150,        // optional
  "latency_ms": 832          // optional
}
```

**Errors:** Return HTTP 5xx with `{"detail": "error message"}`

---

### `GET /health`
Health check - is the sidecar ready to serve requests?

**Response:**
```json
{
  "status": "ok",            // "ok", "degraded", "error"
  "model_name": "gpt-4o",
  "model_loaded": true,      // is model ready?
  "error": null              // error message if status != "ok"
}
```

---

### `GET /model`
Information about the loaded model.

**Response:**
```json
{
  "name": "gpt-4o",
  "provider": "openai",      // "openai", "ollama", etc.
  "parameters": "unknown"    // model size if known (e.g., "3.8B")
}
```

---

### `GET /stats`
Detailed statistics for diagnostics and monitoring.

**Response:**
```json
{
  "uptime_seconds": 3600,
  
  "requests": {
    "total": 1000,
    "success": 985,
    "failure": 15
  },
  
  "latency_ms": {
    "avg": 450,
    "min": 120,
    "max": 2500,             // high watermark
    "p50": 400,
    "p95": 1200,
    "p99": 2000
  },
  
  "tokens": {
    "total": 150000,
    "prompt": 100000,
    "completion": 50000
  },
  
  "memory": {
    "rss_mb": 512,           // resident set size
    "model_mb": 2048         // model memory (if known, null otherwise)
  },
  
  "model": {
    "name": "phi3.5",
    "provider": "ollama",
    "context_length": 4096
  }
}
```

---

## Implementation Requirements

1. **Stateless**: Each `/chat` request is independent. No session tracking.

2. **Port**: Default to `11435` (configurable via `PORT` env var).

3. **Timeouts**: Handle long inference gracefully. Recommend 120s timeout.

4. **Health checks**: `/health` should return quickly (<1s). Don't do inference.

5. **Graceful degradation**: If model isn't loaded yet, return `status: "degraded"` not 500.

6. **Memory tracking**: For local models, track actual memory usage. For cloud APIs, report process RSS only.

---

## Environment Variables (Common)

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `11435` | HTTP port |
| `MODEL_NAME` | varies | Model to use |
| `DEFAULT_TEMPERATURE` | `0.7` | Default temperature |
| `DEFAULT_MAX_TOKENS` | `1024` | Default max tokens |
| `LOG_LEVEL` | `info` | Logging level |

---

## Adding a New Sidecar

To add a new LLM backend (e.g., `llm-anthropic`):

1. Create `llm-anthropic/` directory
2. Implement all 4 endpoints above
3. Add Dockerfile exposing port 11435
4. Add to docker-compose.yml as an alternative `llm:` service

The Monger will work with it automatically - no changes needed.

