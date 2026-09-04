"""
Longitudinal scan comparison service (Phase 4, Section 5).
Calculates metric deltas, checks face-shape stability, and computes
comparability warnings for mismatched capture conditions.
"""
from typing import List, Optional, Dict, Any
from app.schemas import (
    ComparisonDeltaSchema,
    ScanTimelineItem,
    ScanComparisonResponse,
)


def evaluate_comparability_warning(timeline: List[ScanTimelineItem], raw_scans: List[Any]) -> Optional[str]:
    """
    Detects capture condition mismatches that make trend comparisons unreliable.
    Flags:
      1. Large image quality difference (>= 0.20)
      2. Large lighting quality difference (>= 0.25)
      3. Large pose angle difference (>= 0.25)
    """
    if len(raw_scans) < 2:
        return None

    quality_scores = []
    lighting_scores = []
    pose_scores = []

    for s in raw_scans:
        if isinstance(s, dict):
            q = s.get("image_quality") or {}
        else:
            q = getattr(s, "image_quality", None) or {}

        quality_scores.append(float(q.get("score", 0.0)))
        lighting_scores.append(float(q.get("lighting", 0.0)))
        pose_scores.append(float(q.get("pose", 0.0)))

    max_q_gap = max(quality_scores) - min(quality_scores)
    max_light_gap = max(lighting_scores) - min(lighting_scores)
    max_pose_gap = max(pose_scores) - min(pose_scores)

    warnings = []
    if max_q_gap >= 0.20:
        warnings.append(
            "Image quality differs significantly between these scans; "
            "trend may reflect capture conditions rather than actual change."
        )
    elif max_light_gap >= 0.25:
        warnings.append(
            "Lighting conditions differ noticeably between scans; "
            "surface contrast and tone variations should be interpreted with caution."
        )
    elif max_pose_gap >= 0.25:
        warnings.append(
            "Head pose or camera angle varies significantly between scans, "
            "which may influence regional perspective."
        )

    return " ".join(warnings) if warnings else None


def compare_scan_records(scans: List[Any]) -> ScanComparisonResponse:
    """
    Compare 2 or more scan models or scan dicts in chronological order.
    Returns ScanComparisonResponse with deltas, face_shape_stable, and comparability_warning.
    """
    if len(scans) < 2:
        raise ValueError("At least 2 scans are required for comparison.")

    # Sort chronologically (oldest first)
    sorted_scans = sorted(
        scans,
        key=lambda s: getattr(s, "created_at", None) or s.get("created_at")
    )

    timeline: List[ScanTimelineItem] = []
    face_shapes = []

    for s in sorted_scans:
        s_id = str(getattr(s, "id", None) or s.get("id"))
        created_at = getattr(s, "created_at", None) or s.get("created_at")
        created_str = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at)

        iq = getattr(s, "image_quality", None) or s.get("image_quality") or {}
        face = getattr(s, "face_metrics", None) or s.get("face") or {}
        skin = getattr(s, "skin_metrics", None) or s.get("skin") or {}

        shape = str(face.get("shape", "unknown"))
        face_shapes.append(shape.lower())

        timeline.append(ScanTimelineItem(
            scan_id=s_id,
            created_at=created_str,
            quality_score=round(float(iq.get("score", 0.0)), 3),
            face_shape=shape,
            redness_score=round(float(skin.get("redness_score", 0.0)), 3),
            pigmentation_score=round(float(skin.get("pigmentation_score", 0.0)), 3),
            texture_score=round(float(skin.get("texture_score", 0.0)), 3),
            under_eye_score=round(float(skin.get("under_eye_score", 0.0)), 3),
            visible_spots=int(skin.get("visible_spots", 0)),
        ))

    oldest = timeline[0]
    newest = timeline[-1]

    # Calculate net deltas (newest - oldest)
    deltas = ComparisonDeltaSchema(
        redness_score=round(newest.redness_score - oldest.redness_score, 3),
        pigmentation_score=round(newest.pigmentation_score - oldest.pigmentation_score, 3),
        texture_score=round(newest.texture_score - oldest.texture_score, 3),
        under_eye_score=round(newest.under_eye_score - oldest.under_eye_score, 3),
        visible_spots=newest.visible_spots - oldest.visible_spots,
    )

    # Face shape stability: all scans in sequence share the same shape
    face_shape_stable = len(set(face_shapes)) == 1

    # Comparability warning for capture mismatch
    warning = evaluate_comparability_warning(timeline, sorted_scans)

    return ScanComparisonResponse(
        scans_compared=[t.scan_id for t in timeline],
        comparability_warning=warning,
        deltas=deltas,
        face_shape_stable=face_shape_stable,
        timeline=timeline,
    )
