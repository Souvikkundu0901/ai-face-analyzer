"""
Pydantic response and error schemas matching the AI Face Analyzer specification.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class ImageQualitySchema(BaseModel):
    score: float = Field(..., description="Overall image quality score (0.0 - 1.0)")
    lighting: float = Field(..., description="Lighting quality score (0.0 - 1.0)")
    sharpness: float = Field(..., description="Image sharpness score (0.0 - 1.0)")
    pose: float = Field(..., description="Head pose score (0.0 - 1.0)")
    passed: bool = Field(..., description="Whether the quality gate passed")


class FaceRatiosSchema(BaseModel):
    jaw_width_to_face_width: float = Field(..., description="Ratio of jaw width to cheekbone face width")
    forehead_width_to_face_width: float = Field(..., description="Ratio of forehead width to face width")
    eye_distance_to_face_width: float = Field(..., description="Ratio of inter-eye distance to face width")
    nose_width_to_face_width: float = Field(..., description="Ratio of nose width to face width")
    lip_width_to_face_width: float = Field(..., description="Ratio of lip width to face width")


class FaceAnalysisSchema(BaseModel):
    shape: str = Field(..., description="Heuristic facial shape (oval, round, square, rectangle, heart, diamond)")
    shape_confidence: float = Field(..., description="Confidence of face shape classification (0.0 - 1.0)")
    symmetry_score: float = Field(..., description="Facial symmetry score (0.0 - 1.0)")
    face_ratio: float = Field(..., description="Ratio of face height to face width")
    ratios: FaceRatiosSchema


class SkinAnalysisSchema(BaseModel):
    visible_spots: int = Field(..., description="Count of visible spot-like regions detected")
    redness_score: float = Field(..., description="Normalized redness score (0.0 - 1.0)")
    pigmentation_score: float = Field(..., description="Normalized pigmentation variation score (0.0 - 1.0)")
    texture_score: float = Field(..., description="Normalized skin texture roughness score (0.0 - 1.0)")
    under_eye_score: float = Field(..., description="Normalized under-eye darkness/contrast score (0.0 - 1.0)")


class RegionSchema(BaseModel):
    type: str = Field(default="spot_like_region", description="Flagged region type descriptor")
    x: float = Field(..., description="Normalized horizontal center coordinate (0.0 - 1.0)")
    y: float = Field(..., description="Normalized vertical center coordinate (0.0 - 1.0)")
    radius: float = Field(..., description="Normalized radius relative to image dimensions")
    confidence: float = Field(..., description="Confidence score for this detected region (0.0 - 1.0)")


class ExplanationSchema(BaseModel):
    id: str = Field(..., description="Recommendation ID being explained")
    text: str = Field(..., description="Observational explanation text")


class ReportSchema(BaseModel):
    triggered_recommendations: List[str] = Field(..., description="List of triggered recommendation IDs")
    explanations: List[ExplanationSchema] = Field(..., description="LLM or canned explanations per recommendation")
    summary: str = Field(..., description="Closing summary paragraph")
    disclaimer: str = Field(..., description="Standard non-medical disclaimer")


class AnalysisResponseSchema(BaseModel):
    scan_id: str = Field(..., description="Unique scan identifier UUID")
    pipeline_version: str = Field(..., description="Pipeline version string")
    image_quality: ImageQualitySchema
    face: FaceAnalysisSchema
    skin: SkinAnalysisSchema
    regions: List[RegionSchema] = Field(default_factory=list, description="List of detected regions")
    warnings: List[str] = Field(default_factory=list, description="Soft warnings regarding scan reliability")
    report: Optional[ReportSchema] = Field(default=None, description="Recommendation report with explanations")


class QualityRejectionSchema(BaseModel):
    passed: bool = Field(default=False, description="Always false for rejected scans")
    reason: str = Field(..., description="Short machine-readable failure reason code")
    message: str = Field(..., description="User-facing retake guidance")


# ==============================================================================
# Phase 4 Auth & User Schemas
# ==============================================================================
class UserRegisterRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="Plaintext password (minimum 6 characters)")


class UserLoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="Plaintext password")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Valid refresh token")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration time in seconds")


class UserResponse(BaseModel):
    id: str = Field(..., description="Unique user UUID")
    email: str = Field(..., description="User email address")
    created_at: str = Field(..., description="Registration timestamp")


# ==============================================================================
# Phase 4 Scan Persistence & History Schemas
# ==============================================================================
class ScanSummarySchema(BaseModel):
    id: str = Field(..., description="Scan UUID")
    created_at: str = Field(..., description="Capture timestamp")
    pipeline_version: str = Field(..., description="Pipeline version used")
    overall_quality_score: float = Field(..., description="Overall image quality score (0.0 - 1.0)")
    face_shape: str = Field(..., description="Classified face shape")
    top_recommendation: Optional[str] = Field(None, description="Primary triggered recommendation ID")
    visible_spots: int = Field(..., description="Detected spot count")
    redness_score: float = Field(..., description="Redness score")
    texture_score: float = Field(..., description="Texture score")


class ScanListResponse(BaseModel):
    items: List[ScanSummarySchema] = Field(..., description="List of scan summaries")
    total: int = Field(..., description="Total count of scans for user")
    limit: int = Field(..., description="Pagination limit")
    offset: int = Field(..., description="Pagination offset")


# ==============================================================================
# Phase 4 Comparison Schemas
# ==============================================================================
class ComparisonDeltaSchema(BaseModel):
    redness_score: float = Field(..., description="Delta in redness score (newer - older)")
    pigmentation_score: float = Field(..., description="Delta in pigmentation variation")
    texture_score: float = Field(..., description="Delta in texture roughness")
    under_eye_score: float = Field(..., description="Delta in under-eye shade")
    visible_spots: int = Field(..., description="Delta in visible spot count")


class ScanTimelineItem(BaseModel):
    scan_id: str
    created_at: str
    quality_score: float
    face_shape: str
    redness_score: float
    pigmentation_score: float
    texture_score: float
    under_eye_score: float
    visible_spots: int


class ScanComparisonResponse(BaseModel):
    scans_compared: List[str] = Field(..., description="List of scan UUIDs compared in chronological order")
    comparability_warning: Optional[str] = Field(
        None,
        description="Warning surfaced prominently if capture conditions differ significantly"
    )
    deltas: ComparisonDeltaSchema = Field(..., description="Net metric changes between oldest and newest scan")
    face_shape_stable: bool = Field(..., description="Whether face shape remained consistent across scans")
    timeline: List[ScanTimelineItem] = Field(..., description="Chronological metrics for each compared scan")

