"""
Image quality gate for validating selfies before analysis.
Rejects blurry, dark, overexposed, off-pose, or improperly framed inputs.
"""
import math
from typing import Dict, List, Optional, Tuple, Any
import cv2
import numpy as np

from app.config import QUALITY_THRESHOLDS, LANDMARK_INDICES


def evaluate_sharpness(gray_img: np.ndarray) -> Tuple[float, float]:
    """
    Calculate image sharpness using Laplacian variance.
    Returns: (variance_value, normalized_score [0.0 - 1.0])
    """
    laplacian_var = float(cv2.Laplacian(gray_img, cv2.CV_64F).var())
    normalized = float(np.clip(laplacian_var / QUALITY_THRESHOLDS["sharpness_norm_scale"], 0.0, 1.0))
    return laplacian_var, round(normalized, 3)


def evaluate_lighting(gray_img: np.ndarray, mask: Optional[np.ndarray] = None) -> Tuple[float, float]:
    """
    Calculate lighting quality from mean pixel intensity.
    Returns: (mean_intensity, normalized_score [0.0 - 1.0])
    """
    if mask is not None and np.count_nonzero(mask) > 100:
        pixels = gray_img[mask > 0]
        mean_val = float(np.mean(pixels))
    else:
        mean_val = float(np.mean(gray_img))
        
    optimal = QUALITY_THRESHOLDS["optimal_brightness"]
    lighting_score = float(max(0.0, 1.0 - abs(mean_val - optimal) / optimal))
    return mean_val, round(lighting_score, 3)


def estimate_pose_angles(landmarks: List[Any], img_w: int, img_h: int) -> Tuple[float, float, float]:
    """
    Estimate head pose angles (yaw, pitch, roll) in degrees from 3D facial landmarks.
    """
    idx_nose = LANDMARK_INDICES["nose_tip"]
    idx_bridge = LANDMARK_INDICES["nose_bridge"]
    idx_chin = LANDMARK_INDICES["chin"]
    idx_top = LANDMARK_INDICES["top_forehead"]
    idx_left_eye = LANDMARK_INDICES["left_pupil"]
    idx_right_eye = LANDMARK_INDICES["right_pupil"]
    idx_left_edge = LANDMARK_INDICES["left_face_edge"]
    idx_right_edge = LANDMARK_INDICES["right_face_edge"]

    p_nose = np.array([landmarks[idx_nose].x * img_w, landmarks[idx_nose].y * img_h, landmarks[idx_nose].z * img_w])
    p_bridge = np.array([landmarks[idx_bridge].x * img_w, landmarks[idx_bridge].y * img_h, landmarks[idx_bridge].z * img_w])
    p_chin = np.array([landmarks[idx_chin].x * img_w, landmarks[idx_chin].y * img_h, landmarks[idx_chin].z * img_w])
    p_top = np.array([landmarks[idx_top].x * img_w, landmarks[idx_top].y * img_h, landmarks[idx_top].z * img_w])
    p_left_eye = np.array([landmarks[idx_left_eye].x * img_w, landmarks[idx_left_eye].y * img_h, landmarks[idx_left_eye].z * img_w])
    p_right_eye = np.array([landmarks[idx_right_eye].x * img_w, landmarks[idx_right_eye].y * img_h, landmarks[idx_right_eye].z * img_w])
    p_left_edge = np.array([landmarks[idx_left_edge].x * img_w, landmarks[idx_left_edge].y * img_h])
    p_right_edge = np.array([landmarks[idx_right_edge].x * img_w, landmarks[idx_right_edge].y * img_h])

    # 1. Roll
    dx = p_right_eye[0] - p_left_eye[0]
    dy = p_right_eye[1] - p_left_eye[1]
    roll_deg = math.degrees(math.atan2(dy, dx))

    # 2. Yaw
    d_left = abs(p_nose[0] - p_left_edge[0])
    d_right = abs(p_right_edge[0] - p_nose[0])
    total_w = d_left + d_right
    if total_w > 0:
        yaw_ratio = (d_right - d_left) / total_w
        yaw_deg = yaw_ratio * 75.0
    else:
        yaw_deg = 0.0

    # 3. Pitch
    d_upper = abs(p_bridge[1] - p_top[1])
    d_lower = abs(p_chin[1] - p_bridge[1])
    total_h = d_upper + d_lower
    if total_h > 0:
        pitch_ratio = (d_lower - d_upper) / total_h
        pitch_deg = pitch_ratio * 60.0
    else:
        pitch_deg = 0.0

    return yaw_deg, pitch_deg, roll_deg


def validate_image_quality(
    bgr_img: np.ndarray,
    face_count: int,
    landmarks: Optional[List[Any]]
) -> Tuple[bool, Optional[str], Optional[str], Dict[str, Any], List[str]]:
    """
    Run full image quality gate checks.
    
    Returns:
        (passed, failure_reason, failure_message, quality_metrics, warnings)
    """
    h, w = bgr_img.shape[:2]
    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
    
    sharpness_var, sharpness_score = evaluate_sharpness(gray)
    brightness_val, lighting_score = evaluate_lighting(gray)
    
    warnings: List[str] = []
    
    # 1. Check face count
    if face_count == 0:
        return (
            False,
            "no_face",
            "No face detected. Please ensure your face is well-lit, unobstructed, and looking toward the camera.",
            {"score": 0.0, "lighting": lighting_score, "sharpness": sharpness_score, "pose": 0.0, "passed": False},
            warnings
        )
    
    if face_count > 1:
        return (
            False,
            "multiple_faces",
            f"Multiple faces detected ({face_count}). Please take a solo photo with only one face in the frame.",
            {"score": 0.0, "lighting": lighting_score, "sharpness": sharpness_score, "pose": 0.0, "passed": False},
            warnings
        )

    # 2. Check Exposure
    if brightness_val < QUALITY_THRESHOLDS["min_brightness"]:
        return (
            False,
            "underexposed",
            "Image is too dark. Please move to a well-lit area or turn on front-facing lighting.",
            {"score": 0.3, "lighting": lighting_score, "sharpness": sharpness_score, "pose": 0.5, "passed": False},
            warnings
        )
    
    if brightness_val > QUALITY_THRESHOLDS["max_brightness"]:
        return (
            False,
            "overexposed",
            "Image is overexposed or washed out. Please reduce bright backlight or direct flash glare.",
            {"score": 0.3, "lighting": lighting_score, "sharpness": sharpness_score, "pose": 0.5, "passed": False},
            warnings
        )

    # 3. Check Blur
    if sharpness_var < QUALITY_THRESHOLDS["min_sharpness_var"]:
        return (
            False,
            "blur",
            "Image is too blurry. Hold the camera steady and retake in good light.",
            {"score": round(sharpness_score * 0.4, 3), "lighting": lighting_score, "sharpness": sharpness_score, "pose": 0.5, "passed": False},
            warnings
        )

    # 4. Check bounding box framing
    xs = [lm.x for lm in landmarks]
    ys = [lm.y for lm in landmarks]
    min_x, max_x = max(0.0, min(xs)), min(1.0, max(xs))
    min_y, max_y = max(0.0, min(ys)), min(1.0, max(ys))
    
    face_w_ratio = max_x - min_x
    face_h_ratio = max_y - min_y
    face_bbox_area = face_w_ratio * face_h_ratio
    
    if (face_w_ratio < QUALITY_THRESHOLDS["min_face_width_ratio"] or 
        face_h_ratio < QUALITY_THRESHOLDS["min_face_height_ratio"] or 
        face_bbox_area < QUALITY_THRESHOLDS["min_face_area_ratio"]):
        return (
            False,
            "face_too_small",
            "Face is too far from the camera. Please move closer so your face fills at least 20% of the frame.",
            {"score": 0.2, "lighting": lighting_score, "sharpness": sharpness_score, "pose": 0.5, "passed": False},
            warnings
        )

    # 5. Check Pose
    yaw, pitch, roll = estimate_pose_angles(landmarks, w, h)
    
    max_yaw = QUALITY_THRESHOLDS["max_yaw_deg"]
    max_pitch = QUALITY_THRESHOLDS["max_pitch_deg"]
    max_roll = QUALITY_THRESHOLDS["max_roll_deg"]
    
    # Calculate independent continuous pose score
    pose_score = float(np.clip(
        1.0 - (abs(yaw)/max_yaw*0.4 + abs(pitch)/max_pitch*0.3 + abs(roll)/max_roll*0.3),
        0.0, 1.0
    ))
    
    if abs(yaw) > max_yaw or abs(pitch) > max_pitch or abs(roll) > max_roll:
        return (
            False,
            "pose_angle",
            "Face is turned or tilted too far. Please look directly at the camera with your head upright.",
            {"score": round(pose_score * 0.5, 3), "lighting": lighting_score, "sharpness": sharpness_score, "pose": round(pose_score, 3), "passed": False},
            warnings
        )

    # Soft warnings for slight suboptimal conditions
    if sharpness_var < QUALITY_THRESHOLDS["warn_soft_sharpness"]:
        warnings.append("Slight image softness detected; hold camera steady for maximum clarity.")
    if brightness_val < QUALITY_THRESHOLDS["warn_low_brightness"] or brightness_val > QUALITY_THRESHOLDS["warn_high_brightness"]:
        warnings.append("Mild uneven lighting detected.")
    if abs(yaw) > QUALITY_THRESHOLDS["warn_yaw_deg"] or abs(pitch) > QUALITY_THRESHOLDS["warn_pitch_deg"] or abs(roll) > QUALITY_THRESHOLDS["warn_roll_deg"]:
        warnings.append("Slight head angle detected; center alignment gives the most consistent measurements.")

    # Overall composite quality score
    composite_score = round(float(sharpness_score * 0.35 + lighting_score * 0.35 + pose_score * 0.30), 3)

    quality_metrics = {
        "score": composite_score,
        "lighting": lighting_score,
        "sharpness": sharpness_score,
        "pose": round(pose_score, 3),
        "passed": True
    }
    
    return True, None, None, quality_metrics, warnings
