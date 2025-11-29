"""
Performance and error tracking for LLM calls.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from collections import deque

logger = logging.getLogger(__name__)

@dataclass
class LLMCallRecord:
    """Record of a single LLM call."""
    timestamp: float
    latency_ms: int
    success: bool
    tokens_used: Optional[int] = None
    error: Optional[str] = None


class LLMStats:
    """Tracks LLM call statistics."""
    
    def __init__(self, max_history: int = 1000):
        self._calls: deque[LLMCallRecord] = deque(maxlen=max_history)
        self._total_calls: int = 0
        self._total_failures: int = 0
        self._total_tokens: int = 0
    
    def record_success(self, latency_ms: int, tokens: Optional[int] = None):
        """Record a successful LLM call."""
        record = LLMCallRecord(
            timestamp=time.time(),
            latency_ms=latency_ms,
            success=True,
            tokens_used=tokens,
        )
        self._calls.append(record)
        self._total_calls += 1
        if tokens:
            self._total_tokens += tokens
        
        logger.debug(
            "LLM call success: latency=%dms, tokens=%s",
            latency_ms, tokens
        )
    
    def record_failure(self, latency_ms: int, error: str):
        """Record a failed LLM call."""
        record = LLMCallRecord(
            timestamp=time.time(),
            latency_ms=latency_ms,
            success=False,
            error=error,
        )
        self._calls.append(record)
        self._total_calls += 1
        self._total_failures += 1
        
        logger.warning(
            "LLM call failed: latency=%dms, error=%s",
            latency_ms, error
        )
    
    def get_summary(self) -> dict:
        """Get a summary of LLM call statistics."""
        if not self._calls:
            return {
                "total_calls": 0,
                "total_failures": 0,
                "failure_rate": 0.0,
                "avg_latency_ms": 0,
                "max_latency_ms": 0,
                "min_latency_ms": 0,
                "p95_latency_ms": 0,
                "total_tokens": 0,
                "recent_errors": [],
            }
        
        # Calculate latency stats from recent calls
        latencies = [c.latency_ms for c in self._calls]
        sorted_latencies = sorted(latencies)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)
        
        # P95 latency
        p95_idx = int(len(sorted_latencies) * 0.95)
        p95_latency = sorted_latencies[min(p95_idx, len(sorted_latencies) - 1)]
        
        # Recent errors (last 5)
        recent_errors = [
            {"timestamp": c.timestamp, "error": c.error, "latency_ms": c.latency_ms}
            for c in reversed(list(self._calls))
            if not c.success
        ][:5]
        
        # Failure rate
        failure_rate = (self._total_failures / self._total_calls * 100) if self._total_calls > 0 else 0.0
        
        return {
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "failure_rate": round(failure_rate, 2),
            "avg_latency_ms": round(avg_latency),
            "max_latency_ms": max_latency,
            "min_latency_ms": min_latency,
            "p95_latency_ms": p95_latency,
            "total_tokens": self._total_tokens,
            "recent_errors": recent_errors,
        }


# Global stats instance
_llm_stats: Optional[LLMStats] = None


def get_llm_stats() -> LLMStats:
    """Get the global LLM stats tracker."""
    global _llm_stats
    if _llm_stats is None:
        _llm_stats = LLMStats()
    return _llm_stats

