"""
FastAPI application service for AI Face Analyzer Phase 2 (Hardening + Visualization).
"""
import io
import time
import uuid
import logging
from typing import Dict, Any, Optional
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import PIPELINE_VERSION, BASE_DIR, MAX_INPUT_DIMENSION, DEBUG_MODE
from app.schemas import (
    AnalysisResponseSchema,
    ImageQualitySchema,
    FaceAnalysisSchema,
    FaceRatiosSchema,
    SkinAnalysisSchema,
    RegionSchema,
    ReportSchema,
    ExplanationSchema,
    QualityRejectionSchema,
)
from app.pipeline.face_detect import get_face_landmarks, ensure_model_downloaded
from app.pipeline.quality import validate_image_quality
from app.pipeline.geometry import analyze_face_geometry
from app.pipeline.skin import analyze_skin_characteristics
from app.pipeline.overlay import render_debug_overlay, render_rejection_debug_overlay
from app.rules.engine import evaluate as evaluate_rules
from app.rules.recommendations import REPORT_DISCLAIMER
from app.llm.client import generate_explanation

# Configure structured logging
logging.basicConfig(
    level=logging.DEBUG if DEBUG_MODE else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("ai_face_analyzer")

# Initialize FastAPI application
app = FastAPI(
    title="AI Face Analyzer API",
    description="Computer vision pipeline analyzing facial geometry and skin characteristics from selfies.",
    version=PIPELINE_VERSION,
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory LRU cache for recent scans to serve debug overlay endpoint
SCAN_CACHE: Dict[str, Dict[str, Any]] = {}
MAX_CACHE_SIZE = 60


def cache_scan(scan_id: str, data: Dict[str, Any]) -> None:
    """Store scan session data in memory with simple FIFO eviction."""
    if len(SCAN_CACHE) >= MAX_CACHE_SIZE:
        oldest_key = next(iter(SCAN_CACHE))
        del SCAN_CACHE[oldest_key]
    SCAN_CACHE[scan_id] = data


@app.on_event("startup")
def startup_event():
    """Ensure MediaPipe model file is downloaded and ready at startup."""
    logger.info(f"Starting AI Face Analyzer service ({PIPELINE_VERSION})")
    ensure_model_downloaded()


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    import traceback
    tb = traceback.format_exc()
    logger.error(f"Global server error: {tb}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "traceback": tb
        }
    )


@app.get("/health", summary="Health Check")
@app.get("/api/health", summary="Health Check (API Prefix)", include_in_schema=False)
def health_check():
    """Service liveness and diagnostic check."""
    detector_status = "uninitialized"
    model_info = None
    err = None
    try:
        from app.pipeline.face_detect import FaceDetector, ensure_model_downloaded
        path = ensure_model_downloaded()
        model_info = {"path": str(path), "size": path.stat().st_size if path.exists() else 0}
        FaceDetector.get_instance()
        detector_status = "ready"
    except Exception as e:
        import traceback
        detector_status = "error"
        err = {"message": str(e), "traceback": traceback.format_exc()}

    return {
        "status": "ok" if detector_status == "ready" else "degraded",
        "version": PIPELINE_VERSION,
        "detector": detector_status,
        "model": model_info,
        "error_details": err
    }


@app.post(
    "/api/analyze",
    response_model=AnalysisResponseSchema,
    responses={
        200: {"description": "Successful analysis response", "model": AnalysisResponseSchema},
        422: {"description": "Quality gate rejection", "model": QualityRejectionSchema}
    },
    summary="Analyze Face Selfie"
)
@app.post(
    "/analyze",
    response_model=AnalysisResponseSchema,
    include_in_schema=False
)
async def analyze_face(image: UploadFile = File(..., description="Selfie image file (JPEG or PNG)")):
    """
    Accepts a selfie upload, runs the image quality gate, extracts facial geometry and skin heuristics,
    and returns a structured JSON analysis report.
    """
    t_start = time.perf_counter()
    scan_id = str(uuid.uuid4())
    logger.info(f"[{scan_id}] Received image upload: {image.filename} (content-type: {image.content_type})")

    # 1. Validate MIME type
    if image.content_type not in ["image/jpeg", "image/png", "image/webp", "image/jpg", "application/octet-stream"]:
        logger.warning(f"[{scan_id}] Rejected: invalid content type {image.content_type}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=QualityRejectionSchema(
                passed=False,
                reason="invalid_format",
                message="Uploaded file must be a valid JPEG or PNG image."
            ).model_dump()
        )

    # 2. Read and decode image bytes
    try:
        contents = await image.read()
        if len(contents) == 0:
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=QualityRejectionSchema(
                    passed=False,
                    reason="empty_file",
                    message="Uploaded file is empty."
                ).model_dump()
            )

        pil_img = Image.open(io.BytesIO(contents)).convert("RGB")
        rgb_img = np.array(pil_img)
        
        # Downscale internally if extremely high resolution for memory/performance protection
        h, w = rgb_img.shape[:2]
        if max(h, w) > MAX_INPUT_DIMENSION:
            scale = MAX_INPUT_DIMENSION / float(max(h, w))
            new_w, new_h = int(w * scale), int(h * scale)
            logger.info(f"[{scan_id}] Downscaling high-res image from {w}x{h} to {new_w}x{new_h}")
            rgb_img = cv2.resize(rgb_img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        bgr_img = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2BGR)
    except Exception as e:
        logger.error(f"[{scan_id}] Failed to decode image: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=QualityRejectionSchema(
                passed=False,
                reason="corrupted_image",
                message="Could not decode image file. Please provide an uncorrupted image."
            ).model_dump()
        )

    # 3. Detect face & landmarks
    t_detect = time.perf_counter()
    try:
        face_count, landmarks, _ = get_face_landmarks(rgb_img)
    except Exception as e:
        logger.error(f"[{scan_id}] Face landmark detection error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=QualityRejectionSchema(
                passed=False,
                reason="detection_error",
                message="Facial landmark detector encountered an error processing the image."
            ).model_dump()
        )
    logger.debug(f"[{scan_id}] Landmark extraction took {(time.perf_counter() - t_detect)*1000:.1f}ms (faces: {face_count})")

    # 4. Image Quality Gate
    t_gate = time.perf_counter()
    passed, reason, failure_msg, quality_metrics, warnings = validate_image_quality(
        bgr_img, face_count, landmarks
    )
    logger.debug(f"[{scan_id}] Quality gate check took {(time.perf_counter() - t_gate)*1000:.1f}ms (passed: {passed})")

    if not passed:
        logger.info(f"[{scan_id}] Quality gate REJECTED: {reason} - {failure_msg}")
        # Cache rejection state for visual diagnostic overlay
        cache_scan(scan_id, {
            "status": "rejected",
            "bgr_img": bgr_img,
            "reason": reason or "quality_gate_failed",
            "message": failure_msg or "Image did not meet quality requirements.",
            "metrics": quality_metrics
        })
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=QualityRejectionSchema(
                passed=False,
                reason=reason or "quality_gate_failed",
                message=failure_msg or "Image did not meet quality requirements."
            ).model_dump()
        )

    # 5. Facial Geometry & Shape Analysis
    t_geo = time.perf_counter()
    cur_h, cur_w = bgr_img.shape[:2]
    geometry_results = analyze_face_geometry(landmarks, cur_w, cur_h)
    logger.debug(f"[{scan_id}] Geometry analysis took {(time.perf_counter() - t_geo)*1000:.1f}ms")

    # 6. Skin Characteristic Heuristics
    t_skin = time.perf_counter()
    skin_results, detected_regions, skin_mask = analyze_skin_characteristics(bgr_img, landmarks)
    logger.debug(f"[{scan_id}] Skin heuristics took {(time.perf_counter() - t_skin)*1000:.1f}ms")

    # 7. Rules Engine Evaluation (pure, synchronous, deterministic)
    t_rules = time.perf_counter()
    rule_scores = {
        "redness_score": skin_results.get("redness_score", 0.0),
        "pigmentation_score": skin_results.get("pigmentation_score", 0.0),
        "texture_score": skin_results.get("texture_score", 0.0),
        "under_eye_score": skin_results.get("under_eye_score", 0.0),
        "visible_spots": skin_results.get("visible_spots", 0),
        "image_quality_score": quality_metrics.get("score", 1.0),
    }
    triggered_ids = evaluate_rules(rule_scores)
    logger.debug(f"[{scan_id}] Rules evaluation took {(time.perf_counter() - t_rules)*1000:.1f}ms → {triggered_ids}")

    # 8. LLM Explanation Generation (async, with fallback to canned text)
    t_llm = time.perf_counter()
    try:
        llm_report = await generate_explanation(
            triggered_ids=triggered_ids,
            supporting_scores=rule_scores,
            face_shape=geometry_results.get("shape", "unknown"),
        )
        report_payload = {
            "triggered_recommendations": triggered_ids,
            "explanations": [
                {"id": item.id, "text": item.text}
                for item in llm_report.explanations
            ],
            "summary": llm_report.summary,
            "disclaimer": REPORT_DISCLAIMER,
        }
    except Exception as e:
        logger.error(f"[{scan_id}] LLM explanation failed entirely: {e}. Using minimal report.")
        from app.rules.recommendations import get_fallback_text
        report_payload = {
            "triggered_recommendations": triggered_ids,
            "explanations": [
                {"id": rid, "text": get_fallback_text(rid)} for rid in triggered_ids
            ],
            "summary": f"{len(triggered_ids)} observation(s) noted based on visible characteristics.",
            "disclaimer": REPORT_DISCLAIMER,
        }
    logger.debug(f"[{scan_id}] LLM explanation took {(time.perf_counter() - t_llm)*1000:.1f}ms")

    # 9. Assemble Structured Response
    response_payload = {
        "scan_id": scan_id,
        "pipeline_version": PIPELINE_VERSION,
        "image_quality": quality_metrics,
        "face": geometry_results,
        "skin": skin_results,
        "regions": detected_regions,
        "warnings": warnings,
        "report": report_payload,
    }

    # 10. Cache data for debug overlay inspection
    cache_scan(scan_id, {
        "status": "success",
        "bgr_img": bgr_img,
        "landmarks": landmarks,
        "regions": detected_regions,
        "geometry": geometry_results,
        "skin": skin_results,
        "skin_mask": skin_mask
    })

    t_total = (time.perf_counter() - t_start) * 1000.0
    logger.info(f"[{scan_id}] Analysis completed successfully in {t_total:.1f}ms (Shape: {geometry_results['shape']}, Spots: {skin_results['visible_spots']}, Rules: {triggered_ids})")

    return response_payload


@app.get("/api/analyze/{scan_id}/overlay", summary="Get Visual Debug Overlay")
@app.get("/analyze/{scan_id}/overlay", summary="Get Visual Debug Overlay (Direct)", include_in_schema=False)
def get_debug_overlay(scan_id: str):
    """
    Returns a PNG debug overlay visualization with landmarks, skin mask outline,
    confidence-colored spot regions, or rejection diagnostic if scan failed quality gate.
    """
    if scan_id not in SCAN_CACHE:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan session expired or not found. Please run a new analysis."
        )

    cached = SCAN_CACHE[scan_id]
    try:
        if cached.get("status") == "rejected":
            overlay_png_bytes = render_rejection_debug_overlay(
                bgr_img=cached["bgr_img"],
                reason=cached["reason"],
                message=cached["message"],
                metrics=cached.get("metrics")
            )
        else:
            overlay_png_bytes = render_debug_overlay(
                bgr_img=cached["bgr_img"],
                landmarks=cached["landmarks"],
                regions=cached["regions"],
                geometry_info=cached.get("geometry"),
                skin_info=cached.get("skin"),
                skin_mask=cached.get("skin_mask")
            )
        return Response(content=overlay_png_bytes, media_type="image/png")
    except Exception as e:
        logger.error(f"Failed to generate debug overlay for {scan_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate debug overlay: {str(e)}"
        )


# Mount static directory and root index
static_path = BASE_DIR / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

@app.get("/", include_in_schema=False)
def serve_index():
    """Serve the single-page testing client."""
    index_file = BASE_DIR / "static" / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "AI Face Analyzer API is running. Visit /docs for OpenAPI documentation."}
