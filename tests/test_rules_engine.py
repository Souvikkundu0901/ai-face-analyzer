"""
Exhaustive unit tests for the deterministic rules engine.

Tests every threshold boundary and combination scenario.
The rules engine is pure logic — same input always produces same output.
"""
import unittest
from app.rules.engine import evaluate


class TestRulesEngineAllClear(unittest.TestCase):
    """When all scores are below thresholds, only ALL_CLEAR fires."""

    def test_all_zeros(self):
        result = evaluate({
            "redness_score": 0.0,
            "pigmentation_score": 0.0,
            "texture_score": 0.0,
            "under_eye_score": 0.0,
            "visible_spots": 0,
            "image_quality_score": 1.0,
        })
        self.assertEqual(result, ["ALL_CLEAR"])

    def test_all_just_below_thresholds(self):
        result = evaluate({
            "redness_score": 0.39,
            "pigmentation_score": 0.49,
            "texture_score": 0.59,
            "under_eye_score": 0.49,
            "visible_spots": 2,
            "image_quality_score": 0.61,
        })
        self.assertEqual(result, ["ALL_CLEAR"])

    def test_missing_keys_default_to_safe(self):
        result = evaluate({})
        self.assertEqual(result, ["ALL_CLEAR"])


class TestRulesEngineRedness(unittest.TestCase):
    """Redness threshold boundary tests."""

    def test_redness_below_moderate(self):
        result = evaluate({"redness_score": 0.39})
        self.assertNotIn("REDNESS_MODERATE", result)
        self.assertNotIn("REDNESS_HIGH", result)

    def test_redness_at_moderate_boundary(self):
        result = evaluate({"redness_score": 0.4})
        self.assertIn("REDNESS_MODERATE", result)
        self.assertNotIn("REDNESS_HIGH", result)

    def test_redness_mid_moderate(self):
        result = evaluate({"redness_score": 0.55})
        self.assertIn("REDNESS_MODERATE", result)
        self.assertNotIn("REDNESS_HIGH", result)

    def test_redness_just_below_high(self):
        result = evaluate({"redness_score": 0.69})
        self.assertIn("REDNESS_MODERATE", result)
        self.assertNotIn("REDNESS_HIGH", result)

    def test_redness_at_high_boundary(self):
        result = evaluate({"redness_score": 0.7})
        self.assertIn("REDNESS_HIGH", result)
        self.assertNotIn("REDNESS_MODERATE", result)

    def test_redness_max(self):
        result = evaluate({"redness_score": 1.0})
        self.assertIn("REDNESS_HIGH", result)
        self.assertNotIn("REDNESS_MODERATE", result)


class TestRulesEnginePigmentation(unittest.TestCase):
    """Pigmentation variation threshold tests."""

    def test_below_threshold(self):
        result = evaluate({"pigmentation_score": 0.49})
        self.assertNotIn("PIGMENTATION_VARIATION", result)

    def test_at_threshold(self):
        result = evaluate({"pigmentation_score": 0.5})
        self.assertIn("PIGMENTATION_VARIATION", result)

    def test_above_threshold(self):
        result = evaluate({"pigmentation_score": 0.8})
        self.assertIn("PIGMENTATION_VARIATION", result)


class TestRulesEngineTexture(unittest.TestCase):
    """Texture roughness threshold tests."""

    def test_below_threshold(self):
        result = evaluate({"texture_score": 0.59})
        self.assertNotIn("TEXTURE_ROUGH", result)

    def test_at_threshold(self):
        result = evaluate({"texture_score": 0.6})
        self.assertIn("TEXTURE_ROUGH", result)

    def test_above_threshold(self):
        result = evaluate({"texture_score": 0.9})
        self.assertIn("TEXTURE_ROUGH", result)


class TestRulesEngineUnderEye(unittest.TestCase):
    """Under-eye darkness threshold tests."""

    def test_below_threshold(self):
        result = evaluate({"under_eye_score": 0.49})
        self.assertNotIn("UNDER_EYE_DARK", result)

    def test_at_threshold(self):
        result = evaluate({"under_eye_score": 0.5})
        self.assertIn("UNDER_EYE_DARK", result)


class TestRulesEngineSpots(unittest.TestCase):
    """Spot count threshold tests."""

    def test_zero_spots(self):
        result = evaluate({"visible_spots": 0})
        self.assertNotIn("SPOTS_FEW", result)
        self.assertNotIn("SPOTS_MANY", result)

    def test_two_spots(self):
        result = evaluate({"visible_spots": 2})
        self.assertNotIn("SPOTS_FEW", result)
        self.assertNotIn("SPOTS_MANY", result)

    def test_three_spots(self):
        result = evaluate({"visible_spots": 3})
        self.assertIn("SPOTS_FEW", result)
        self.assertNotIn("SPOTS_MANY", result)

    def test_seven_spots(self):
        result = evaluate({"visible_spots": 7})
        self.assertIn("SPOTS_FEW", result)
        self.assertNotIn("SPOTS_MANY", result)

    def test_eight_spots(self):
        result = evaluate({"visible_spots": 8})
        self.assertIn("SPOTS_MANY", result)
        self.assertNotIn("SPOTS_FEW", result)

    def test_twenty_spots(self):
        result = evaluate({"visible_spots": 20})
        self.assertIn("SPOTS_MANY", result)
        self.assertNotIn("SPOTS_FEW", result)


class TestRulesEngineImageQuality(unittest.TestCase):
    """Image quality threshold tests."""

    def test_good_quality(self):
        result = evaluate({"image_quality_score": 0.8})
        self.assertNotIn("IMAGE_QUALITY_LOW", result)

    def test_at_threshold(self):
        result = evaluate({"image_quality_score": 0.6})
        self.assertNotIn("IMAGE_QUALITY_LOW", result)

    def test_below_threshold(self):
        result = evaluate({"image_quality_score": 0.59})
        self.assertIn("IMAGE_QUALITY_LOW", result)


class TestRulesEngineCombinations(unittest.TestCase):
    """Test multiple recommendations firing together."""

    def test_multiple_skin_issues(self):
        result = evaluate({
            "redness_score": 0.75,
            "texture_score": 0.65,
            "visible_spots": 5,
            "image_quality_score": 0.9,
        })
        self.assertIn("REDNESS_HIGH", result)
        self.assertIn("TEXTURE_ROUGH", result)
        self.assertIn("SPOTS_FEW", result)
        self.assertNotIn("ALL_CLEAR", result)

    def test_everything_triggered(self):
        result = evaluate({
            "redness_score": 0.8,
            "pigmentation_score": 0.7,
            "texture_score": 0.7,
            "under_eye_score": 0.6,
            "visible_spots": 10,
            "image_quality_score": 0.4,
        })
        self.assertIn("REDNESS_HIGH", result)
        self.assertIn("PIGMENTATION_VARIATION", result)
        self.assertIn("TEXTURE_ROUGH", result)
        self.assertIn("UNDER_EYE_DARK", result)
        self.assertIn("SPOTS_MANY", result)
        self.assertIn("IMAGE_QUALITY_LOW", result)
        self.assertNotIn("ALL_CLEAR", result)
        self.assertEqual(len(result), 6)

    def test_quality_low_with_no_skin_issues(self):
        """IMAGE_QUALITY_LOW should fire even if skin scores are clean."""
        result = evaluate({
            "redness_score": 0.1,
            "pigmentation_score": 0.1,
            "texture_score": 0.1,
            "under_eye_score": 0.1,
            "visible_spots": 0,
            "image_quality_score": 0.3,
        })
        self.assertEqual(result, ["IMAGE_QUALITY_LOW"])
        self.assertNotIn("ALL_CLEAR", result)


if __name__ == "__main__":
    unittest.main()
