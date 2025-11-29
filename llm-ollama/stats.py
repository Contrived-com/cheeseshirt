"""
Shared statistics tracking for LLM sidecars.

Copy this file into your sidecar to get consistent stats tracking
that conforms to the llm-interface.md spec.
"""
import os
import time
import statistics
from dataclasses import dataclass, field
from typing import Optional
from collections import deque


@dataclass
class LLMStats:
    """
    Track statistics for LLM sidecar diagnostics.
    
    Thread-safe for single-writer scenarios (one request at a time).
    For concurrent requests, wrap record_* calls in a lock.
    """
    
    # Config
    latency_window: int = 1000  # Keep last N latencies for percentiles
    
    # Timestamps
    start_time: float = field(default_factory=time.time)
    
    # Request counts
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    
    # Latency tracking
    latencies: deque = field(default_factory=lambda: deque(maxlen=1000))
    min_latency_ms: Optional[float] = None
    max_latency_ms: Optional[float] = None  # High watermark
    
    # Token tracking
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    
    def record_request(
        self,
        success: bool,
        latency_ms: float,
        tokens_used: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
    ):
        """Record a completed request."""
        self.total_requests += 1
        
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        # Latency
        self.latencies.append(latency_ms)
        if self.min_latency_ms is None or latency_ms < self.min_latency_ms:
            self.min_latency_ms = latency_ms
        if self.max_latency_ms is None or latency_ms > self.max_latency_ms:
            self.max_latency_ms = latency_ms
        
        # Tokens
        if tokens_used is not None:
            self.total_tokens += tokens_used
        if prompt_tokens is not None:
            self.prompt_tokens += prompt_tokens
        if completion_tokens is not None:
            self.completion_tokens += completion_tokens
    
    def get_percentile(self, p: float) -> Optional[float]:
        """Get latency percentile (0-100)."""
        if not self.latencies:
            return None
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * p / 100)
        idx = min(idx, len(sorted_latencies) - 1)
        return sorted_latencies[idx]
    
    def get_memory_mb(self) -> dict:
        """Get current memory usage."""
        try:
            import resource
            # RSS in bytes, convert to MB
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            # On Linux it's KB, on macOS it's bytes
            if os.uname().sysname == "Darwin":
                rss_mb = rss / (1024 * 1024)
            else:
                rss_mb = rss / 1024
            return {"rss_mb": round(rss_mb, 1), "model_mb": None}
        except Exception:
            return {"rss_mb": None, "model_mb": None}
    
    def get_stats(self, model_name: str, provider: str, context_length: Optional[int] = None) -> dict:
        """
        Get full stats conforming to llm-interface.md spec.
        """
        uptime = time.time() - self.start_time
        
        # Calculate latency stats
        latency_stats = {
            "avg": None,
            "min": self.min_latency_ms,
            "max": self.max_latency_ms,
            "p50": None,
            "p95": None,
            "p99": None,
        }
        
        if self.latencies:
            latency_stats["avg"] = round(statistics.mean(self.latencies), 1)
            latency_stats["p50"] = round(self.get_percentile(50), 1)
            latency_stats["p95"] = round(self.get_percentile(95), 1)
            latency_stats["p99"] = round(self.get_percentile(99), 1)
            if self.min_latency_ms:
                latency_stats["min"] = round(self.min_latency_ms, 1)
            if self.max_latency_ms:
                latency_stats["max"] = round(self.max_latency_ms, 1)
        
        return {
            "uptime_seconds": round(uptime, 1),
            
            "requests": {
                "total": self.total_requests,
                "success": self.success_count,
                "failure": self.failure_count,
            },
            
            "latency_ms": latency_stats,
            
            "tokens": {
                "total": self.total_tokens,
                "prompt": self.prompt_tokens,
                "completion": self.completion_tokens,
            },
            
            "memory": self.get_memory_mb(),
            
            "model": {
                "name": model_name,
                "provider": provider,
                "context_length": context_length,
            },
        }


# Singleton instance
_stats: Optional[LLMStats] = None


def get_stats() -> LLMStats:
    """Get the global stats instance."""
    global _stats
    if _stats is None:
        _stats = LLMStats()
    return _stats

