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
