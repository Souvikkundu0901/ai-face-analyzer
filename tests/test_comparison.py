"""
Comparison logic and comparability warning tests (Phase 4, Sections 5 & 8).
Verifies:
  1. Accurate metric delta computation (newest - oldest) with known score pairs.
  2. Face shape stability detection across scans.
  3. Comparability warning triggers on mismatched capture conditions (e.g. image quality gap).
  4. Comparability warning triggers on mismatched pose/angle.
  5. Happy path comparison without warnings when capture conditions are well-matched.
  6. Integration via GET /api/scans/compare endpoint.
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
from app.db.models import Scan
from app.comparison.service import compare_scan_records

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


def make_scan_dict(scan_id, quality=0.85, lighting=0.85, pose=0.85, redness=0.25, pigmentation=0.30, texture=0.40, undereye=0.35, spots=3, shape="oval", days_offset=0):
    """Generates a structured scan dictionary for pure service unit tests."""
    return {
        "id": scan_id,
        "created_at": datetime.now(timezone.utc) + timedelta(days=days_offset),
        "image_quality": {"score": quality, "lighting": lighting, "pose": pose, "sharpness": quality},
        "face": {"shape": shape},
        "skin": {
            "redness_score": redness,
            "pigmentation_score": pigmentation,
            "texture_score": texture,
            "under_eye_score": undereye,
            "visible_spots": spots,
        }
    }


class TestComparisonLogic(unittest.TestCase):
    """Test suite for longitudinal comparison calculation and comparability warnings."""

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)
        app.dependency_overrides[get_db] = override_get_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)
        app.dependency_overrides.pop(get_db, None)

    def test_01_metric_deltas_with_known_pairs(self):
        """Verify delta computation: delta = newest - oldest."""
        scan_a = make_scan_dict(
            "scan_a", quality=0.85, redness=0.40, pigmentation=0.35, texture=0.50, undereye=0.40, spots=5, days_offset=0
        )
        scan_b = make_scan_dict(
            "scan_b", quality=0.85, redness=0.28, pigmentation=0.38, texture=0.45, undereye=0.40, spots=3, days_offset=7
        )

        res = compare_scan_records([scan_a, scan_b])

        self.assertEqual(res.scans_compared, ["scan_a", "scan_b"])
        # Expected:
        # redness: 0.28 - 0.40 = -0.12
        # pigmentation: 0.38 - 0.35 = 0.03
        # texture: 0.45 - 0.50 = -0.05
        # under_eye: 0.40 - 0.40 = 0.0
        # spots: 3 - 5 = -2
        self.assertAlmostEqual(res.deltas.redness_score, -0.12, places=3)
        self.assertAlmostEqual(res.deltas.pigmentation_score, 0.03, places=3)
        self.assertAlmostEqual(res.deltas.texture_score, -0.05, places=3)
        self.assertAlmostEqual(res.deltas.under_eye_score, 0.0, places=3)
        self.assertEqual(res.deltas.visible_spots, -2)
        self.assertTrue(res.face_shape_stable)
        self.assertIsNone(res.comparability_warning)

    def test_02_comparability_warning_on_quality_gap(self):
        """CRITICAL: Surfacing comparability warning when comparing high vs low quality scans."""
        # scan_high: high quality (0.90)
        scan_high = make_scan_dict("scan_high", quality=0.90, redness=0.25, days_offset=0)
        # scan_low: low quality (0.62) -> gap >= 0.20
        scan_low = make_scan_dict("scan_low", quality=0.62, redness=0.45, days_offset=14)

        res = compare_scan_records([scan_high, scan_low])

        self.assertIsNotNone(res.comparability_warning, "Comparability warning did not trigger on quality gap!")
        self.assertIn("quality differs significantly", res.comparability_warning.lower())

    def test_03_comparability_warning_on_pose_mismatch(self):
        """Comparability warning must trigger when head angle / pose differs substantially."""
        scan_straight = make_scan_dict("scan_straight", quality=0.85, pose=0.92, days_offset=0)
        scan_angled = make_scan_dict("scan_angled", quality=0.85, pose=0.60, days_offset=7)  # gap >= 0.25

        res = compare_scan_records([scan_straight, scan_angled])

        self.assertIsNotNone(res.comparability_warning, "Warning did not trigger on pose angle gap!")
        self.assertIn("pose", res.comparability_warning.lower())

    def test_04_face_shape_stability(self):
        """Detect when classified face shape changes between scans."""
        scan_oval = make_scan_dict("scan_1", shape="oval", days_offset=0)
        scan_round = make_scan_dict("scan_2", shape="round", days_offset=5)

        res = compare_scan_records([scan_oval, scan_round])
        self.assertFalse(res.face_shape_stable, "Face shape change was not detected as unstable!")

    def test_05_api_compare_endpoint(self):
        """Integration test for GET /api/scans/compare?ids=a,b."""
        res_user = self.client.post("/api/auth/register", json={"email": "compare_api@example.com", "password": "password123"})
        token = res_user.json()["access_token"]
        user_id = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]

        db = TestingSessionLocal()
        try:
            scan1_id = str(uuid.uuid4())
            s1 = Scan(
                id=scan1_id,
                user_id=user_id,
                pipeline_version="analysis-v0.4.0",
                image_quality={"score": 0.88, "lighting": 0.85, "pose": 0.90, "sharpness": 0.88},
                face_metrics={"shape": "oval"},
                skin_metrics={"redness_score": 0.35, "pigmentation_score": 0.30, "texture_score": 0.40, "under_eye_score": 0.30, "visible_spots": 4},
                regions=[],
                recommendation_ids=["ALL_CLEAR"],
                report={"triggered_recommendations": [], "explanations": [], "summary": "S1", "disclaimer": "D"},
                created_at=datetime.now(timezone.utc) - timedelta(days=10)
            )
            scan2_id = str(uuid.uuid4())
            s2 = Scan(
                id=scan2_id,
                user_id=user_id,
                pipeline_version="analysis-v0.4.0",
                image_quality={"score": 0.86, "lighting": 0.84, "pose": 0.89, "sharpness": 0.85},
                face_metrics={"shape": "oval"},
                skin_metrics={"redness_score": 0.25, "pigmentation_score": 0.28, "texture_score": 0.35, "under_eye_score": 0.28, "visible_spots": 2},
                regions=[],
                recommendation_ids=["ALL_CLEAR"],
                report={"triggered_recommendations": [], "explanations": [], "summary": "S2", "disclaimer": "D"},
                created_at=datetime.now(timezone.utc)
            )
            db.add_all([s1, s2])
            db.commit()
        finally:
            db.close()

        # Call compare endpoint
        res = self.client.get(
            f"/api/scans/compare?ids={scan1_id},{scan2_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        self.assertEqual(data["scans_compared"], [scan1_id, scan2_id])
        self.assertAlmostEqual(data["deltas"]["redness_score"], -0.10, places=3)
        self.assertEqual(data["deltas"]["visible_spots"], -2)
        self.assertTrue(data["face_shape_stable"])
        self.assertIsNone(data["comparability_warning"])
        self.assertEqual(len(data["timeline"]), 2)


if __name__ == "__main__":
    unittest.main()
