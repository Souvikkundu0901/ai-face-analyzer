"""
Deterministic rules engine.

Pure function: structured scores in → list of recommendation IDs out.
No I/O, no network calls, no side effects. Trivially unit-testable.

The LLM never touches this module. It only receives this module's output.
"""

from typing import Dict, Any, List

from app.rules.thresholds import (
    REDNESS_MODERATE_MIN,
    REDNESS_MODERATE_MAX,
    REDNESS_HIGH_MIN,
    PIGMENTATION_VARIATION_MIN,
    TEXTURE_ROUGH_MIN,
    UNDER_EYE_DARK_MIN,
    SPOTS_FEW_MIN,
    SPOTS_FEW_MAX,
    SPOTS_MANY_MIN,
    IMAGE_QUALITY_LOW_MAX,
)


def evaluate(scores: Dict[str, Any]) -> List[str]:
    """
    Evaluate structured analysis scores and return triggered recommendation IDs.

    Args:
        scores: Dictionary containing:
            - redness_score (float, 0.0-1.0)
            - pigmentation_score (float, 0.0-1.0)
            - texture_score (float, 0.0-1.0)
            - under_eye_score (float, 0.0-1.0)
            - visible_spots (int)
            - image_quality_score (float, 0.0-1.0)

    Returns:
        List of triggered recommendation IDs (strings).
        Returns ["ALL_CLEAR"] if no other recommendations are triggered.
    """
    triggered: List[str] = []

    # --- Redness evaluation ---
    redness = scores.get("redness_score", 0.0)
    if redness >= REDNESS_HIGH_MIN:
        triggered.append("REDNESS_HIGH")
    elif redness >= REDNESS_MODERATE_MIN:
        triggered.append("REDNESS_MODERATE")

    # --- Pigmentation variation ---
    pigmentation = scores.get("pigmentation_score", 0.0)
    if pigmentation >= PIGMENTATION_VARIATION_MIN:
        triggered.append("PIGMENTATION_VARIATION")

    # --- Texture roughness ---
    texture = scores.get("texture_score", 0.0)
    if texture >= TEXTURE_ROUGH_MIN:
        triggered.append("TEXTURE_ROUGH")

    # --- Under-eye darkness ---
    under_eye = scores.get("under_eye_score", 0.0)
    if under_eye >= UNDER_EYE_DARK_MIN:
        triggered.append("UNDER_EYE_DARK")

    # --- Spot-like regions ---
    spots = scores.get("visible_spots", 0)
    if spots >= SPOTS_MANY_MIN:
        triggered.append("SPOTS_MANY")
    elif spots >= SPOTS_FEW_MIN:
        triggered.append("SPOTS_FEW")

    # --- Image quality ---
    quality = scores.get("image_quality_score", 1.0)
    if quality < IMAGE_QUALITY_LOW_MAX:
        triggered.append("IMAGE_QUALITY_LOW")

    # --- Fallback: nothing triggered means all clear ---
    if not triggered:
        triggered.append("ALL_CLEAR")

    return triggered
