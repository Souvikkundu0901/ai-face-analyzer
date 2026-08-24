"""
Fixed, finite catalog of all possible recommendation identifiers.

Every recommendation the system can ever produce is defined here.
The rules engine selects from this catalog; the LLM explains items
from this catalog. Nothing outside this list can appear in a report.

Language rules:
  - Non-medical, observational only
  - No condition names, no diagnoses, no treatment suggestions
  - Relative/normalized descriptions ("elevated", "noticeable", "minimal")
"""

from typing import Dict, Any


# Each entry contains:
#   id            — unique machine-readable key (used in API responses)
#   trigger_desc  — human-readable description of when this fires (documentation only)
#   fallback_text — static explanation used when the LLM is unavailable or fails
RECOMMENDATION_CATALOG: Dict[str, Dict[str, Any]] = {
    "REDNESS_MODERATE": {
        "trigger_desc": "redness_score between 0.4 and 0.7",
        "fallback_text": (
            "Moderate redness was detected across the analyzed skin areas, "
            "primarily in the cheek region. This may reflect natural flushing, "
            "recent physical activity, or environmental warmth."
        ),
        "icon": "🔴",
        "severity": "moderate",
    },
    "REDNESS_HIGH": {
        "trigger_desc": "redness_score above 0.7",
        "fallback_text": (
            "Elevated redness was detected across multiple facial zones. "
            "This is a visible surface observation and may be influenced by "
            "lighting conditions, recent sun exposure, or natural skin tone variation."
        ),
        "icon": "🔴",
        "severity": "high",
    },
    "PIGMENTATION_VARIATION": {
        "trigger_desc": "pigmentation_score above 0.5",
        "fallback_text": (
            "Noticeable variation in skin tone was observed across the analyzed area. "
            "This includes differences in luminance and color evenness that may "
            "reflect natural pigmentation patterns or uneven light exposure."
        ),
        "icon": "🎨",
        "severity": "moderate",
    },
    "TEXTURE_ROUGH": {
        "trigger_desc": "texture_score above 0.6",
        "fallback_text": (
            "Higher-than-average surface texture variation was detected. "
            "This measures fine-grain roughness visible at the pixel level "
            "and may be influenced by skin hydration, lighting angle, or camera focus."
        ),
        "icon": "🧱",
        "severity": "moderate",
    },
    "UNDER_EYE_DARK": {
        "trigger_desc": "under_eye_score above 0.5",
        "fallback_text": (
            "A noticeable contrast was detected between the under-eye area and "
            "the surrounding cheek region. This is a common visible feature that "
            "can be influenced by lighting, sleep patterns, or natural skin depth."
        ),
        "icon": "👁️",
        "severity": "moderate",
    },
    "SPOTS_FEW": {
        "trigger_desc": "visible_spots between 3 and 7",
        "fallback_text": (
            "A small number of spot-like regions were detected on the skin surface. "
            "These are localized areas of contrast variation and may include "
            "natural features like freckles or minor blemishes."
        ),
        "icon": "🔍",
        "severity": "low",
    },
    "SPOTS_MANY": {
        "trigger_desc": "visible_spots 8 or more",
        "fallback_text": (
            "Multiple spot-like regions were detected across the analyzed skin area. "
            "These represent localized contrast variations visible at the surface level "
            "and may include a mix of natural skin features."
        ),
        "icon": "🔍",
        "severity": "moderate",
    },
    "IMAGE_QUALITY_LOW": {
        "trigger_desc": "image_quality.score below 0.6",
        "fallback_text": (
            "The image quality score was below the recommended threshold. "
            "For more reliable analysis results, consider retaking the photo "
            "with better lighting, a steady hand, and the face centered in frame."
        ),
        "icon": "📷",
        "severity": "info",
    },
    "ALL_CLEAR": {
        "trigger_desc": "no other recommendations triggered",
        "fallback_text": (
            "All analyzed metrics fall within typical ranges. The skin surface "
            "appears even in tone, texture, and redness levels based on the "
            "visible characteristics captured in this image."
        ),
        "icon": "✅",
        "severity": "good",
    },
}


# Standard disclaimer — appears once at the report level, not per-item
REPORT_DISCLAIMER = (
    "This analysis reflects visible characteristics only and is not a medical "
    "diagnosis. The results are based on image processing heuristics and may "
    "vary with lighting, camera quality, and skin preparation. Consult a "
    "dermatologist for any skin concerns."
)


def get_fallback_text(recommendation_id: str) -> str:
    """Return the static fallback explanation for a recommendation ID."""
    entry = RECOMMENDATION_CATALOG.get(recommendation_id)
    if entry:
        return entry["fallback_text"]
    return f"Analysis observation: {recommendation_id.replace('_', ' ').lower()}."


def get_all_ids() -> list:
    """Return all valid recommendation IDs."""
    return list(RECOMMENDATION_CATALOG.keys())
