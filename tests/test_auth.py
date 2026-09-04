"""
Authentication unit and integration tests (Phase 4, Section 3).
Tests registration, login, token refreshing, rotation, and authorization guard.
"""
import unittest
import uuid
from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.db.models import User, RefreshToken

# In-memory database with StaticPool so all sessions share the same in-memory DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestAuthFlow(unittest.TestCase):
    """Test suite for authentication API endpoints."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        app.dependency_overrides.pop(get_db, None)

    def test_01_register_user_success(self):
        """Register a new user successfully."""
        email = f"user_{uuid.uuid4().hex[:6]}@example.com"
        res = self.client.post("/api/auth/register", json={
            "email": email,
            "password": "strongPassword123!"
        })
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["token_type"], "bearer")

    def test_02_register_duplicate_email_fails(self):
        """Duplicate email registration must return 400 Bad Request."""
        email = "duplicate@example.com"
        # First registration
        res1 = self.client.post("/api/auth/register", json={
            "email": email,
            "password": "password123"
        })
        self.assertEqual(res1.status_code, 200)

        # Duplicate registration
        res2 = self.client.post("/api/auth/register", json={
            "email": email,
            "password": "anotherPassword"
        })
        self.assertEqual(res2.status_code, 400)
        self.assertIn("already exists", res2.json()["detail"])

    def test_03_login_success_and_invalid_password(self):
        """Login with valid password succeeds; invalid password returns 401."""
        email = "login_test@example.com"
        password = "mySecretPassword!"
        self.client.post("/api/auth/register", json={"email": email, "password": password})

        # Correct password
        res_ok = self.client.post("/api/auth/login", json={"email": email, "password": password})
        self.assertEqual(res_ok.status_code, 200)
        tokens = res_ok.json()
        self.assertIn("access_token", tokens)

        # Wrong password
        res_fail = self.client.post("/api/auth/login", json={"email": email, "password": "wrongPassword"})
        self.assertEqual(res_fail.status_code, 401)
        self.assertIn("Invalid email or password", res_fail.json()["detail"])

    def test_04_get_current_user_profile(self):
        """Protected /api/auth/me returns authenticated user profile."""
        email = "profile_test@example.com"
        reg = self.client.post("/api/auth/register", json={"email": email, "password": "password123"})
        token = reg.json()["access_token"]

        # Call with valid Bearer token
        res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res.status_code, 200)
        user_info = res.json()
        self.assertEqual(user_info["email"], email)
        self.assertIn("id", user_info)

        # Call without token
        res_no_auth = self.client.get("/api/auth/me")
        self.assertEqual(res_no_auth.status_code, 401)

        # Call with garbage token
        res_bad_auth = self.client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.value"})
        self.assertEqual(res_bad_auth.status_code, 401)

    def test_05_refresh_token_rotation_and_revocation(self):
        """Refresh token generates new pair and immediately revokes the old refresh token."""
        email = "refresh_test@example.com"
        reg = self.client.post("/api/auth/register", json={"email": email, "password": "password123"})
        initial_refresh_token = reg.json()["refresh_token"]

        # 1. Use refresh token to get new tokens
        res_refresh = self.client.post("/api/auth/refresh", json={"refresh_token": initial_refresh_token})
        self.assertEqual(res_refresh.status_code, 200, res_refresh.text)
        new_tokens = res_refresh.json()
        self.assertIn("access_token", new_tokens)
        self.assertIn("refresh_token", new_tokens)
        new_refresh_token = new_tokens["refresh_token"]

        # 2. Re-using the initial refresh token MUST be rejected (already revoked)
        res_reuse = self.client.post("/api/auth/refresh", json={"refresh_token": initial_refresh_token})
        self.assertEqual(res_reuse.status_code, 401)
        self.assertIn("revoked or expired", res_reuse.json()["detail"])

        # 3. Using the new refresh token should succeed
        res_next = self.client.post("/api/auth/refresh", json={"refresh_token": new_refresh_token})
        self.assertEqual(res_next.status_code, 200)


if __name__ == "__main__":
    unittest.main()
