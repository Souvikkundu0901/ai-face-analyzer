"""
Facial geometry analysis, ratio computation, symmetry scoring, and rule-based face shape classification.
"""
import math
from typing import Any, Dict, List, Tuple
import numpy as np

from app.config import LANDMARK_INDICES, FACE_SHAPE_ARCHETYPES, FACE_SHAPE_SCALES


def euclidean_dist_2d(p1: Tuple[float, float], p2: Tuple[float, float], w: int, h: int) -> float:
    """Calculate Euclidean distance in image pixel units."""
    x1, y1 = p1[0] * w, p1[1] * h
    x2, y2 = p2[0] * w, p2[1] * h
    return math.hypot(x2 - x1, y2 - y1)


def compute_facial_symmetry(landmarks: List[Any], w: int, h: int) -> float:
    """
    Compute facial symmetry score (0.0 to 1.0) by comparing horizontal distances
    of bilateral landmark pairs to the central facial midline.
    """
    bridge_x = landmarks[LANDMARK_INDICES["nose_bridge"]].x * w
    chin_x = landmarks[LANDMARK_INDICES["chin"]].x * w
    midline_x = (bridge_x + chin_x) / 2.0

    pairs = [
        (LANDMARK_INDICES["left_pupil"], LANDMARK_INDICES["right_pupil"]),
        (LANDMARK_INDICES["left_face_edge"], LANDMARK_INDICES["right_face_edge"]),
        (LANDMARK_INDICES["left_forehead_edge"], LANDMARK_INDICES["right_forehead_edge"]),
        (LANDMARK_INDICES["left_jaw_edge"], LANDMARK_INDICES["right_jaw_edge"]),
        (LANDMARK_INDICES["left_mouth_corner"], LANDMARK_INDICES["right_mouth_corner"]),
        (LANDMARK_INDICES["left_nose_edge"], LANDMARK_INDICES["right_nose_edge"])
    ]

    asymmetries = []
    for l_idx, r_idx in pairs:
        lx = landmarks[l_idx].x * w
        rx = landmarks[r_idx].x * w
        d_left = abs(midline_x - lx)
        d_right = abs(rx - midline_x)
        denom = d_left + d_right
        if denom > 1e-3:
            asymmetry = abs(d_left - d_right) / denom
            asymmetries.append(asymmetry)

    if not asymmetries:
        return 0.85

    mean_asym = float(np.mean(asymmetries))
    symmetry_score = float(np.clip(1.0 - mean_asym * 2.0, 0.0, 1.0))
    return round(symmetry_score, 3)


def classify_face_shape(
    face_ratio: float,
    jaw_ratio: float,
    forehead_ratio: float
) -> Tuple[str, float]:
    """
    Classify facial shape using rule-based archetype distance metrics.
    Confidence reflects both proximity to the best archetype and separation from the runner-up.
    
    Returns:
        (shape_label, confidence_score [0.0 - 1.0])
    """
    s_fr = FACE_SHAPE_SCALES["face_ratio_scale"]
    s_jr = FACE_SHAPE_SCALES["jaw_ratio_scale"]
    s_fhr = FACE_SHAPE_SCALES["forehead_ratio_scale"]

    distances: List[Tuple[str, float]] = []
    for name, (ideal_fr, ideal_jr, ideal_fhr) in FACE_SHAPE_ARCHETYPES.items():
        dist = (
            ((face_ratio - ideal_fr) / s_fr) ** 2 +
            ((jaw_ratio - ideal_jr) / s_jr) ** 2 +
            ((forehead_ratio - ideal_fhr) / s_fhr) ** 2
        )
        distances.append((name, dist))

    distances.sort(key=lambda x: x[1])
    best_shape, min_dist = distances[0]
    runner_up_shape, second_dist = distances[1]

    # Proximity score (0.0 to 1.0)
    proximity = math.exp(-0.35 * min_dist)
    
    # Boundary separation margin (dist_runner_up - dist_best)
    margin = second_dist - min_dist
    margin_factor = 1.0 - math.exp(-0.5 * margin)  # 0 at boundary, ~1.0 when clearly separated

    # Composite confidence: high when close to center AND well separated from boundary
    composite_conf = 0.50 + 0.30 * proximity + 0.15 * margin_factor
    confidence = round(float(np.clip(composite_conf, 0.50, 0.95)), 2)
    
    return best_shape, confidence


def analyze_face_geometry(landmarks: List[Any], img_w: int, img_h: int) -> Dict[str, Any]:
    """
    Extract facial measurements, calculate proportional ratios, symmetry, and classify shape.
    """
    def pt(idx: int) -> Tuple[float, float]:
        return landmarks[idx].x, landmarks[idx].y

    face_w = euclidean_dist_2d(pt(LANDMARK_INDICES["left_face_edge"]), pt(LANDMARK_INDICES["right_face_edge"]), img_w, img_h)
    face_h = euclidean_dist_2d(pt(LANDMARK_INDICES["top_forehead"]), pt(LANDMARK_INDICES["chin"]), img_w, img_h)
    jaw_w = euclidean_dist_2d(pt(LANDMARK_INDICES["left_jaw_edge"]), pt(LANDMARK_INDICES["right_jaw_edge"]), img_w, img_h)
    forehead_w = euclidean_dist_2d(pt(LANDMARK_INDICES["left_forehead_edge"]), pt(LANDMARK_INDICES["right_forehead_edge"]), img_w, img_h)
    eye_dist = euclidean_dist_2d(pt(LANDMARK_INDICES["left_pupil"]), pt(LANDMARK_INDICES["right_pupil"]), img_w, img_h)
    nose_w = euclidean_dist_2d(pt(LANDMARK_INDICES["left_nose_edge"]), pt(LANDMARK_INDICES["right_nose_edge"]), img_w, img_h)
    lip_w = euclidean_dist_2d(pt(LANDMARK_INDICES["left_mouth_corner"]), pt(LANDMARK_INDICES["right_mouth_corner"]), img_w, img_h)

    safe_face_w = max(face_w, 1.0)

    face_ratio = round(face_h / safe_face_w, 2)
    jaw_width_to_face_width = round(jaw_w / safe_face_w, 2)
    forehead_width_to_face_width = round(forehead_w / safe_face_w, 2)
    eye_distance_to_face_width = round(eye_dist / safe_face_w, 2)
    nose_width_to_face_width = round(nose_w / safe_face_w, 2)
    lip_width_to_face_width = round(lip_w / safe_face_w, 2)

    symmetry_score = compute_facial_symmetry(landmarks, img_w, img_h)

    shape, shape_confidence = classify_face_shape(
        face_ratio, jaw_width_to_face_width, forehead_width_to_face_width
    )

    return {
        "shape": shape,
        "shape_confidence": shape_confidence,
        "symmetry_score": symmetry_score,
        "face_ratio": face_ratio,
        "ratios": {
            "jaw_width_to_face_width": jaw_width_to_face_width,
            "forehead_width_to_face_width": forehead_width_to_face_width,
            "eye_distance_to_face_width": eye_distance_to_face_width,
            "nose_width_to_face_width": nose_width_to_face_width,
            "lip_width_to_face_width": lip_width_to_face_width,
        }
    }
