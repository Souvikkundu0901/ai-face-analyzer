"""
Visual debug overlay renderer for facial landmarks, skin boundaries, flagged regions,
and quality-gate rejection diagnostics.
"""
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from app.config import LANDMARK_INDICES
from app.pipeline.skin import get_polygon_points


def get_confidence_color(conf: float) -> Tuple[int, int, int]:
    """
    Interpolate BGR color for spot confidence:
    Low confidence (~0.55) -> Green
    Medium confidence (~0.75) -> Amber / Yellow
    High confidence (~0.90+) -> Red / Coral
    """
    t = float(np.clip((conf - 0.55) / 0.40, 0.0, 1.0))
    if t < 0.5:
        # Green (0, 220, 80) to Yellow (0, 215, 255)
        local_t = t * 2.0
        b = int(0 * (1 - local_t) + 0 * local_t)
        g = int(220 * (1 - local_t) + 215 * local_t)
        r = int(80 * (1 - local_t) + 255 * local_t)
    else:
        # Yellow (0, 215, 255) to Red (30, 40, 240)
        local_t = (t - 0.5) * 2.0
        b = int(0 * (1 - local_t) + 30 * local_t)
        g = int(215 * (1 - local_t) + 40 * local_t)
        r = int(255 * (1 - local_t) + 240 * local_t)
    return (b, g, r)


def render_debug_overlay(
    bgr_img: np.ndarray,
    landmarks: List[Any],
    regions: List[Dict[str, Any]],
    geometry_info: Optional[Dict[str, Any]] = None,
    skin_info: Optional[Dict[str, Any]] = None,
    skin_mask: Optional[np.ndarray] = None
) -> bytes:
    """
    Render visual debug overlay with landmarks, masked skin boundary,
    confidence-colored spot circles, and ratio-annotated shape label.
    Returns PNG image bytes.
    """
    h, w = bgr_img.shape[:2]
    overlay = bgr_img.copy()

    # 1. Draw precise skin mask boundary
    if skin_mask is not None:
        contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(overlay, contours, -1, (0, 255, 140), 2, cv2.LINE_AA)

    # 2. Draw subtle facial landmark points
    for idx, lm in enumerate(landmarks):
        px = int(np.clip(lm.x * w, 0, w - 1))
        py = int(np.clip(lm.y * h, 0, h - 1))
        
        if idx in (LANDMARK_INDICES["chin"], LANDMARK_INDICES["top_forehead"],
                   LANDMARK_INDICES["left_face_edge"], LANDMARK_INDICES["right_face_edge"]):
            cv2.circle(overlay, (px, py), 4, (0, 240, 255), -1, cv2.LINE_AA)
        elif idx in (LANDMARK_INDICES["left_pupil"], LANDMARK_INDICES["right_pupil"]):
            cv2.circle(overlay, (px, py), 4, (255, 120, 0), -1, cv2.LINE_AA)
        elif idx % 4 == 0:
            cv2.circle(overlay, (px, py), 1, (210, 210, 210), -1, cv2.LINE_AA)

    # 3. Draw under-eye measurement zones
    left_ue_pts = get_polygon_points(landmarks, LANDMARK_INDICES["left_under_eye"], w, h)
    right_ue_pts = get_polygon_points(landmarks, LANDMARK_INDICES["right_under_eye"], w, h)
    if len(left_ue_pts) >= 3:
        cv2.polylines(overlay, [left_ue_pts], True, (255, 190, 0), 1, cv2.LINE_AA)
    if len(right_ue_pts) >= 3:
        cv2.polylines(overlay, [right_ue_pts], True, (255, 190, 0), 1, cv2.LINE_AA)

    # 4. Draw detected spot-like regions colored by confidence
    max_dim = max(w, h)
    for reg in regions:
        cx = int(reg["x"] * w)
        cy = int(reg["y"] * h)
        radius = max(3, int(reg["radius"] * max_dim))
        conf = reg.get("confidence", 0.70)
        color = get_confidence_color(conf)

        cv2.circle(overlay, (cx, cy), radius, color, 2, cv2.LINE_AA)
        cv2.circle(overlay, (cx, cy), 1, color, -1, cv2.LINE_AA)

    # 5. Blend overlay with original
    alpha = 0.85
    blended = cv2.addWeighted(overlay, alpha, bgr_img, 1.0 - alpha, 0)

    # 6. Render informational HUD banner at top
    bar_h = 38
    hud_bar = np.zeros((bar_h, w, 3), dtype=np.uint8)
    hud_bar[:] = (20, 22, 28)
    
    info_text = "AI Face Analyzer (v0.2.0)"
    if geometry_info:
        shape_name = geometry_info.get("shape", "").title()
        conf_pct = int(geometry_info.get("shape_confidence", 0.8) * 100)
        ratios = geometry_info.get("ratios", {})
        info_text += f" | Shape: {shape_name} ({conf_pct}%) [H/W: {geometry_info.get('face_ratio', 0):.2f}, Jaw: {ratios.get('jaw_width_to_face_width', 0):.2f}]"
    if skin_info:
        info_text += f" | Spots: {skin_info.get('visible_spots', 0)} | Redness: {skin_info.get('redness_score', 0):.2f}"

    cv2.putText(hud_bar, info_text, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (240, 240, 245), 1, cv2.LINE_AA)
    final_img = np.vstack([hud_bar, blended])

    success, buffer = cv2.imencode(".png", final_img)
    if not success:
        raise ValueError("Failed to encode overlay image to PNG.")
    return buffer.tobytes()


def render_rejection_debug_overlay(
    bgr_img: np.ndarray,
    reason: str,
    message: str,
    metrics: Optional[Dict[str, Any]] = None
) -> bytes:
    """
    Render diagnostic overlay explaining why an image failed the quality gate.
    Returns PNG image bytes.
    """
    h, w = bgr_img.shape[:2]
    diag_img = bgr_img.copy()

    # Red tinted banner overlay
    banner_h = min(120, max(80, int(h * 0.2)))
    banner = np.zeros((banner_h, w, 3), dtype=np.uint8)
    banner[:] = (15, 15, 120)  # dark crimson

    cv2.putText(
        banner,
        f"QUALITY GATE REJECTED: {reason.upper()}",
        (16, 32),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA
    )

    # Wrap message text
    cv2.putText(
        banner,
        message[:90],
        (16, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (220, 220, 240),
        1,
        cv2.LINE_AA
    )

    if metrics:
        metric_str = f"Sharpness: {metrics.get('sharpness', 0):.2f} | Lighting: {metrics.get('lighting', 0):.2f} | Pose: {metrics.get('pose', 0):.2f}"
        cv2.putText(
            banner,
            metric_str,
            (16, 88),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.40,
            (180, 230, 255),
            1,
            cv2.LINE_AA
        )

    final_img = np.vstack([banner, diag_img])
    success, buffer = cv2.imencode(".png", final_img)
    if not success:
        raise ValueError("Failed to encode rejection debug overlay.")
    return buffer.tobytes()
