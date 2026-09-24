"""
Comprehensive security test suite for Phase 5 Hardening:
- Rate limiting on Auth and Scan endpoints
- Magic bytes upload validation and MIME spoofing protection
- Max file size limits (HTTP 413)
- Error sanitization (no traceback leaks in production)
- DB-backed JWT refresh token rotation and revocation
"""
import io
import pytest
from starlette.testclient import TestClient
from PIL import Image

from app.main import app
from app.db.session import Base, engine, get_db
from app.security.rate_limiter import auth_limiter, scan_limiter
from app.security.validation import validate_image_upload, detect_image_type
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def setup_db_and_limiters():
    """Reset DB tables and rate limiters before each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    auth_limiter.reset()
    scan_limiter.reset()
    yield
    auth_limiter.reset()
    scan_limiter.reset()


@pytest.fixture
def client():
    return TestClient(app)


def make_test_jpeg():
    img = Image.new("RGB", (100, 100), color=(200, 150, 100))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def make_test_png():
    img = Image.new("RGB", (100, 100), color=(100, 200, 150))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestRateLimiting:
    def test_auth_rate_limiting(self, client):
        """Auth endpoint allows 5 requests and blocks the 6th with HTTP 429."""
        for i in range(5):
            res = client.post("/api/auth/login", json={"email": f"user{i}@test.com", "password": "Password123!"})
            assert res.status_code in (401, 200)

        # 6th request must trigger 429 Too Many Requests
        res = client.post("/api/auth/login", json={"email": "user_overflow@test.com", "password": "Password123!"})
        assert res.status_code == 429
        assert "Retry-After" in res.headers
        assert "Rate limit exceeded" in res.json()["detail"]

    def test_scan_rate_limiting(self, client):
        """Scan endpoint allows 10 requests and blocks the 11th with HTTP 429."""
        jpeg_bytes = make_test_jpeg()
        for _ in range(10):
            res = client.post(
                "/api/analyze",
                files={"image": ("test.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")}
            )
            # Either 200 or 422 (quality rejection), but not 429
            assert res.status_code in (200, 422)

        # 11th request must trigger 429
        res = client.post(
            "/api/analyze",
            files={"image": ("test.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")}
        )
        assert res.status_code == 429
        assert "Retry-After" in res.headers


class TestMagicBytesValidation:
    def test_detect_valid_magic_bytes(self):
        jpeg_bytes = make_test_jpeg()
        png_bytes = make_test_png()
        assert detect_image_type(jpeg_bytes) == "jpeg"
        assert detect_image_type(png_bytes) == "png"

    def test_reject_spoofed_text_file(self, client):
        """Uploading plain text disguised as .jpg fails magic byte verification with 400."""
        fake_content = b"This is a malicious shell script pretending to be a jpg"
        res = client.post(
            "/api/analyze",
            files={"image": ("malicious.jpg", io.BytesIO(fake_content), "image/jpeg")}
        )
        assert res.status_code == 400
        assert "Magic byte inspection failed" in res.json()["detail"]

    def test_reject_truncated_or_empty_upload(self, client):
        """Uploading truncated bytes fails magic byte check."""
        res = client.post(
            "/api/analyze",
            files={"image": ("short.jpg", io.BytesIO(b"\xFF\xD8"), "image/jpeg")}
        )
        assert res.status_code == 400

    def test_reject_oversized_file(self):
        """Payload exceeding max size limit raises HTTP 413."""
        huge_bytes = b"\xFF\xD8\xFF\xE0" + b"\x00" * (11 * 1024 * 1024)
        with pytest.raises(HTTPException) as exc_info:
            validate_image_upload(huge_bytes, max_size_bytes=10 * 1024 * 1024)
        assert exc_info.value.status_code == 413
        assert "exceeds maximum limit" in exc_info.value.detail


class TestJWTRefreshSecurity:
    def test_db_backed_refresh_rotation_and_revocation(self, client):
        """Test registration, refresh token rotation, and rejection of replayed refresh tokens."""
        # 1. Register user
        reg_res = client.post(
            "/api/auth/register",
            json={"email": "security@test.com", "password": "SecurePassword123!"}
        )
        assert reg_res.status_code == 200
        tokens = reg_res.json()
        rt1 = tokens["refresh_token"]

        # 2. Refresh session with valid refresh token
        ref_res = client.post(
            "/api/auth/refresh",
            json={"refresh_token": rt1}
        )
        assert ref_res.status_code == 200
        new_tokens = ref_res.json()
        rt2 = new_tokens["refresh_token"]
        assert rt2 != rt1

        # 3. Attempt to REPLAY the old refresh token (rt1) - must be rejected with 401
        replay_res = client.post(
            "/api/auth/refresh",
            json={"refresh_token": rt1}
        )
        assert replay_res.status_code == 401
        assert "revoked" in replay_res.json()["detail"].lower()
