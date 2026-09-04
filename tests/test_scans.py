"""
Scan persistence, authorization isolation, and deletion tests (Phase 4, Sections 4 & 6).
Verifies:
  1. Strict authorization scoping (User A cannot access, delete, or compare User B's scans).
  2. Real database deletion (physical DELETE statement, no soft-delete flag).
  3. Real cascading account deletion (deleting user removes all associated scans).
  4. Scan history listing and pagination.
"""
import unittest
import uuid
from datetime import datetime, timezone, timedelta
from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.session import Base, get_db
from app.db.models import User, Scan

# Shared in-memory test database
test_engine = create_engine(
    "sqlite:///:memory:",
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


def create_mock_scan(db, user_id, quality=0.85, redness=0.25, shape="oval", offset_minutes=0):
    """Helper to insert a structured scan into DB for testing persistence and comparison."""
    scan_id = str(uuid.uuid4())
    scan = Scan(
        id=scan_id,
        user_id=user_id,
        pipeline_version="analysis-v0.4.0",
        image_quality={"score": quality, "lighting": quality, "sharpness": quality, "pose": quality, "passed": True},
        face_metrics={"shape": shape, "shape_confidence": 0.9, "symmetry_score": 0.88, "face_ratio": 1.4, "ratios": {}},
        skin_metrics={"redness_score": redness, "pigmentation_score": 0.2, "texture_score": 0.3, "under_eye_score": 0.2, "visible_spots": 2},
        regions=[],
        recommendation_ids=["ALL_CLEAR"] if redness < 0.4 else ["REDNESS_MODERATE"],
        report={"triggered_recommendations": [], "explanations": [], "summary": "Test summary", "disclaimer": "Test disclaimer"},
        image_ref=None,
        created_at=datetime.now(timezone.utc) + timedelta(minutes=offset_minutes),
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan_id


class TestScansPersistenceAndSecurity(unittest.TestCase):
    """Test suite for scan persistence, security isolation, and deletion."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        app.dependency_overrides.pop(get_db, None)

    def test_01_user_authorization_isolation(self):
        """CRITICAL: User B must NEVER be able to read, delete, or compare User A's scans."""
        # 1. Register User A and User B
        res_a = self.client.post("/api/auth/register", json={"email": "usera@example.com", "password": "password123"})
        token_a = res_a.json()["access_token"]
        user_a_info = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_a}"}).json()
        user_a_id = user_a_info["id"]

        res_b = self.client.post("/api/auth/register", json={"email": "userb@example.com", "password": "password123"})
        token_b = res_b.json()["access_token"]
        user_b_info = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token_b}"}).json()
        user_b_id = user_b_info["id"]

        # 2. Insert scan for User A directly into DB
        db = TestingSessionLocal()
        try:
            scan_a_id = create_mock_scan(db, user_id=user_a_id, quality=0.9, redness=0.2)
            scan_b_id = create_mock_scan(db, user_id=user_b_id, quality=0.9, redness=0.3)
        finally:
            db.close()

        # 3. User B attempts to read User A's scan -> MUST return 404
        res_read = self.client.get(
            f"/api/scans/{scan_a_id}",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(res_read.status_code, 404, "User B was able to read User A's scan!")

        # 4. User B attempts to delete User A's scan -> MUST return 404
        res_del = self.client.delete(
            f"/api/scans/{scan_a_id}",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(res_del.status_code, 404, "User B was able to delete User A's scan!")

        # Verify User A's scan is still intact in DB
        db = TestingSessionLocal()
        try:
            intact = db.query(Scan).filter(Scan.id == scan_a_id).first()
            self.assertIsNotNone(intact, "User A's scan was erroneously deleted!")
        finally:
            db.close()

        # 5. User B attempts to compare User A's scan with User B's scan -> MUST return 404
        res_compare = self.client.get(
            f"/api/scans/compare?ids={scan_a_id},{scan_b_id}",
            headers={"Authorization": f"Bearer {token_b}"}
        )
        self.assertEqual(res_compare.status_code, 404, "User B was able to include User A's scan in comparison!")

        # 6. User B list scans -> MUST NOT contain User A's scan
        res_list_b = self.client.get("/api/scans", headers={"Authorization": f"Bearer {token_b}"})
        self.assertEqual(res_list_b.status_code, 200)
        items_b = res_list_b.json()["items"]
        b_scan_ids = [item["id"] for item in items_b]
        self.assertIn(scan_b_id, b_scan_ids)
        self.assertNotIn(scan_a_id, b_scan_ids)

    def test_02_real_scan_deletion(self):
        """CRITICAL: Scan deletion must physically delete the row from DB (no soft-delete)."""
        res_user = self.client.post("/api/auth/register", json={"email": "deleter@example.com", "password": "password123"})
        token = res_user.json()["access_token"]
        user_id = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]

        db = TestingSessionLocal()
        try:
            scan_id = create_mock_scan(db, user_id=user_id)
        finally:
            db.close()

        # Delete via API
        res_del = self.client.delete(f"/api/scans/{scan_id}", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(res_del.json()["status"], "deleted")

        # Verify real physical removal from DB
        db = TestingSessionLocal()
        try:
            row = db.query(Scan).filter(Scan.id == scan_id).first()
            self.assertIsNone(row, "Scan row still exists in database after DELETE!")
        finally:
            db.close()

        # Subsequent GET must return 404
        res_get = self.client.get(f"/api/scans/{scan_id}", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_get.status_code, 404)

    def test_03_account_deletion_cascades_all_data(self):
        """CRITICAL: Deleting an account must cascade and physically delete all scans and user data."""
        res_user = self.client.post("/api/auth/register", json={"email": "cascade@example.com", "password": "password123"})
        token = res_user.json()["access_token"]
        user_id = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]

        db = TestingSessionLocal()
        try:
            scan1_id = create_mock_scan(db, user_id=user_id, offset_minutes=1)
            scan2_id = create_mock_scan(db, user_id=user_id, offset_minutes=2)
        finally:
            db.close()

        # Delete user account via DELETE /api/users/me
        res_del = self.client.delete("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(res_del.json()["status"], "deleted")

        # Verify user is gone
        db = TestingSessionLocal()
        try:
            user_row = db.query(User).filter(User.id == user_id).first()
            self.assertIsNone(user_row, "User row still exists after account deletion!")

            # Verify all scans are gone
            scans = db.query(Scan).filter(Scan.id.in_([scan1_id, scan2_id])).all()
            self.assertEqual(len(scans), 0, f"Orphaned scans remain after account deletion: {scans}")
        finally:
            db.close()

    def test_04_scan_pagination(self):
        """Verify pagination with limit and offset."""
        res_user = self.client.post("/api/auth/register", json={"email": "pagination@example.com", "password": "password123"})
        token = res_user.json()["access_token"]
        user_id = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]

        db = TestingSessionLocal()
        try:
            # Create 12 scans with different timestamps
            for i in range(12):
                create_mock_scan(db, user_id=user_id, offset_minutes=i)
        finally:
            db.close()

        # Page 1 (limit 5, offset 0)
        res_p1 = self.client.get("/api/scans?limit=5&offset=0", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_p1.status_code, 200)
        p1 = res_p1.json()
        self.assertEqual(p1["total"], 12)
        self.assertEqual(len(p1["items"]), 5)

        # Page 2 (limit 5, offset 5)
        res_p2 = self.client.get("/api/scans?limit=5&offset=5", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_p2.status_code, 200)
        p2 = res_p2.json()
        self.assertEqual(len(p2["items"]), 5)

        # Ensure no overlap between page 1 and page 2
        p1_ids = {item["id"] for item in p1["items"]}
        p2_ids = {item["id"] for item in p2["items"]}
        self.assertEqual(len(p1_ids.intersection(p2_ids)), 0)

        # Page 3 (limit 5, offset 10)
        res_p3 = self.client.get("/api/scans?limit=5&offset=10", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(res_p3.status_code, 200)
        p3 = res_p3.json()
        self.assertEqual(len(p3["items"]), 2)


if __name__ == "__main__":
    unittest.main()
