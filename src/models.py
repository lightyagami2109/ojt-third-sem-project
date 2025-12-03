"""SQLAlchemy async models."""
from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, Index
from sqlalchemy.orm import relationship
from src.db import Base


class Tenant(Base):
    """Tenant model (multi-tenancy support)."""
    __tablename__ = "tenants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    
    # Relationships
    assets = relationship("Asset", back_populates="tenant", cascade="all, delete-orphan")


class Asset(Base):
    """Asset model representing an uploaded image."""
    __tablename__ = "assets"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    content_hash = Column(String(64), unique=True, index=True, nullable=False)  # SHA256 hex
    original_filename = Column(String, nullable=False)
    original_size_bytes = Column(BigInteger, nullable=False)
    original_width = Column(Integer, nullable=False)
    original_height = Column(Integer, nullable=False)
    phash = Column(String(16), index=True, nullable=False)  # Perceptual hash (hex)
    in_use_count = Column(Integer, default=0, nullable=False)  # Safety counter for purge
    
    # Relationships
    tenant = relationship("Tenant", back_populates="assets")
    renditions = relationship("Rendition", back_populates="asset", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_asset_content_hash", "content_hash"),
        Index("idx_asset_phash", "phash"),
    )


class Rendition(Base):
    """Rendition model representing a processed image variant."""
    __tablename__ = "renditions"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False, index=True)
    preset = Column(String, nullable=False, index=True)
    url = Column(String, nullable=False)  # Storage URL/path
    size_bytes = Column(BigInteger, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    quality = Column(Integer, nullable=False)  # JPEG quality (1-100)
    phash = Column(String(16), index=True, nullable=False)  # Perceptual hash of rendition
    
    # Relationships
    asset = relationship("Asset", back_populates="renditions")
    
    # Indexes
    __table_args__ = (
        Index("idx_rendition_asset_preset", "asset_id", "preset", unique=True),
        Index("idx_rendition_phash", "phash"),
    )


class Job(Base):
    """Job model (lightweight placeholder for future async job tracking)."""
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=True)
    status = Column(String, default="pending", nullable=False)
    error_message = Column(String, nullable=True)
    
    # Note: In production with external workers, this would track:
    # - job_type, created_at, started_at, completed_at
    # - retry_count, priority, worker_id

