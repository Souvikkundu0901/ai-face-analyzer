"""
SQLAlchemy ORM models for User, RefreshToken, and Scan.
Uses JSONB on PostgreSQL and JSON on SQLite for flexible, migration-friendly schema.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.session import Base

# Dialect-agnostic JSON column type (JSONB on PostgreSQL, JSON on SQLite)
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")


def utc_now():
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class User(Base):
    """User account entity."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationships
    scans = relationship(
        "Scan",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="desc(Scan.created_at)"
    )
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """Database-backed refresh token for explicit revocation and rotation."""
    __tablename__ = "refresh_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")


class Scan(Base):
    """Persisted face and skin scan entity."""
    __tablename__ = "scans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pipeline_version = Column(String(64), nullable=False)
    image_quality = Column(JSON_TYPE, nullable=False)
    face_metrics = Column(JSON_TYPE, nullable=False)
    skin_metrics = Column(JSON_TYPE, nullable=False)
    regions = Column(JSON_TYPE, nullable=False)
    recommendation_ids = Column(JSON_TYPE, nullable=False)
    report = Column(JSON_TYPE, nullable=False)
    image_ref = Column(String(512), nullable=True)  # None by default (no image retention)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    user = relationship("User", back_populates="scans")
