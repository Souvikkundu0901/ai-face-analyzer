"""
Centralized configuration, thresholds, landmark mappings, and constants for AI Face Analyzer.
Phase 2 (Hardening + Visualization): all magic numbers are extracted and documented here.
"""
import os
from pathlib import Path

# ==============================================================================
# 1. Base Paths and Versioning
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "face_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

# Version identifier — bump when thresholds or pipeline logic are modified
PIPELINE_VERSION = "analysis-v0.3.0"

# Verbose debug logging flag
DEBUG_MODE = os.environ.get("DEBUG", "false").lower() in ("true", "1", "yes")

# Max input resolution before internal downscaling for CV efficiency
MAX_INPUT_DIMENSION = 2048

# ==============================================================================
# 1b. Gemini LLM Configuration
# ==============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
LLM_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT_SECONDS", "10"))


# ==============================================================================
# 2. Quality Gate Thresholds
# ==============================================================================
QUALITY_THRESHOLDS = {
    # Sharpness: Laplacian variance cutoff. Lower values indicate motion/optical blur.
    "min_sharpness_var": 50.0,
    "sharpness_norm_scale": 300.0,
    
    # Exposure: Mean grayscale brightness (0 - 255).
    "min_brightness": 35.0,
    "max_brightness": 225.0,
    "optimal_brightness": 128.0,
    
    # Framing: Face bounding box ratios relative to image frame.
    "min_face_width_ratio": 0.18,
    "min_face_height_ratio": 0.20,
    "min_face_area_ratio": 0.04,
    
    # Head Pose: Maximum allowable rotation in degrees before quality gate fails.
    "max_yaw_deg": 30.0,
    "max_pitch_deg": 30.0,
    "max_roll_deg": 30.0,
    
    # Soft warning thresholds (triggers warnings without hard rejection)
    "warn_soft_sharpness": 80.0,
    "warn_low_brightness": 60.0,
    "warn_high_brightness": 195.0,
    "warn_yaw_deg": 18.0,
    "warn_pitch_deg": 18.0,
    "warn_roll_deg": 15.0,
}


# ==============================================================================
# 3. Skin Masking & Morphological Parameters
# ==============================================================================
MASK_CONFIG = {
    "dilation_kernel_size": (5, 5),
    "dilation_iterations": 1,
    "erosion_kernel_size": (5, 5),
    "erosion_iterations": 2,
}


# ==============================================================================
# 4. Skin Heuristic Parameters
# ==============================================================================
# Redness: CIELAB a* channel (higher = more red/magenta)
REDNESS_CONFIG = {
    "cielab_a_baseline": 132.0,  # standard neutral baseline in sRGB/LAB
    "cielab_a_range": 28.0,      # saturation range mapping to 1.0
    "cheek_weight": 0.60,        # weighting for cheek regional redness
    "face_weight": 0.40,         # weighting for general skin redness
}

# Pigmentation Variation: Luminance (L*) global standard deviation & local contrast
PIGMENTATION_CONFIG = {
    "std_baseline": 10.0,        # uniform skin tone std dev
    "std_scale": 22.0,           # variance scale mapping to 1.0
    "local_diff_baseline": 2.5,  # local median difference baseline
    "local_diff_scale": 7.0,
    "global_weight": 0.60,
    "local_weight": 0.40,
    "median_blur_ksize": 15,
}

# Texture Roughness: High-frequency gradient and Laplacian response
TEXTURE_CONFIG = {
    "bilateral_d": 7,
    "bilateral_sigma_color": 50,
    "bilateral_sigma_space": 50,
    "hf_baseline": 1.5,
    "hf_scale": 6.0,
    "lap_baseline": 2.0,
    "lap_scale": 10.0,
    "hf_weight": 0.60,
    "lap_weight": 0.40,
}

# Under-Eye Shade Contrast: Luminance deficit compared to cheek
UNDER_EYE_CONFIG = {
    "min_deficit": 0.02,
    "deficit_range": 0.20,
}

# Spot-like Region Detection: Scale-adaptive contrast peak blob detection
SPOT_CONFIG = {
    "blur_ksize": (25, 25),
    "percentile_threshold": 96.0,
    "min_percentile_val": 10,
    "min_circularity": 0.35,
    "min_area_ratio": 0.00003,
    "max_area_ratio": 0.003,
    "max_regions_output": 25,
}


# ==============================================================================
# 5. Face Shape Archetype Centroids (face_ratio, jaw_ratio, forehead_ratio)
# ==============================================================================
FACE_SHAPE_ARCHETYPES = {
    "oval": (1.40, 0.74, 0.80),
    "round": (1.18, 0.82, 0.82),
    "square": (1.20, 0.90, 0.88),
    "heart": (1.38, 0.65, 0.88),
    "diamond": (1.42, 0.64, 0.70),
    "rectangle": (1.58, 0.86, 0.84),
}

# Archetype distance scaling weights
FACE_SHAPE_SCALES = {
    "face_ratio_scale": 0.18,
    "jaw_ratio_scale": 0.12,
    "forehead_ratio_scale": 0.12,
}


# ==============================================================================
# 6. MediaPipe 478 Face Mesh Landmark Index Mappings
# ==============================================================================
LANDMARK_INDICES = {
    # Full outer face oval contour
    "face_oval": [
        10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 
        397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 
        172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109
    ],
    
    # Left eye contour
    "left_eye": [
        33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246
    ],
    
    # Right eye contour
    "right_eye": [
        362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398
    ],
    
    # Eyebrows
    "left_eyebrow": [70, 63, 105, 66, 107, 55, 65, 52, 53, 46],
    "right_eyebrow": [336, 296, 334, 293, 300, 276, 283, 282, 295, 285],
    
    # Lips outer boundary
    "lips_outer": [
        61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146
    ],
    
    # Nostrils
    "nostrils": [2, 98, 97, 327, 326],
    
    # Specific landmarks for distance measurement
    "top_forehead": 10,
    "chin": 152,
    "left_face_edge": 234,
    "right_face_edge": 454,
    "left_forehead_edge": 103,
    "right_forehead_edge": 332,
    "left_jaw_edge": 58,
    "right_jaw_edge": 288,
    "left_pupil": 468,
    "right_pupil": 473,
    "left_nose_edge": 129,
    "right_nose_edge": 358,
    "left_mouth_corner": 61,
    "right_mouth_corner": 291,
    "nose_tip": 1,
    "nose_bridge": 6,
    
    # Regional zones
    "left_under_eye": [111, 116, 123, 147, 192, 213, 130, 25, 33, 7, 163, 144],
    "right_under_eye": [340, 345, 352, 376, 416, 433, 359, 255, 362, 382, 381, 380],
    "left_cheek": [116, 117, 118, 119, 100, 126, 209, 198, 131, 134],
    "right_cheek": [345, 346, 347, 348, 329, 355, 429, 420, 360, 363],
    "forehead_zone": [10, 338, 297, 332, 284, 109, 67, 103, 68]
}
