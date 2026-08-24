"""
Gemini API wrapper with caching, fallback, and keyword safety net.

Core design principle: the app NEVER fails because the LLM had a hiccup.
On any error — timeout, malformed response, validation failure, banned
terms — the system falls back to canned template text from recommendations.py.
"""

import json
import logging
from typing import Dict, Any, List, Optional, Tuple

from app.llm.schema import LLMReport, ExplanationItem
from app.llm.prompt import SYSTEM_PROMPT, build_user_prompt, check_banned_terms
from app.rules.recommendations import get_fallback_text, RECOMMENDATION_CATALOG

logger = logging.getLogger("ai_face_analyzer.llm")

# ==============================================================================
# In-memory explanation cache
# Keyed by frozenset of sorted recommendation IDs.
# Same recommendation combo = same cached response (no redundant API calls).
# ==============================================================================
_explanation_cache: Dict[frozenset, LLMReport] = {}
MAX_CACHE_SIZE = 200


def _cache_key(triggered_ids: List[str]) -> frozenset:
    """Generate a deterministic cache key from recommendation IDs."""
    return frozenset(sorted(triggered_ids))


def _build_fallback_report(triggered_ids: List[str]) -> LLMReport:
    """
    Build a complete report from static canned text.
    Used when the LLM call fails or returns invalid output.
    """
    explanations = [
        ExplanationItem(id=rid, text=get_fallback_text(rid))
        for rid in triggered_ids
    ]

    if "ALL_CLEAR" in triggered_ids:
        summary = (
            "Overall, the analyzed facial characteristics fall within "
            "typical ranges based on the visible features in this image."
        )
    else:
        count = len([r for r in triggered_ids if r != "IMAGE_QUALITY_LOW"])
        summary = (
            f"Based on this analysis, {count} observation(s) were noted. "
            f"These reflect visible surface characteristics captured in the image."
        )

    return LLMReport(explanations=explanations, summary=summary)


def _sanitize_report(report: LLMReport, triggered_ids: List[str]) -> LLMReport:
    """
    Post-generation safety net: check each explanation for banned
    medical terms. Replace offending items with canned fallback text.
    """
    sanitized_explanations = []
    for item in report.explanations:
        if check_banned_terms(item.text):
            logger.warning(
                f"Banned medical term detected in LLM output for {item.id}. "
                f"Falling back to canned text."
            )
            sanitized_explanations.append(
                ExplanationItem(id=item.id, text=get_fallback_text(item.id))
            )
        else:
            sanitized_explanations.append(item)

    # Also check the summary
    summary = report.summary
    if check_banned_terms(summary):
        logger.warning("Banned medical term detected in LLM summary. Using fallback.")
        summary = (
            f"Based on this analysis, {len(triggered_ids)} observation(s) were noted "
            f"reflecting visible surface characteristics."
        )

    return LLMReport(explanations=sanitized_explanations, summary=summary)


async def generate_explanation(
    triggered_ids: List[str],
    supporting_scores: Dict[str, Any],
    face_shape: str = "unknown",
) -> LLMReport:
    """
    Generate LLM-powered explanations for triggered recommendation IDs.

    Flow:
    1. Check cache → return cached report if available
    2. Call Gemini API with structured prompt
    3. Validate response against Pydantic schema
    4. Run keyword safety net
    5. Cache and return

    On ANY failure at steps 2-4, falls back to canned template text.
    The request always succeeds — never fails due to LLM issues.
    """
    cache_key = _cache_key(triggered_ids)

    # 1. Check cache
    if cache_key in _explanation_cache:
        logger.debug(f"Cache hit for recommendation combo: {sorted(triggered_ids)}")
        return _explanation_cache[cache_key]

    # 2. Attempt Gemini API call
    try:
        report = await _call_gemini(triggered_ids, supporting_scores, face_shape)
    except Exception as e:
        logger.error(f"LLM API call failed: {e}. Using canned fallback text.")
        report = _build_fallback_report(triggered_ids)
        # Cache the fallback too so we don't retry failed combos repeatedly
        _cache_report(cache_key, report)
        return report

    # Verify all triggered IDs are covered in explanations
    explained_ids = {item.id for item in report.explanations}
    missing_ids = set(triggered_ids) - explained_ids
    if missing_ids:
        for mid in missing_ids:
            report.explanations.append(
                ExplanationItem(id=mid, text=get_fallback_text(mid))
            )

    # 3. Sanitize for banned medical terms
    report = _sanitize_report(report, triggered_ids)

    # 4. Cache and return
    _cache_report(cache_key, report)
    return report


def _cache_report(key: frozenset, report: LLMReport) -> None:
    """Store report in cache with simple FIFO eviction."""
    if len(_explanation_cache) >= MAX_CACHE_SIZE:
        oldest = next(iter(_explanation_cache))
        del _explanation_cache[oldest]
    _explanation_cache[key] = report


async def _call_gemini(
    triggered_ids: List[str],
    supporting_scores: Dict[str, Any],
    face_shape: str,
) -> LLMReport:
    """
    Make the actual Gemini API call and parse the response.
    Raises on any failure (caught by caller for fallback).
    """
    from app.config import GEMINI_API_KEY, GEMINI_MODEL, LLM_TIMEOUT_SECONDS

    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. Using canned fallback text.")
        return _build_fallback_report(triggered_ids)

    # Import here to avoid import errors when API key is not configured
    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)

    user_prompt = build_user_prompt(triggered_ids, supporting_scores, face_shape)

    logger.debug(f"Calling Gemini ({GEMINI_MODEL}) for IDs: {triggered_ids}")

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.3,
            max_output_tokens=1024,
            response_mime_type="application/json",
        ),
    )

    # Extract text from response
    raw_text = response.text
    if not raw_text:
        raise ValueError("Empty response from Gemini API")

    # Parse JSON
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Gemini returned invalid JSON: {e}")

    # Validate against Pydantic schema
    return LLMReport(**parsed)
