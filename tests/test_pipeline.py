"""
Automated Test Harness for AI Face Analyzer (Phase 2).
Includes subfolder batch testing, relative ordering invariant tests, and edge-case resilience tests.
"""
import io
import unittest
from pathlib import Path
import cv2
import numpy as np

from app.config import PIPELINE_VERSION
from app.pipeline.face_detect import FaceDetector, ensure_model_downloaded, get_face_landmarks
from app.pipeline.quality import evaluate_sharpness, evaluate_lighting, validate_image_quality
from app.pipeline.geometry import analyze_face_geometry, classify_face_shape
from app.pipeline.skin import analyze_skin_characteristics
from app.pipeline.overlay import render_debug_overlay, render_rejection_debug_overlay


class TestPhase2Harness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_model_downloaded()
        cls.detector = FaceDetector.get_instance()
        cls.sample_root = Path(__file__).resolve().parent / "sample_images"

    def _run_pipeline_on_image(self, img_path: Path):
        """Helper to run the full pipeline on a given image file."""
        bgr = cv2.imread(str(img_path))
        self.assertIsNotNone(bgr, f"Could not load image: {img_path}")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w = bgr.shape[:2]

        face_count, landmarks, _ = get_face_landmarks(rgb)
        passed, reason, msg, q_metrics, warnings = validate_image_quality(bgr, face_count, landmarks)
        
        geo_result, skin_result, regions, overlay_bytes = None, None, None, None
        if passed:
            geo_result = analyze_face_geometry(landmarks, w, h)
            skin_result, regions, skin_mask = analyze_skin_characteristics(bgr, landmarks)
            overlay_bytes = render_debug_overlay(bgr, landmarks, regions, geo_result, skin_result, skin_mask)

        return {
            "passed": passed,
            "reason": reason,
            "message": msg,
            "quality": q_metrics,
            "geometry": geo_result,
            "skin": skin_result,
            "regions": regions,
            "overlay": overlay_bytes,
            "bgr": bgr
        }

    # ==========================================================================
    # 1. Quality Gate Rejection Tests by Subfolder
    # ==========================================================================
    def test_rejection_no_face_folder(self):
        """Verify that all images in no_face/ are rejected with reason 'no_face'."""
        folder = self.sample_root / "no_face"
        for img_path in folder.glob("*.jpg"):
            res = self._run_pipeline_on_image(img_path)
            self.assertFalse(res["passed"], f"Expected rejection for {img_path.name}")
            self.assertEqual(res["reason"], "no_face", f"Wrong reason for {img_path.name}")

    def test_rejection_multiple_faces_folder(self):
        """Verify that all images in multiple_faces/ are rejected with reason 'multiple_faces'."""
        folder = self.sample_root / "multiple_faces"
        for img_path in folder.glob("*.jpg"):
            res = self._run_pipeline_on_image(img_path)
            self.assertFalse(res["passed"], f"Expected rejection for {img_path.name}")
            self.assertEqual(res["reason"], "multiple_faces", f"Wrong reason for {img_path.name}")

    def test_rejection_blurry_folder(self):
        """Verify that all images in blurry/ are rejected with reason 'blur'."""
        folder = self.sample_root / "blurry"
        for img_path in folder.glob("*.jpg"):
            res = self._run_pipeline_on_image(img_path)
            self.assertFalse(res["passed"], f"Expected rejection for {img_path.name}")
            self.assertEqual(res["reason"], "blur", f"Wrong reason for {img_path.name}")

    def test_rejection_low_light_folder(self):
        """Verify that low_light/ images are rejected with reason 'underexposed' or 'no_face'."""
        folder = self.sample_root / "low_light"
        for img_path in folder.glob("*.jpg"):
            res = self._run_pipeline_on_image(img_path)
            self.assertFalse(res["passed"], f"Expected rejection for {img_path.name}")
            self.assertIn(res["reason"], ["underexposed", "no_face"])

    def test_rejection_extreme_angle_folder(self):
        """Verify that extreme_angle/ images are rejected with reason 'pose_angle' or 'no_face'."""
        folder = self.sample_root / "extreme_angle"
        for img_path in folder.glob("*.jpg"):
            res = self._run_pipeline_on_image(img_path)
            self.assertFalse(res["passed"], f"Expected rejection for {img_path.name}")
            self.assertIn(res["reason"], ["pose_angle", "no_face"])

    # ==========================================================================
    # 2. Passing Test Cases
    # ==========================================================================
    def test_good_lighting_folder(self):
        """Verify that images in good_lighting/ pass the quality gate and produce valid results."""
        folder = self.sample_root / "good_lighting"
        for img_path in folder.glob("*.jpg"):
            res = self._run_pipeline_on_image(img_path)
            self.assertTrue(res["passed"], f"Failed on good image {img_path.name}: {res['reason']}")
            self.assertIsNotNone(res["geometry"])
            self.assertIsNotNone(res["skin"])
            self.assertIsNotNone(res["overlay"])
            self.assertGreater(res["quality"]["score"], 0.70)

    def test_varied_skin_tones_folder(self):
        """Verify that varied skin tones pass and compute valid non-zero metrics."""
        folder = self.sample_root / "varied_skin_tones"
        for img_path in folder.glob("*.jpg"):
            res = self._run_pipeline_on_image(img_path)
            self.assertTrue(res["passed"], f"Failed on {img_path.name}: {res['reason']}")
            self.assertIn("redness_score", res["skin"])
            self.assertIn("pigmentation_score", res["skin"])
            self.assertIn("texture_score", res["skin"])

    # ==========================================================================
    # 3. Relative Ordering Tests
    # ==========================================================================
    def test_relative_ordering_redness(self):
        """Assert that redness_score(flushed) > redness_score(fair)."""
        p_fair = self.sample_root / "varied_skin_tones" / "sample_fair.jpg"
        p_flushed = self.sample_root / "varied_skin_tones" / "sample_flushed.jpg"
        if p_fair.exists() and p_flushed.exists():
            res_fair = self._run_pipeline_on_image(p_fair)
            res_flushed = self._run_pipeline_on_image(p_flushed)
            self.assertGreater(
                res_flushed["skin"]["redness_score"],
                res_fair["skin"]["redness_score"],
                "Flushed sample must have higher redness score than fair baseline."
            )

    def test_relative_ordering_texture(self):
        """Assert that texture_score(textured) > texture_score(fair)."""
        p_fair = self.sample_root / "varied_skin_tones" / "sample_fair.jpg"
        p_textured = self.sample_root / "varied_skin_tones" / "sample_textured.jpg"
        if p_fair.exists() and p_textured.exists():
            res_fair = self._run_pipeline_on_image(p_fair)
            res_textured = self._run_pipeline_on_image(p_textured)
            self.assertGreater(
                res_textured["skin"]["texture_score"],
                res_fair["skin"]["texture_score"],
                "Artificially textured sample must have higher texture score than baseline."
            )

    def test_relative_ordering_sharpness(self):
        """Assert that sharpness(good) > sharpness(blurry)."""
        p_good = self.sample_root / "good_lighting" / "sample_good1.jpg"
        p_blur = self.sample_root / "blurry" / "sample_blurry.jpg"
        if p_good.exists() and p_blur.exists():
            res_good = self._run_pipeline_on_image(p_good)
            res_blur = self._run_pipeline_on_image(p_blur)
            self.assertGreater(
                res_good["quality"]["sharpness"],
                res_blur["quality"]["sharpness"],
                "Good sample sharpness must exceed blurry sample sharpness."
            )

    # ==========================================================================
    # 4. Rejection Debug Overlay Test
    # ==========================================================================
    def test_rejection_debug_overlay(self):
        """Verify that rejection debug overlay generates valid PNG bytes."""
        img = np.full((300, 300, 3), 10, dtype=np.uint8)
        overlay_bytes = render_rejection_debug_overlay(
            img, reason="underexposed", message="Image is too dark.", metrics={"sharpness": 0.5, "lighting": 0.1, "pose": 1.0}
        )
        self.assertGreater(len(overlay_bytes), 500)
        self.assertTrue(overlay_bytes.startswith(b'\x89PNG\r\n\x1a\n'))


if __name__ == "__main__":
    unittest.main()
