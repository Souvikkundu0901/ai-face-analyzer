"""
Monitoring and observability tests for Phase 5:
- Structured Request ID headers (X-Request-ID)
- Comprehensive /health check probes (database, detector, model, metrics)
- Pipeline stage timing collection
- LLM metrics tracking (total calls, fallback rates, latencies)
"""
import io
import pytest
from starlette.testclient import TestClient
from PIL import Image

from app.main import app
from app.monitoring.metrics import metrics
from app.db.session import Base, engine


@pytest.fixture(autouse=True)
def setup_monitoring():
    Base.metadata.create_all(bind=engine)
    metrics.reset()
    yield
    metrics.reset()


@pytest.fixture
def client():
    return TestClient(app)


def make_test_face_jpeg():
    """Generates a small valid test JPEG."""
    img = Image.new("RGB", (200, 200), color=(220, 180, 150))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


class TestMonitoringAndHealth:
    def test_request_id_header_injected(self, client):
        """Every HTTP request must return an X-Request-ID header."""
        res = client.get("/health")
        assert res.status_code == 200
        assert "X-Request-ID" in res.headers
        assert len(res.headers["X-Request-ID"]) > 0

    def test_health_check_structure(self, client):
        """Health check returns comprehensive diagnostic data."""
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] in ("ok", "degraded")
        assert data["database"] == "connected"
        assert "detector" in data
        assert "system" in data
        assert "uptime_seconds" in data["system"]
        assert "pipeline_performance" in data
        assert "llm_performance" in data

    def test_pipeline_timing_metrics_recorded(self, client):
        """Pipeline execution records per-stage timing metrics."""
        # Read a real sample image from tests
        from pathlib import Path
        sample_path = Path(__file__).parent / "sample_images" / "good_lighting" / "sample1.jpg"
        if sample_path.exists():
            with open(sample_path, "rb") as f:
                img_bytes = f.read()
            res = client.post(
                "/api/analyze",
                files={"image": ("sample1.jpg", io.BytesIO(img_bytes), "image/jpeg")}
            )
            assert res.status_code == 200
            
            perf = metrics.get_pipeline_timing_summary()
            assert perf["sample_count"] >= 1
            assert perf["avg_detect_ms"] > 0
            assert perf["avg_total_ms"] > 0

    def test_llm_metrics_tracking(self):
        """LLM metrics collector accurately calculates rates and latencies."""
        metrics.record_llm_call(success=True, fallback_triggered=False, duration_ms=150.0)
        metrics.record_llm_call(success=True, fallback_triggered=False, duration_ms=250.0)
        metrics.record_llm_call(success=False, fallback_triggered=True, duration_ms=50.0)

        summary = metrics.get_llm_summary()
        assert summary["total_calls"] == 3
        assert summary["successful_calls"] == 2
        assert summary["fallback_triggers"] == 1
        assert summary["fallback_rate_pct"] == 33.33
        assert summary["avg_latency_ms"] == 150.0
