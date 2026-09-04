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
from fastapi import FastAPI, File, UploadFile, HTTPException, status, Depends, Query
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
from app.comparison.service import compare_scan_records

# Database & Auth
from datetime import datetime, timedelta, timezone
from fastapi import Depends
from sqlalchemy.orm import Session
from app.db.session import get_db, init_db
from app.db.models import User, Scan, RefreshToken
from app.auth.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
)
from app.auth.dependencies import get_current_user
from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from app.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserResponse,
    ScanSummarySchema,
    ScanListResponse,
    ComparisonDeltaSchema,
    ScanTimelineItem,
    ScanComparisonResponse,
)

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
    """Ensure MediaPipe model file is downloaded and database tables are initialized."""
    logger.info(f"Starting AI Face Analyzer service ({PIPELINE_VERSION})")
    init_db()
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


# ==============================================================================
# Authentication Endpoints (Phase 4, Section 3)
# ==============================================================================
@app.post("/api/auth/register", response_model=TokenResponse, summary="Register New User")
def register_user(req: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account with email and password."""
    email = req.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    hashed_pw = hash_password(req.password)
    user = User(email=email, password_hash=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"Registered new user account: {user.id} ({user.email})")

    # Issue JWT tokens
    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id)

    # Store hashed refresh token for DB-backed revocation tracking
    rt_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(rt_record)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@app.post("/api/auth/login", response_model=TokenResponse, summary="Log In User")
def login_user(req: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with email/password and issue session tokens."""
    email = req.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    access_token = create_access_token(user_id=user.id, email=user.email)
    refresh_token = create_refresh_token(user_id=user.id)

    rt_record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(rt_record)
    db.commit()

    logger.info(f"User logged in successfully: {user.id}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@app.post("/api/auth/refresh", response_model=TokenResponse, summary="Refresh Session Tokens")
def refresh_session(req: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Validate refresh token, revoke it, and issue a rotated token pair."""
    try:
        payload = decode_token(req.refresh_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token."
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type. Expected refresh token."
        )

    user_id = payload.get("sub")
    t_hash = hash_token(req.refresh_token)
    now = datetime.now(timezone.utc)

    rt_record = db.query(RefreshToken).filter(
        RefreshToken.user_id == user_id,
        RefreshToken.token_hash == t_hash,
        RefreshToken.revoked.is_(False),
        RefreshToken.expires_at > now
    ).first()

    if not rt_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or expired."
        )

    # Rotate: Revoke the used token immediately
    rt_record.revoked = True

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists."
        )

    new_access_token = create_access_token(user_id=user.id, email=user.email)
    new_refresh_token = create_refresh_token(user_id=user.id)

    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(new_refresh_token),
        expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(new_rt)
    db.commit()

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@app.get("/api/auth/me", response_model=UserResponse, summary="Current User Profile")
def get_me(current_user: User = Depends(get_current_user)):
    """Return currently authenticated user profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at.isoformat()
    )


async def run_pipeline_on_image(contents: bytes, filename: str, content_type: str):
    """Executes the computer vision and rules pipeline. Returns (status_code, payload, cache_dict)."""
    t_start = time.perf_counter()
    scan_id = str(uuid.uuid4())
    logger.info(f"[{scan_id}] Processing image upload: {filename} (content-type: {content_type})")

    # 1. Validate MIME type
    if content_type not in ["image/jpeg", "image/png", "image/webp", "image/jpg", "application/octet-stream"]:
        logger.warning(f"[{scan_id}] Rejected: invalid content type {content_type}")
        return status.HTTP_422_UNPROCESSABLE_ENTITY, QualityRejectionSchema(
            passed=False,
            reason="invalid_format",
            message="Uploaded file must be a valid JPEG or PNG image."
        ).model_dump(), None

    # 2. Read and decode image bytes
    try:
        if len(contents) == 0:
            return status.HTTP_422_UNPROCESSABLE_ENTITY, QualityRejectionSchema(
                passed=False,
                reason="empty_file",
                message="Uploaded file is empty."
            ).model_dump(), None

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
        return status.HTTP_422_UNPROCESSABLE_ENTITY, QualityRejectionSchema(
            passed=False,
            reason="corrupted_image",
            message="Could not decode image file. Please provide an uncorrupted image."
        ).model_dump(), None

    # 3. Detect face & landmarks
    t_detect = time.perf_counter()
    try:
        face_count, landmarks, _ = get_face_landmarks(rgb_img)
    except Exception as e:
        logger.error(f"[{scan_id}] Face landmark detection error: {str(e)}")
        return status.HTTP_422_UNPROCESSABLE_ENTITY, QualityRejectionSchema(
            passed=False,
            reason="detection_error",
            message="Facial landmark detector encountered an error processing the image."
        ).model_dump(), None
    logger.debug(f"[{scan_id}] Landmark extraction took {(time.perf_counter() - t_detect)*1000:.1f}ms (faces: {face_count})")

    # 4. Image Quality Gate
    t_gate = time.perf_counter()
    passed, reason, failure_msg, quality_metrics, warnings = validate_image_quality(
        bgr_img, face_count, landmarks
    )
    logger.debug(f"[{scan_id}] Quality gate check took {(time.perf_counter() - t_gate)*1000:.1f}ms (passed: {passed})")

    if not passed:
        logger.info(f"[{scan_id}] Quality gate REJECTED: {reason} - {failure_msg}")
        rejection_cache = {
            "status": "rejected",
            "bgr_img": bgr_img,
            "reason": reason or "quality_gate_failed",
            "message": failure_msg or "Image did not meet quality requirements.",
            "metrics": quality_metrics
        }
        return status.HTTP_422_UNPROCESSABLE_ENTITY, QualityRejectionSchema(
            passed=False,
            reason=reason or "quality_gate_failed",
            message=failure_msg or "Image did not meet quality requirements."
        ).model_dump(), rejection_cache

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
    success_cache = {
        "status": "success",
        "bgr_img": bgr_img,
        "landmarks": landmarks,
        "regions": detected_regions,
        "geometry": geometry_results,
        "skin": skin_results,
        "skin_mask": skin_mask
    }

    t_total = (time.perf_counter() - t_start) * 1000.0
    logger.info(f"[{scan_id}] Analysis completed successfully in {t_total:.1f}ms (Shape: {geometry_results['shape']}, Spots: {skin_results['visible_spots']}, Rules: {triggered_ids})")

    return status.HTTP_200_OK, response_payload, success_cache


# ==============================================================================
# Anonymous Scan Endpoint (Backward Compatible with Phase 1-3)
# ==============================================================================
@app.post(
    "/api/analyze",
    response_model=AnalysisResponseSchema,
    responses={
        200: {"description": "Successful analysis response", "model": AnalysisResponseSchema},
        422: {"description": "Quality gate rejection", "model": QualityRejectionSchema}
    },
    summary="Analyze Face Selfie (Anonymous)"
)
@app.post(
    "/analyze",
    response_model=AnalysisResponseSchema,
    include_in_schema=False
)
async def analyze_face(image: UploadFile = File(..., description="Selfie image file (JPEG or PNG)")):
    """Accepts a selfie upload, runs analysis, and returns report without requiring login."""
    contents = await image.read()
    status_code, payload, cache_entry = await run_pipeline_on_image(contents, image.filename, image.content_type)
    if cache_entry and "scan_id" in payload:
        cache_scan(payload["scan_id"], cache_entry)

    if status_code != status.HTTP_200_OK:
        return JSONResponse(status_code=status_code, content=payload)
    return payload


# ==============================================================================
# Authenticated Scan Persistence Endpoints (Phase 4, Section 4)
# ==============================================================================
@app.post(
    "/api/scans",
    response_model=AnalysisResponseSchema,
    responses={
        200: {"description": "Successful analysis response", "model": AnalysisResponseSchema},
        422: {"description": "Quality gate rejection", "model": QualityRejectionSchema}
    },
    summary="Analyze Face and Persist Scan"
)
async def create_scan(
    image: UploadFile = File(..., description="Selfie image file (JPEG or PNG)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Runs full analysis pipeline and persists the structured metrics to the database.
    Strictly scoped to the authenticated user.
    """
    contents = await image.read()
    status_code, payload, cache_entry = await run_pipeline_on_image(contents, image.filename, image.content_type)
    if cache_entry and "scan_id" in payload:
        cache_scan(payload["scan_id"], cache_entry)

    if status_code != status.HTTP_200_OK:
        return JSONResponse(status_code=status_code, content=payload)

    # Persist structured scan metrics to PostgreSQL/database
    scan = Scan(
        id=payload["scan_id"],
        user_id=current_user.id,
        pipeline_version=payload["pipeline_version"],
        image_quality=payload["image_quality"],
        face_metrics=payload["face"],
        skin_metrics=payload["skin"],
        regions=payload["regions"],
        recommendation_ids=payload["report"]["triggered_recommendations"],
        report=payload["report"],
        image_ref=None,  # Zero image retention default per Section 6
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    logger.info(f"Audit log: Persisted scan {scan.id} for user {current_user.id}")

    return payload


@app.get(
    "/api/scans",
    response_model=ScanListResponse,
    summary="List User Scans (Paginated, Newest First)"
)
def list_user_scans(
    limit: int = Query(10, ge=1, le=50, description="Page limit"),
    offset: int = Query(0, ge=0, description="Page offset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List authenticated user's scans, newest first."""
    query = db.query(Scan).filter(Scan.user_id == current_user.id)
    total = query.count()
    scans = query.order_by(Scan.created_at.desc()).offset(offset).limit(limit).all()

    items = []
    for s in scans:
        rec_ids = s.recommendation_ids if isinstance(s.recommendation_ids, list) else []
        top_rec = rec_ids[0] if len(rec_ids) > 0 else None
        iq = s.image_quality if isinstance(s.image_quality, dict) else {}
        face = s.face_metrics if isinstance(s.face_metrics, dict) else {}
        skin = s.skin_metrics if isinstance(s.skin_metrics, dict) else {}

        items.append(ScanSummarySchema(
            id=s.id,
            created_at=s.created_at.isoformat(),
            pipeline_version=s.pipeline_version,
            overall_quality_score=float(iq.get("score", 0.0)),
            face_shape=str(face.get("shape", "unknown")),
            top_recommendation=top_rec,
            visible_spots=int(skin.get("visible_spots", 0)),
            redness_score=float(skin.get("redness_score", 0.0)),
            texture_score=float(skin.get("texture_score", 0.0)),
        ))

    logger.info(f"Audit log: User {current_user.id} retrieved scan list (total={total})")

    return ScanListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset
    )


@app.get(
    "/api/scans/compare",
    response_model=ScanComparisonResponse,
    summary="Compare Two or More Scans (Phase 4, Section 5)"
)
def compare_scans(
    ids: str = Query(..., description="Comma-separated scan UUIDs (minimum 2)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compare 2 or more scans belonging to the authenticated user.
    Surfaces metric deltas and prominent comparability warning if capture conditions differ.
    """
    scan_id_list = [sid.strip() for sid in ids.split(",") if sid.strip()]
    if len(scan_id_list) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 scan IDs must be provided for comparison."
        )

    # Strictly scoped: Only load scans belonging to current_user
    scans = db.query(Scan).filter(
        Scan.id.in_(scan_id_list),
        Scan.user_id == current_user.id
    ).all()

    if len(scans) != len(scan_id_list):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more scan IDs not found or access denied."
        )

    logger.info(f"Audit log: User {current_user.id} compared scans {scan_id_list}")

    try:
        comparison_res = compare_scan_records(scans)
        return comparison_res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Comparison failed: {str(e)}"
        )


@app.get(
    "/api/scans/{scan_id}",
    response_model=AnalysisResponseSchema,
    summary="Get Full Scan Detail"
)
def get_scan_detail(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve full detail for one scan. Strictly scoped to authenticated user."""
    scan = db.query(Scan).filter(Scan.id == scan_id, Scan.user_id == current_user.id).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found or access denied."
        )

    logger.info(f"Audit log: User {current_user.id} accessed scan {scan.id}")

    return {
        "scan_id": scan.id,
        "pipeline_version": scan.pipeline_version,
        "image_quality": scan.image_quality,
        "face": scan.face_metrics,
        "skin": scan.skin_metrics,
        "regions": scan.regions,
        "warnings": [],
        "report": scan.report
    }


@app.delete(
    "/api/scans/{scan_id}",
    summary="Delete Single Scan (Real Delete)"
)
def delete_scan(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permanently delete a scan from the database.
    Real deletion, not a soft-delete flag.
    """
    scan = db.query(Scan).filter(Scan.id == scan_id, Scan.user_id == current_user.id).first()
    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scan not found or access denied."
        )

    db.delete(scan)
    db.commit()
    logger.info(f"Audit log: User {current_user.id} permanently deleted scan {scan_id}")

    # Evict from overlay cache if present
    SCAN_CACHE.pop(scan_id, None)

    return {"status": "deleted", "scan_id": scan_id}


@app.delete(
    "/api/users/me",
    summary="Delete User Account and All Data (Real Cascade Delete)"
)
def delete_user_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permanently delete the user account and all associated scans and session tokens.
    Real deletion with cascading removal.
    """
    user_id = current_user.id
    email = current_user.email

    # Explicitly delete associated child scans and tokens to guarantee 100% clean cascade across all engines
    db.query(Scan).filter(Scan.user_id == user_id).delete(synchronize_session="fetch")
    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete(synchronize_session="fetch")

    user = db.query(User).filter(User.id == user_id).first()
    if user:
        db.delete(user)
    db.commit()
    logger.info(f"Audit log: User {user_id} ({email}) permanently deleted their account and all data.")

    return {
        "status": "deleted",
        "message": "User account and all associated scan data permanently removed."
    }


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
