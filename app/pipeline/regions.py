"""
Region representation and coordinate normalization utilities.
"""
from typing import Dict, Any


def create_region_dict(
    x: float,
    y: float,
    radius: float,
    confidence: float,
    region_type: str = "spot_like_region"
) -> Dict[str, Any]:
    """
    Format a normalized detected region.
    Coordinates x, y, and radius are relative to image dimensions [0.0 - 1.0].
    """
    return {
        "type": region_type,
        "x": round(float(x), 4),
        "y": round(float(y), 4),
        "radius": round(float(radius), 4),
        "confidence": round(float(confidence), 2)
    }
