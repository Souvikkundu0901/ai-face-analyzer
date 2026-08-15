"""
MediaPipe Face Landmarker detection and landmark extraction module.
Serverless-ready with bundled model resolution and /tmp fallback.
"""
import os
import tempfile
import urllib.request
import ssl
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from app.config import MODEL_PATH, MODEL_URL, MODELS_DIR, BASE_DIR


def ensure_model_downloaded() -> Path:
    """
    Ensure the MediaPipe face_landmarker.task model file is available locally.
    Checks bundled models directory first, then /tmp fallback.
    """
    candidate_paths = [
        MODEL_PATH,
        BASE_DIR / "models" / "face_landmarker.task",
        Path("models/face_landmarker.task"),
        Path(tempfile.gettempdir()) / "face_landmarker.task",
    ]

    # 1. Check if model exists at any candidate location
    for p in candidate_paths:
        try:
            if p.exists() and p.stat().st_size > 1000000:
                return p
        except Exception:
            continue

    # 2. If not found, download directly to system temp directory
    target_path = Path(tempfile.gettempdir()) / "face_landmarker.task"
    print(f"Downloading face landmarker model (~3.7MB) to {target_path}...")
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    with urllib.request.urlopen(MODEL_URL, context=ctx) as response, open(target_path, 'wb') as out_file:
        out_file.write(response.read())

    print("Model download complete.")
    return target_path


class FaceDetector:
    """Wrapper around MediaPipe Tasks FaceLandmarker."""

    _instance: Optional["FaceDetector"] = None

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or ensure_model_downloaded()
        base_options = python.BaseOptions(model_asset_path=str(self.model_path))
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=True,
            num_faces=5,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)

    @classmethod
    def get_instance(cls) -> "FaceDetector":
        """Get or initialize singleton instance."""
        if cls._instance is None:
            cls._instance = FaceDetector()
        return cls._instance

    def detect(self, rgb_image: np.ndarray) -> vision.FaceLandmarkerResult:
        """
        Run face landmarker on an RGB uint8 numpy image.
        Returns FaceLandmarkerResult containing detected landmarks.
        """
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
        return self.landmarker.detect(mp_image)


def get_face_landmarks(rgb_image: np.ndarray) -> Tuple[int, Optional[List[Any]], Optional[vision.FaceLandmarkerResult]]:
    """
    Extract facial landmarks from an RGB image.
    
    Returns:
        (face_count, primary_face_landmarks_list, full_result)
    """
    detector = FaceDetector.get_instance()
    result = detector.detect(rgb_image)
    
    face_count = len(result.face_landmarks) if result.face_landmarks else 0
    if face_count == 0:
        return 0, None, result
    
    primary_landmarks = result.face_landmarks[0]
    return face_count, primary_landmarks, result
