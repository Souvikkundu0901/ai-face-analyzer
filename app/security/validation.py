"""
Strict file upload validation and magic byte sniffing (Phase 5 Security Hardening).
Prevents MIME/extension spoofing, oversized uploads, and malformed image attacks.
"""
import io
import logging
from typing import Tuple
from PIL import Image, ImageOps
from fastapi import HTTPException, status

logger = logging.getLogger("ai_face_analyzer.security.validation")

# Magic byte signatures for supported image formats
MAGIC_SIGNATURES = {
    "jpeg": [
        b"\xFF\xD8\xFF\xDB",
        b"\xFF\xD8\xFF\xE0",
        b"\xFF\xD8\xFF\xE1",
        b"\xFF\xD8\xFF\xEE",
        b"\xFF\xD8\xFF\xE2",
        b"\xFF\xD8\xFF",
    ],
    "png": [
        b"\x89PNG\r\n\x1a\n",
    ],
    "webp": [
        b"RIFF",  # followed by length and WEBP at byte offset 8
    ]
}


def detect_image_type(raw_bytes: bytes) -> str:
    """
    Sniff magic bytes from image header.
    Returns format string ('jpeg', 'png', 'webp') or raises HTTPException.
    """
    if len(raw_bytes) < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is too small or truncated to be a valid image."
        )

    # PNG check
    if raw_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"

    # JPEG check
    if raw_bytes.startswith(b"\xFF\xD8\xFF"):
        return "jpeg"

    # WebP check (RIFF....WEBP)
    if raw_bytes.startswith(b"RIFF") and raw_bytes[8:12] == b"WEBP":
        return "webp"

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid file format. Magic byte inspection failed. Only genuine JPEG, PNG, or WebP images are allowed."
    )


def validate_image_upload(raw_bytes: bytes, max_size_bytes: int = 10 * 1024 * 1024) -> Tuple[str, Image.Image]:
    """
    Perform multi-layer validation on uploaded image payload:
    1. Enforces strict payload size limit (HTTP 413).
    2. Inspects magic bytes (HTTP 400).
    3. Verifies PIL decode and prevents decompression bombs (HTTP 400).

    Returns:
        Tuple of (detected_format, verified_pil_image)
    """
    # 1. Size check
    if len(raw_bytes) > max_size_bytes:
        max_mb = max_size_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload rejected: Image size ({len(raw_bytes) / (1024*1024):.1f}MB) exceeds maximum limit of {max_mb}MB."
        )

    # 2. Magic byte sniffing
    img_type = detect_image_type(raw_bytes)

    # 3. Pillow parser & integrity validation
    try:
        pil_img = Image.open(io.BytesIO(raw_bytes))
        pil_img.verify()  # Verifies file integrity without full decompression
        
        # Re-open for actual return because verify() mutates stream
        pil_img = Image.open(io.BytesIO(raw_bytes))
        # Ensure orientation normalization if EXIF present
        pil_img = ImageOps.exif_transpose(pil_img) or pil_img
        
        # Dimension sanity check (prevent decompression bombs)
        w, h = pil_img.size
        if w > 8192 or h > 8192 or (w * h) > 36_000_000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Upload rejected: Image dimensions ({w}x{h}) exceed safety limit."
            )
            
        return img_type, pil_img
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Image integrity verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted or malformed image payload could not be decoded."
        )
