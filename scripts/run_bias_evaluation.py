"""
Bias and Performance Evaluation Harness (Phase 5 Section 3 & 4).
Builds a diverse 24-image evaluation dataset spanning Fitzpatrick skin tones (I-VI),
lighting variations, face shapes, and surface skin conditions.
Runs the full computer vision and rules pipeline, reporting empirical distributions.
"""
import os
import sys
import json
import time
import math
import numpy as np
import cv2
from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.pipeline.face_detect import get_face_landmarks, ensure_model_downloaded
from app.pipeline.quality import validate_image_quality
from app.pipeline.geometry import analyze_face_geometry
from app.pipeline.skin import analyze_skin_characteristics
from app.rules.engine import evaluate as evaluate_rules
from app.rules.recommendations import REPORT_DISCLAIMER

EVAL_DIR = BASE_DIR / "tests" / "evaluation_dataset"
EVAL_DIR.mkdir(parents=True, exist_ok=True)


def get_base_portrait() -> np.ndarray:
    """Load or construct high quality base portrait."""
    sample_path = BASE_DIR / "tests" / "sample_images" / "good_lighting" / "sample_good1.jpg"
    if not sample_path.exists():
        sample_path = BASE_DIR / "tests" / "sample_images" / "sample1.jpg"
    
    img = cv2.imread(str(sample_path))
    if img is None:
        raise RuntimeError(f"Base portrait not found at {sample_path}")
    return img


def create_eval_dataset():
    """Generates 24 precisely calibrated evaluation images across 4 distinct cohorts."""
    base_bgr = get_base_portrait()
    base_rgb = cv2.cvtColor(base_bgr, cv2.COLOR_BGR2RGB)
    
    # Get base face mask for regional synthesis
    face_count, landmarks, _ = get_face_landmarks(base_rgb)
    if face_count == 0:
        raise RuntimeError("Base image face detection failed.")

    h, w = base_bgr.shape[:2]

    # Create skin mask polygon
    from app.config import LANDMARK_INDICES
    oval_pts = np.array([
        (int(landmarks[idx].x * w), int(landmarks[idx].y * h))
        for idx in LANDMARK_INDICES["face_oval"]
    ], dtype=np.int32)

    face_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(face_mask, [oval_pts], 255)
    
    # Exclude eyes and lips from mask for natural tone shifting
    for part in ["left_eye", "right_eye", "lips_outer"]:
        pts = np.array([
            (int(landmarks[idx].x * w), int(landmarks[idx].y * h))
            for idx in LANDMARK_INDICES[part]
        ], dtype=np.int32)
        cv2.fillPoly(face_mask, [pts], 0)
        
    face_mask_soft = cv2.GaussianBlur(face_mask, (25, 25), 0) / 255.0
    face_mask_soft3 = np.repeat(face_mask_soft[:, :, np.newaxis], 3, axis=2)

    eval_items = []

    # =========================================================================
    # Cohort 1: Fitzpatrick Skin Tone Spectrum (Types I through VI)
    # =========================================================================
    tone_shifts = [
        ("fitz_1_fair_pale", 1.25, [1.05, 1.02, 1.08], "Fitzpatrick I (Pale/Fair)", "I"),
        ("fitz_2_fair_rosy", 1.12, [1.02, 1.00, 1.08], "Fitzpatrick II (Fair Rosy)", "II"),
        ("fitz_3_medium_warm", 0.98, [0.95, 1.00, 1.04], "Fitzpatrick III (Medium Warm)", "III"),
        ("fitz_4_olive_tan", 0.85, [0.88, 0.96, 1.02], "Fitzpatrick IV (Olive/Tan)", "IV"),
        ("fitz_5_brown_deep", 0.62, [0.72, 0.84, 0.95], "Fitzpatrick V (Rich Brown)", "V"),
        ("fitz_6_dark_ebony", 0.45, [0.58, 0.72, 0.85], "Fitzpatrick VI (Deep Ebony)", "VI"),
    ]

    for name, lum_scale, bgr_mult, label, fitz_type in tone_shifts:
        # Convert to LAB for luminance adjustment within skin area
        lab = cv2.cvtColor(base_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
        lab[:, :, 0] = lab[:, :, 0] * (1.0 + (lum_scale - 1.0) * face_mask_soft)
        lab[:, :, 0] = np.clip(lab[:, :, 0], 10, 245)
        shifted = cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR).astype(np.float32)
        
        # Color multiplier
        for c in range(3):
            shifted[:, :, c] = shifted[:, :, c] * (1.0 + (bgr_mult[c] - 1.0) * face_mask_soft)
        
        out_bgr = np.clip(shifted, 0, 255).astype(np.uint8)
        file_path = EVAL_DIR / f"{name}.jpg"
        cv2.imwrite(str(file_path), out_bgr)
        eval_items.append({
            "id": name,
            "filename": f"{name}.jpg",
            "path": str(file_path),
            "cohort": "skin_tone_spectrum",
            "label": label,
            "fitzpatrick_group": fitz_type,
            "lighting_condition": "balanced",
        })

    # =========================================================================
    # Cohort 2: Lighting & Illuminant Variations
    # =========================================================================
    lighting_variants = [
        ("light_balanced_5500k", lambda b: b, "Balanced 5500K Studio", "II/III", "optimal"),
        ("light_warm_tungsten", lambda b: cv2.convertScaleAbs(b, alpha=1.0, beta=0) * np.array([0.75, 0.95, 1.25]), "Warm Tungsten (2700K)", "II/III", "warm"),
        ("light_cool_fluorescent", lambda b: cv2.convertScaleAbs(b, alpha=1.0, beta=0) * np.array([1.25, 1.05, 0.85]), "Cool Fluorescent (6500K)", "II/III", "cool"),
        ("light_low_exposure", lambda b: cv2.convertScaleAbs(b, alpha=0.55, beta=-20), "Low Exposure (Dim Room)", "II/III", "low_light"),
        ("light_high_exposure", lambda b: cv2.convertScaleAbs(b, alpha=1.40, beta=35), "High Exposure (Direct Sunlight)", "II/III", "bright"),
        ("light_directional_shadow", lambda b: apply_directional_shadow(b), "Directional Side Lighting", "II/III", "shadowed"),
    ]

    for name, transform_fn, label, fitz_type, light_cond in lighting_variants:
        out_bgr = np.clip(transform_fn(base_bgr.copy()), 0, 255).astype(np.uint8)
        file_path = EVAL_DIR / f"{name}.jpg"
        cv2.imwrite(str(file_path), out_bgr)
        eval_items.append({
            "id": name,
            "filename": f"{name}.jpg",
            "path": str(file_path),
            "cohort": "lighting_variation",
            "label": label,
            "fitzpatrick_group": fitz_type,
            "lighting_condition": light_cond,
        })

    # =========================================================================
    # Cohort 3: Facial Geometry & Morphology (Aspect Ratios)
    # =========================================================================
    shapes = [
        ("shape_oval_ref", 1.0, 1.0, "Oval Morphology", "II/III"),
        ("shape_round_wide", 1.15, 0.92, "Round Morphology (Wider Cheekbones)", "II/III"),
        ("shape_square_jaw", 1.18, 0.95, "Square Morphology (Prominent Jaw)", "II/III"),
        ("shape_heart_taper", 0.90, 1.05, "Heart Morphology (Narrower Chin)", "II/III"),
        ("shape_diamond_narrow", 0.92, 1.10, "Diamond Morphology (Prominent Zygoma)", "II/III"),
        ("shape_rectangle_long", 0.88, 1.20, "Rectangle Morphology (Elongated Vertical)", "II/III"),
    ]

    for name, sx, sy, label, fitz_type in shapes:
        new_w, new_h = int(w * sx), int(h * sy)
        resized = cv2.resize(base_bgr, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        # Pad or crop to maintain uniform frame
        canvas = np.zeros_like(base_bgr)
        ch, cw = canvas.shape[:2]
        pad_y = max(0, (ch - new_h) // 2)
        pad_x = max(0, (cw - new_w) // 2)
        
        src_y1 = max(0, (new_h - ch) // 2)
        src_x1 = max(0, (new_w - cw) // 2)
        src_y2 = src_y1 + min(ch, new_h)
        src_x2 = src_x1 + min(cw, new_w)
        
        dst_y1 = pad_y
        dst_x1 = pad_x
        dst_y2 = dst_y1 + (src_y2 - src_y1)
        dst_x2 = dst_x1 + (src_x2 - src_x1)
        
        canvas[dst_y1:dst_y2, dst_x1:dst_x2] = resized[src_y1:src_y2, src_x1:src_x2]
        
        file_path = EVAL_DIR / f"{name}.jpg"
        cv2.imwrite(str(file_path), canvas)
        eval_items.append({
            "id": name,
            "filename": f"{name}.jpg",
            "path": str(file_path),
            "cohort": "facial_geometry",
            "label": label,
            "fitzpatrick_group": fitz_type,
            "lighting_condition": "balanced",
        })

    # =========================================================================
    # Cohort 4: Surface Characteristics & Skin Conditions
    # =========================================================================
    conditions = [
        ("cond_clear_optimal", lambda b: b, "Clear & Smooth Baseline", "II/III"),
        ("cond_erythema_flushed", lambda b: apply_flushed_skin(b, face_mask_soft), "Facial Erythema / Flushed Redness", "II/III"),
        ("cond_pigmentation_uneven", lambda b: apply_pigmentation_mottling(b, face_mask_soft), "Hyperpigmentation Mottling", "II/III"),
        ("cond_texture_rough", lambda b: apply_texture_noise(b, face_mask_soft), "Elevated Surface Roughness", "II/III"),
        ("cond_undereye_shade", lambda b: apply_undereye_shadow(b, landmarks, w, h), "Periorbital Under-Eye Shadow", "II/III"),
        ("cond_blemishes_spots", lambda b: apply_blemish_spots(b, landmarks, w, h), "Localized Blemish Clusters", "II/III"),
    ]

    for name, cond_fn, label, fitz_type in conditions:
        out_bgr = np.clip(cond_fn(base_bgr.copy()), 0, 255).astype(np.uint8)
        file_path = EVAL_DIR / f"{name}.jpg"
        cv2.imwrite(str(file_path), out_bgr)
        eval_items.append({
            "id": name,
            "filename": f"{name}.jpg",
            "path": str(file_path),
            "cohort": "skin_conditions",
            "label": label,
            "fitzpatrick_group": fitz_type,
            "lighting_condition": "balanced",
        })

    # Save metadata manifest
    manifest_path = EVAL_DIR / "dataset_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(eval_items, f, indent=2)
        
    return eval_items


def apply_directional_shadow(bgr: np.ndarray) -> np.ndarray:
    h, w = bgr.shape[:2]
    gradient = np.linspace(1.3, 0.4, w).astype(np.float32)
    grad_mask = np.repeat(gradient[np.newaxis, :, np.newaxis], h, axis=0)
    return (bgr.astype(np.float32) * grad_mask).clip(0, 255).astype(np.uint8)


def apply_flushed_skin(bgr: np.ndarray, face_mask: np.ndarray) -> np.ndarray:
    bgr_f = bgr.astype(np.float32)
    # Increase Red channel (BGR index 2) in facial skin
    bgr_f[:, :, 2] += 42.0 * face_mask
    bgr_f[:, :, 0] -= 10.0 * face_mask
    return bgr_f.clip(0, 255).astype(np.uint8)


def apply_pigmentation_mottling(bgr: np.ndarray, face_mask: np.ndarray) -> np.ndarray:
    h, w = bgr.shape[:2]
    noise = cv2.resize(np.random.normal(0, 22, (h // 8, w // 8)), (w, h))
    noise_blur = cv2.GaussianBlur(noise, (21, 21), 0)
    bgr_f = bgr.astype(np.float32)
    for c in range(3):
        bgr_f[:, :, c] += noise_blur * face_mask
    return bgr_f.clip(0, 255).astype(np.uint8)


def apply_texture_noise(bgr: np.ndarray, face_mask: np.ndarray) -> np.ndarray:
    h, w = bgr.shape[:2]
    high_freq = np.random.normal(0, 18, (h, w)).astype(np.float32)
    bgr_f = bgr.astype(np.float32)
    for c in range(3):
        bgr_f[:, :, c] += high_freq * face_mask
    return bgr_f.clip(0, 255).astype(np.uint8)


def apply_undereye_shadow(bgr: np.ndarray, landmarks, w, h) -> np.ndarray:
    from app.config import LANDMARK_INDICES
    shadow_mask = np.zeros((h, w), dtype=np.uint8)
    for side in ["left_under_eye", "right_under_eye"]:
        pts = np.array([
            (int(landmarks[idx].x * w), int(landmarks[idx].y * h))
            for idx in LANDMARK_INDICES[side]
        ], dtype=np.int32)
        cv2.fillPoly(shadow_mask, [pts], 255)
    shadow_soft = cv2.GaussianBlur(shadow_mask, (15, 15), 0) / 255.0
    
    bgr_f = bgr.astype(np.float32)
    for c in range(3):
        bgr_f[:, :, c] *= (1.0 - 0.40 * shadow_soft)
    return bgr_f.clip(0, 255).astype(np.uint8)


def apply_blemish_spots(bgr: np.ndarray, landmarks, w, h) -> np.ndarray:
    bgr_out = bgr.copy()
    # Draw dark reddish spots on cheek landmarks
    for idx in [117, 119, 126, 346, 348, 355]:
        cx, cy = int(landmarks[idx].x * w), int(landmarks[idx].y * h)
        cv2.circle(bgr_out, (cx, cy), 6, (40, 45, 110), -1)
        cv2.circle(bgr_out, (cx + 8, cy - 6), 4, (35, 40, 105), -1)
    return cv2.GaussianBlur(bgr_out, (3, 3), 0)


def evaluate_dataset():
    """Runs evaluation suite on all images and computes distribution metrics."""
    items = create_eval_dataset()
    ensure_model_downloaded()

    results = []

    for item in items:
        p = Path(item["path"])
        bgr_img = cv2.imread(str(p))
        rgb_img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)
        h, w = bgr_img.shape[:2]

        t0 = time.perf_counter()
        
        # 1. Detection
        t_det_start = time.perf_counter()
        face_count, landmarks, _ = get_face_landmarks(rgb_img)
        t_det = (time.perf_counter() - t_det_start) * 1000.0

        if face_count == 0:
            results.append({
                **item,
                "passed_gate": False,
                "rejection_reason": "no_face_detected",
                "timings": {"detect_ms": t_det, "total_ms": t_det}
            })
            continue

        # 2. Quality Gate
        t_gate_start = time.perf_counter()
        passed_gate, reason, failure_msg, quality_metrics, warnings = validate_image_quality(
            bgr_img, face_count, landmarks
        )
        t_gate = (time.perf_counter() - t_gate_start) * 1000.0

        if not passed_gate:
            results.append({
                **item,
                "passed_gate": False,
                "rejection_reason": reason,
                "rejection_message": failure_msg,
                "quality_metrics": quality_metrics,
                "warnings": warnings,
                "timings": {"detect_ms": t_det, "gate_ms": t_gate, "total_ms": (time.perf_counter() - t0)*1000.0}
            })
            continue

        # 3. Geometry
        t_geo_start = time.perf_counter()
        geometry_results = analyze_face_geometry(landmarks, w, h)
        t_geo = (time.perf_counter() - t_geo_start) * 1000.0

        # 4. Skin Analysis
        t_skin_start = time.perf_counter()
        skin_results, detected_regions, _ = analyze_skin_characteristics(bgr_img, landmarks)
        t_skin = (time.perf_counter() - t_skin_start) * 1000.0

        # 5. Rules Evaluation
        t_rules_start = time.perf_counter()
        rule_scores = {
            "redness_score": skin_results.get("redness_score", 0.0),
            "pigmentation_score": skin_results.get("pigmentation_score", 0.0),
            "texture_score": skin_results.get("texture_score", 0.0),
            "under_eye_score": skin_results.get("under_eye_score", 0.0),
            "visible_spots": skin_results.get("visible_spots", 0),
            "image_quality_score": quality_metrics.get("score", 1.0),
        }
        triggered_ids = evaluate_rules(rule_scores)
        t_rules = (time.perf_counter() - t_rules_start) * 1000.0

        t_total = (time.perf_counter() - t0) * 1000.0

        results.append({
            **item,
            "passed_gate": True,
            "quality_metrics": quality_metrics,
            "warnings": warnings,
            "face_shape": geometry_results.get("shape"),
            "face_symmetry": geometry_results.get("symmetry_score"),
            "face_ratios": geometry_results.get("ratios"),
            "skin_scores": {
                "redness": round(skin_results.get("redness_score", 0.0), 3),
                "pigmentation": round(skin_results.get("pigmentation_score", 0.0), 3),
                "texture": round(skin_results.get("texture_score", 0.0), 3),
                "under_eye": round(skin_results.get("under_eye_score", 0.0), 3),
                "visible_spots": skin_results.get("visible_spots", 0),
            },
            "triggered_rules": triggered_ids,
            "timings": {
                "detect_ms": round(t_det, 1),
                "gate_ms": round(t_gate, 1),
                "geometry_ms": round(t_geo, 1),
                "skin_ms": round(t_skin, 1),
                "rules_ms": round(t_rules, 1),
                "total_ms": round(t_total, 1),
            }
        })

    # Write evaluation raw results
    out_file = EVAL_DIR / "evaluation_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    results = evaluate_dataset()
    print(f"Evaluated {len(results)} images. Saved to {EVAL_DIR / 'evaluation_results.json'}")
