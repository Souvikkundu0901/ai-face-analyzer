"""
Integration/unit tests for the LLM explanation layer (app.llm.client).

Uses unittest.mock to mock the Gemini API and tests caching, fallbacks,
Pydantic validation, and the medical keyword safety net.
"""
import unittest
from unittest.mock import patch, MagicMock
import asyncio

# Setup event loop for async test cases
def async_test(coro):
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro(*args, **kwargs))
    return wrapper


class TestLLMIntegration(unittest.TestCase):
    """Test suite for the LLM Explanation client."""

    def setUp(self):
        # Clear in-memory cache before each test
        from app.llm.client import _explanation_cache
        _explanation_cache.clear()

    @patch("app.llm.client._call_gemini")
    @async_test
    async def test_successful_llm_generation(self, mock_call):
        """Verify successful LLM response is returned, validated, and cached."""
        from app.llm.client import generate_explanation, _explanation_cache
        from app.llm.schema import LLMReport, ExplanationItem

        # Configure mock return value
        expected_report = LLMReport(
            explanations=[
                ExplanationItem(id="REDNESS_MODERATE", text="Observational explanation of moderate redness.")
            ],
            summary="Skin shows high resilience with localized redness."
        )
        mock_call.return_value = expected_report

        triggered_ids = ["REDNESS_MODERATE"]
        supporting_scores = {"redness_score": 0.52}

        # First call: should call the mock API
        report = await generate_explanation(triggered_ids, supporting_scores)
        
        self.assertEqual(report.summary, "Skin shows high resilience with localized redness.")
        self.assertEqual(len(report.explanations), 1)
        self.assertEqual(report.explanations[0].id, "REDNESS_MODERATE")
        self.assertEqual(report.explanations[0].text, "Observational explanation of moderate redness.")
        
        mock_call.assert_called_once()
        self.assertEqual(len(_explanation_cache), 1)

        # Second call: should hit cache and NOT call the mock API again
        mock_call.reset_mock()
        report2 = await generate_explanation(triggered_ids, supporting_scores)
        self.assertEqual(report2.summary, report.summary)
        mock_call.assert_not_called()

    @patch("app.llm.client._call_gemini")
    @async_test
    async def test_llm_api_failure_fallback(self, mock_call):
        """Verify that on API error, the system falls back to static canned text."""
        from app.llm.client import generate_explanation
        from app.rules.recommendations import get_fallback_text

        # Configure mock to raise an exception (like connection or credentials error)
        mock_call.side_effect = Exception("API connection timed out")

        triggered_ids = ["REDNESS_HIGH", "TEXTURE_ROUGH"]
        supporting_scores = {"redness_score": 0.82, "texture_score": 0.65}

        report = await generate_explanation(triggered_ids, supporting_scores)

        # Should fall back to canned explanations
        self.assertEqual(len(report.explanations), 2)
        self.assertEqual(report.explanations[0].id, "REDNESS_HIGH")
        self.assertEqual(report.explanations[0].text, get_fallback_text("REDNESS_HIGH"))
        self.assertEqual(report.explanations[1].id, "TEXTURE_ROUGH")
        self.assertEqual(report.explanations[1].text, get_fallback_text("TEXTURE_ROUGH"))
        self.assertIn("2 observation(s) were noted", report.summary)

    @patch("app.llm.client._call_gemini")
    @async_test
    async def test_medical_keyword_safety_net(self, mock_call):
        """Verify that explanations containing banned medical terms fall back to canned text."""
        from app.llm.client import generate_explanation
        from app.llm.schema import LLMReport, ExplanationItem
        from app.rules.recommendations import get_fallback_text

        # Mock returns an explanation containing "rosacea" (banned) and "diagnose" (banned)
        expected_report = LLMReport(
            explanations=[
                ExplanationItem(id="REDNESS_MODERATE", text="This indicates a diagnosis of rosacea."),
                ExplanationItem(id="TEXTURE_ROUGH", text="This is a safe, observational explanation of rough texture.")
            ],
            summary="A safe summary of visible characteristics."
        )
        mock_call.return_value = expected_report

        triggered_ids = ["REDNESS_MODERATE", "TEXTURE_ROUGH"]
        supporting_scores = {"redness_score": 0.52, "texture_score": 0.65}

        report = await generate_explanation(triggered_ids, supporting_scores)

        # REDNESS_MODERATE should be replaced by static canned text
        self.assertEqual(report.explanations[0].id, "REDNESS_MODERATE")
        self.assertEqual(report.explanations[0].text, get_fallback_text("REDNESS_MODERATE"))
        self.assertNotIn("rosacea", report.explanations[0].text)

        # TEXTURE_ROUGH should remain unchanged
        self.assertEqual(report.explanations[1].id, "TEXTURE_ROUGH")
        self.assertEqual(report.explanations[1].text, "This is a safe, observational explanation of rough texture.")

    @patch("app.llm.client._call_gemini")
    @async_test
    async def test_llm_json_incomplete_keys(self, mock_call):
        """Verify that if LLM omits a triggered key, fallback text is supplied for that key."""
        from app.llm.client import generate_explanation
        from app.llm.schema import LLMReport, ExplanationItem
        from app.rules.recommendations import get_fallback_text

        # Mock returns only REDNESS_MODERATE explanation, omitting UNDER_EYE_DARK
        expected_report = LLMReport(
            explanations=[
                ExplanationItem(id="REDNESS_MODERATE", text="Observation of redness.")
            ],
            summary="Summary text."
        )
        mock_call.return_value = expected_report

        triggered_ids = ["REDNESS_MODERATE", "UNDER_EYE_DARK"]
        supporting_scores = {"redness_score": 0.52, "under_eye_score": 0.62}

        report = await generate_explanation(triggered_ids, supporting_scores)

        # Both should exist, with UNDER_EYE_DARK populated from fallback
        self.assertEqual(len(report.explanations), 2)
        self.assertEqual(report.explanations[0].id, "REDNESS_MODERATE")
        self.assertEqual(report.explanations[0].text, "Observation of redness.")
        
        self.assertEqual(report.explanations[1].id, "UNDER_EYE_DARK")
        self.assertEqual(report.explanations[1].text, get_fallback_text("UNDER_EYE_DARK"))


if __name__ == "__main__":
    unittest.main()
