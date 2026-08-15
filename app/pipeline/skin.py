"""
Skin characteristic heuristics using classical OpenCV algorithms.
Computes redness, pigmentation variation, texture roughness, under-eye shade, and spot-like regions.
"""
from typing import Any, Dict, List, Tuple
import cv2
import numpy as np

from app.config import (
    LANDMARK_INDICES,
    MASK_CONFIG,
    REDNESS_CONFIG,
    PIGMENTATION_CONFIG,
    TEXTURE_CONFIG,
    UNDER_EYE_CONFIG,
    SPOT_CONFIG,
)
from app.pipeline.regions import create_region_dict


def get_polygon_points(landmarks: List[Any], indices: List[int], w: int, h: int) -> np.ndarray:
    """Extract (x, y) integer pixel coordinates for a sequence of landmark indices."""
    pts = []
    for idx in indices:
        lm = landmarks[idx]
        pts.append([int(np.clip(lm.x * w, 0, w - 1)), int(np.clip(lm.y * h, 0, h - 1))])
    return np.array(pts, dtype=np.int32)


def generate_skin_mask(landmarks: List[Any], img_w: int, img_h: int) -> np.ndarray:
    """
    Build an accurate skin mask by including the full facial contour
    and excluding eyes, eyebrows, lips, and nostrils.
    """
    mask = np.zeros((img_h, img_w), dtype=np.uint8)

    # 1. Base face oval
    face_pts = get_polygon_points(landmarks, LANDMARK_INDICES["face_oval"], img_w, img_h)
    cv2.fillPoly(mask, [face_pts], 255)

    # 2. Exclude non-skin regions with slight dilation
    dil_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, MASK_CONFIG["dilation_kernel_size"])
    ero_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, MASK_CONFIG["erosion_kernel_size"])

    exclusion_keys = [
        "left_eye",
        "right_eye",
        "left_eyebrow",
        "right_eyebrow",
        "lips_outer",
        "nostrils"
    ]

    for key in exclusion_keys:
        feature_pts = get_polygon_points(landmarks, LANDMARK_INDICES[key], img_w, img_h)
        if len(feature_pts) >= 3:
            ex_mask = np.zeros((img_h, img_w), dtype=np.uint8)
            cv2.fillPoly(ex_mask, [feature_pts], 255)
            ex_mask = cv2.dilate(ex_mask, dil_kernel, iterations=MASK_CONFIG["dilation_iterations"])
            mask[ex_mask > 0] = 0

    # 3. Erode outer face boundary to remove background hair / boundary edges
    mask = cv2.erode(mask, ero_kernel, iterations=MASK_CONFIG["erosion_iterations"])
    return mask


def analyze_redness(lab_img: np.ndarray, skin_mask: np.ndarray, landmarks: List[Any], w: int, h: int) -> float:
    """
    Compute normalized redness score (0.0 - 1.0) using CIELAB a* channel in skin zones.
    """
    a_channel = lab_img[:, :, 1]
    
    skin_a_values = a_channel[skin_mask > 0]
    if len(skin_a_values) == 0:
        return 0.0

    mean_a = float(np.mean(skin_a_values))

    # Regional cheek evaluation
    left_cheek_pts = get_polygon_points(landmarks, LANDMARK_INDICES["left_cheek"], w, h)
    right_cheek_pts = get_polygon_points(landmarks, LANDMARK_INDICES["right_cheek"], w, h)

    cheek_mask = np.zeros((h, w), dtype=np.uint8)
    if len(left_cheek_pts) >= 3:
        cv2.fillPoly(cheek_mask, [left_cheek_pts], 255)
    if len(right_cheek_pts) >= 3:
        cv2.fillPoly(cheek_mask, [right_cheek_pts], 255)
    cheek_mask = cv2.bitwise_and(cheek_mask, skin_mask)

    cheek_a_values = a_channel[cheek_mask > 0]
    if len(cheek_a_values) > 50:
        mean_cheek_a = float(np.mean(cheek_a_values))
        combined_a = (REDNESS_CONFIG["cheek_weight"] * mean_cheek_a + 
                      REDNESS_CONFIG["face_weight"] * mean_a)
    else:
        combined_a = mean_a

    norm_redness = float(np.clip(
        (combined_a - REDNESS_CONFIG["cielab_a_baseline"]) / REDNESS_CONFIG["cielab_a_range"],
        0.0, 1.0
    ))
    return round(norm_redness, 2)


def analyze_pigmentation(lab_img: np.ndarray, skin_mask: np.ndarray) -> float:
    """
    Compute pigmentation variation score (0.0 - 1.0) using luminance (L*) standard deviation
    and local patch contrast on the skin mask.
    """
    l_channel = lab_img[:, :, 0]
    skin_l_values = l_channel[skin_mask > 0]
    if len(skin_l_values) == 0:
        return 0.0

    global_std = float(np.std(skin_l_values))

    # Local median filtering
    ksize = PIGMENTATION_CONFIG["median_blur_ksize"]
    local_blur = cv2.medianBlur(l_channel, ksize)
    local_diff = cv2.absdiff(l_channel, local_blur)
    local_skin_diff = local_diff[skin_mask > 0]
    local_mean_diff = float(np.mean(local_skin_diff)) if len(local_skin_diff) > 0 else 0.0

    score = (
        ((global_std - PIGMENTATION_CONFIG["std_baseline"]) / PIGMENTATION_CONFIG["std_scale"]) * PIGMENTATION_CONFIG["global_weight"] +
        ((local_mean_diff - PIGMENTATION_CONFIG["local_diff_baseline"]) / PIGMENTATION_CONFIG["local_diff_scale"]) * PIGMENTATION_CONFIG["local_weight"]
    )
    norm_pigmentation = float(np.clip(score, 0.0, 1.0))
    return round(norm_pigmentation, 2)


def analyze_texture(gray_img: np.ndarray, skin_mask: np.ndarray) -> float:
    """
    Compute skin surface texture roughness score (0.0 - 1.0) using high-frequency edge response.
    """
    cfg = TEXTURE_CONFIG
    smoothed = cv2.bilateralFilter(
        gray_img,
        d=cfg["bilateral_d"],
        sigmaColor=cfg["bilateral_sigma_color"],
        sigmaSpace=cfg["bilateral_sigma_space"]
    )
    high_freq = cv2.absdiff(gray_img, smoothed)
    
    laplacian = cv2.Laplacian(smoothed, cv2.CV_32F)
    lap_mag = np.abs(laplacian)

    skin_high_freq = high_freq[skin_mask > 0]
    skin_lap = lap_mag[skin_mask > 0]
    
    if len(skin_high_freq) == 0:
        return 0.0

    mean_hf = float(np.mean(skin_high_freq))
    mean_lap = float(np.mean(skin_lap))

    hf_score = (mean_hf - cfg["hf_baseline"]) / cfg["hf_scale"]
    lap_score = (mean_lap - cfg["lap_baseline"]) / cfg["lap_scale"]
    combined = cfg["hf_weight"] * hf_score + cfg["lap_weight"] * lap_score
    
    norm_texture = float(np.clip(combined, 0.0, 1.0))
    return round(norm_texture, 2)


def analyze_under_eye(lab_img: np.ndarray, skin_mask: np.ndarray, landmarks: List[Any], w: int, h: int) -> float:
    """
    Compute under-eye darkness / shade contrast score (0.0 - 1.0) comparing under-eye zones to adjacent cheek zones.
    """
    l_channel = lab_img[:, :, 0]

    left_ue_pts = get_polygon_points(landmarks, LANDMARK_INDICES["left_under_eye"], w, h)
    right_ue_pts = get_polygon_points(landmarks, LANDMARK_INDICES["right_under_eye"], w, h)

    left_ch_pts = get_polygon_points(landmarks, LANDMARK_INDICES["left_cheek"], w, h)
    right_ch_pts = get_polygon_points(landmarks, LANDMARK_INDICES["right_cheek"], w, h)

    ue_mask = np.zeros((h, w), dtype=np.uint8)
    if len(left_ue_pts) >= 3:
        cv2.fillPoly(ue_mask, [left_ue_pts], 255)
    if len(right_ue_pts) >= 3:
        cv2.fillPoly(ue_mask, [right_ue_pts], 255)
    ue_mask = cv2.bitwise_and(ue_mask, skin_mask)

    ch_mask = np.zeros((h, w), dtype=np.uint8)
    if len(left_ch_pts) >= 3:
        cv2.fillPoly(ch_mask, [left_ch_pts], 255)
    if len(right_ch_pts) >= 3:
        cv2.fillPoly(ch_mask, [right_ch_pts], 255)
    ch_mask = cv2.bitwise_and(ch_mask, skin_mask)

    ue_lum = l_channel[ue_mask > 0]
    ch_lum = l_channel[ch_mask > 0]

    if len(ue_lum) < 20 or len(ch_lum) < 20:
        return 0.0

    mean_ue = float(np.mean(ue_lum))
    mean_ch = float(np.mean(ch_lum))

    deficit = max(0.0, (mean_ch - mean_ue) / max(mean_ch, 1.0))
    norm_score = float(np.clip(
        (deficit - UNDER_EYE_CONFIG["min_deficit"]) / UNDER_EYE_CONFIG["deficit_range"],
        0.0, 1.0
    ))
    return round(norm_score, 2)


def detect_spot_regions(
    bgr_img: np.ndarray,
    lab_img: np.ndarray,
    skin_mask: np.ndarray
) -> List[Dict[str, Any]]:
    """
    Detect localized spot-like regions within the masked skin area
    using adaptive color and luminance difference filtering with real prominence-based confidence.
    """
    h, w = bgr_img.shape[:2]
    l_channel = lab_img[:, :, 0]
    a_channel = lab_img[:, :, 1]

    bg_l = cv2.GaussianBlur(l_channel, SPOT_CONFIG["blur_ksize"], 0)
    bg_a = cv2.GaussianBlur(a_channel, SPOT_CONFIG["blur_ksize"], 0)

    dark_contrast = cv2.subtract(bg_l, l_channel)
    red_contrast = cv2.subtract(a_channel, bg_a)

    combined_response = cv2.addWeighted(dark_contrast, 0.5, red_contrast, 0.5, 0)
    combined_response[skin_mask == 0] = 0

    if np.any(skin_mask > 0):
        threshold_val = int(max(
            SPOT_CONFIG["min_percentile_val"],
            np.percentile(combined_response[skin_mask > 0], SPOT_CONFIG["percentile_threshold"])
        ))
    else:
        threshold_val = 25

    _, spot_bin = cv2.threshold(combined_response, threshold_val, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    spot_bin = cv2.morphologyEx(spot_bin, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(spot_bin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    regions: List[Dict[str, Any]] = []
    min_area = max(4.0, (w * h) * SPOT_CONFIG["min_area_ratio"])
    max_area = max(50.0, (w * h) * SPOT_CONFIG["max_area_ratio"])

    # Local skin standard deviation for baseline noise comparison
    skin_noise_std = float(np.std(combined_response[skin_mask > 0])) if np.any(skin_mask > 0) else 5.0
    skin_noise_std = max(skin_noise_std, 1.0)

    for c in contours:
        area = cv2.contourArea(c)
        if min_area <= area <= max_area:
            (cx, cy), radius = cv2.minEnclosingCircle(c)
            perimeter = cv2.arcLength(c, True)
            if perimeter > 0:
                circularity = 4 * np.pi * (area / (perimeter * perimeter))
                if circularity >= SPOT_CONFIG["min_circularity"]:
                    roi_mask = np.zeros((h, w), dtype=np.uint8)
                    cv2.circle(roi_mask, (int(cx), int(cy)), max(2, int(radius)), 255, -1)
                    roi_vals = combined_response[roi_mask > 0]
                    
                    if len(roi_vals) > 0:
                        peak_prominence = float(np.mean(roi_vals))
                        # Signal-to-noise ratio of this spot relative to overall skin response variance
                        snr = peak_prominence / skin_noise_std
                        # Map SNR 1.5 - 5.0 to confidence 0.55 - 0.95
                        conf = 0.55 + 0.40 * float(np.clip((snr - 1.5) / 3.5, 0.0, 1.0))
                    else:
                        conf = 0.60

                    norm_x = cx / w
                    norm_y = cy / h
                    norm_r = radius / max(w, h)

                    regions.append(create_region_dict(norm_x, norm_y, norm_r, round(conf, 2)))

    regions.sort(key=lambda r: r["confidence"], reverse=True)
    return regions[:SPOT_CONFIG["max_regions_output"]]


def analyze_skin_characteristics(
    bgr_img: np.ndarray,
    landmarks: List[Any]
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], np.ndarray]:
    """
    Run full skin heuristic analysis.
    
    Returns:
        (skin_metrics_dict, detected_regions_list, skin_mask)
    """
    h, w = bgr_img.shape[:2]
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    lab = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2LAB)

    skin_mask = generate_skin_mask(landmarks, w, h)

    redness_score = analyze_redness(lab, skin_mask, landmarks, w, h)
    pigmentation_score = analyze_pigmentation(lab, skin_mask)
    texture_score = analyze_texture(gray, skin_mask)
    under_eye_score = analyze_under_eye(lab, skin_mask, landmarks, w, h)

    regions = detect_spot_regions(bgr_img, lab, skin_mask)

    skin_metrics = {
        "visible_spots": len(regions),
        "redness_score": redness_score,
        "pigmentation_score": pigmentation_score,
        "texture_score": texture_score,
        "under_eye_score": under_eye_score,
    }

    return skin_metrics, regions, skin_mask
