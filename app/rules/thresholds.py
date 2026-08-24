"""
Score band thresholds that trigger each recommendation.

All thresholds are plain constants with explanatory comments.
These are the ONLY values that determine which recommendations fire —
changing a value here changes system behavior deterministically.
"""

# ==============================================================================
# Skin Score Thresholds
# ==============================================================================

# Redness (0.0 = no redness, 1.0 = maximum redness detected)
REDNESS_MODERATE_MIN = 0.4   # Lower bound for moderate redness flag
REDNESS_MODERATE_MAX = 0.7   # Upper bound (exclusive) — above this triggers HIGH
REDNESS_HIGH_MIN = 0.7       # Threshold for elevated redness flag

# Pigmentation variation (0.0 = perfectly even, 1.0 = maximum variation)
PIGMENTATION_VARIATION_MIN = 0.5  # Minimum score to flag noticeable variation

# Texture roughness (0.0 = smooth, 1.0 = maximum roughness)
TEXTURE_ROUGH_MIN = 0.6  # Minimum score to flag noticeable texture

# Under-eye darkness (0.0 = no contrast, 1.0 = maximum contrast)
UNDER_EYE_DARK_MIN = 0.5  # Minimum score to flag under-eye contrast

# Spot-like region counts
SPOTS_FEW_MIN = 3    # Minimum spots to trigger "few spots" observation
SPOTS_FEW_MAX = 7    # Maximum spots for "few" category (inclusive)
SPOTS_MANY_MIN = 8   # Minimum spots for "many spots" observation

# ==============================================================================
# Image Quality Threshold
# ==============================================================================

# Overall image quality score (0.0 = poor, 1.0 = excellent)
IMAGE_QUALITY_LOW_MAX = 0.6  # Below this, suggest retake for better results
