"""
Observability and Metrics Collector (Phase 5 Monitoring).
Tracks pipeline stage latency, request counts, and LLM call/fallback performance.
"""
import time
import threading
from typing import Dict, Any, List
from datetime import datetime, timezone

START_TIME = time.time()
START_DATETIME = datetime.now(timezone.utc)


class MetricsCollector:
    """
    Thread-safe in-memory performance and reliability metrics tracker.
    """
    def __init__(self):
        self._lock = threading.Lock()
        
        # LLM Call Statistics
        self.llm_total_calls = 0
        self.llm_successful_calls = 0
        self.llm_fallback_calls = 0
        self.llm_total_latency_ms = 0.0
        
        # Pipeline Timings (rolling records)
        self.recent_pipeline_timings: List[Dict[str, float]] = []
        self.max_timing_history = 100
        
        # HTTP Request Statistics
        self.total_http_requests = 0
        self.total_http_errors = 0

    def record_llm_call(self, success: bool, fallback_triggered: bool, duration_ms: float) -> None:
        """Record the outcome and latency of an LLM generation attempt."""
        with self._lock:
            self.llm_total_calls += 1
            if success:
                self.llm_successful_calls += 1
            if fallback_triggered:
                self.llm_fallback_calls += 1
            self.llm_total_latency_ms += duration_ms

    def record_pipeline_timing(self, timings: Dict[str, float]) -> None:
        """Record per-stage pipeline execution timings (in milliseconds)."""
        with self._lock:
            self.recent_pipeline_timings.append(timings)
            if len(self.recent_pipeline_timings) > self.max_timing_history:
                self.recent_pipeline_timings.pop(0)

    def record_http_request(self, status_code: int) -> None:
        """Record high-level HTTP request stats."""
        with self._lock:
            self.total_http_requests += 1
            if status_code >= 500:
                self.total_http_errors += 1

    def get_llm_summary(self) -> Dict[str, Any]:
        """Return aggregated LLM success and fallback metrics."""
        with self._lock:
            total = self.llm_total_calls
            success = self.llm_successful_calls
            fallbacks = self.llm_fallback_calls
            avg_latency = (self.llm_total_latency_ms / total) if total > 0 else 0.0
            fallback_rate = (fallbacks / total * 100.0) if total > 0 else 0.0
            success_rate = (success / total * 100.0) if total > 0 else 100.0

            return {
                "total_calls": total,
                "successful_calls": success,
                "fallback_triggers": fallbacks,
                "success_rate_pct": round(success_rate, 2),
                "fallback_rate_pct": round(fallback_rate, 2),
                "avg_latency_ms": round(avg_latency, 2)
            }

    def get_pipeline_timing_summary(self) -> Dict[str, Any]:
        """Return average execution times per pipeline stage across recent scans."""
        with self._lock:
            if not self.recent_pipeline_timings:
                return {
                    "sample_count": 0,
                    "avg_detect_ms": 0.0,
                    "avg_quality_gate_ms": 0.0,
                    "avg_geometry_ms": 0.0,
                    "avg_skin_ms": 0.0,
                    "avg_rules_ms": 0.0,
                    "avg_llm_ms": 0.0,
                    "avg_total_ms": 0.0,
                }

            n = len(self.recent_pipeline_timings)
            keys = ["detect_ms", "quality_gate_ms", "geometry_ms", "skin_ms", "rules_ms", "llm_ms", "total_ms"]
            avg_dict = {"sample_count": n}
            for k in keys:
                avg_dict[f"avg_{k}"] = round(sum(t.get(k, 0.0) for t in self.recent_pipeline_timings) / n, 2)
            return avg_dict

    def get_system_health(self) -> Dict[str, Any]:
        """Return system uptime and operational summary."""
        uptime_seconds = int(time.time() - START_TIME)
        return {
            "uptime_seconds": uptime_seconds,
            "started_at": START_DATETIME.isoformat(),
            "total_requests": self.total_http_requests,
            "server_errors_5xx": self.total_http_errors,
        }

    def reset(self) -> None:
        """Reset metrics (useful for isolated tests)."""
        with self._lock:
            self.llm_total_calls = 0
            self.llm_successful_calls = 0
            self.llm_fallback_calls = 0
            self.llm_total_latency_ms = 0.0
            self.recent_pipeline_timings.clear()
            self.total_http_requests = 0
            self.total_http_errors = 0


# Global metrics instance
metrics = MetricsCollector()
