"""
Pydantic schemas for LLM input/output validation.

These schemas enforce structure on LLM responses so that malformed
or off-schema output is caught before it reaches the user.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class LLMInput(BaseModel):
    """Structured input sent to the LLM for explanation generation."""
    triggered_recommendations: List[str] = Field(
        ..., description="List of recommendation IDs from the rules engine"
    )
    supporting_scores: Dict[str, Any] = Field(
        ..., description="Relevant scores that support the triggered recommendations"
    )
    face_shape: str = Field(
        default="unknown", description="Detected face shape classification"
    )


class ExplanationItem(BaseModel):
    """A single recommendation explanation from the LLM."""
    id: str = Field(..., description="The recommendation ID being explained")
    text: str = Field(..., description="1-2 sentence observational explanation")


class LLMReport(BaseModel):
    """Expected structured output from the LLM."""
    explanations: List[ExplanationItem] = Field(
        ..., description="One explanation per triggered recommendation"
    )
    summary: str = Field(
        ..., description="One closing summary paragraph"
    )
