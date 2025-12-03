"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel
from typing import List, Optional


class RenditionOut(BaseModel):
    """Rendition output schema."""
    id: int
    preset: str
    url: str
    size_bytes: int
    width: int
    height: int
    quality: int
    
    class Config:
        from_attributes = True


class AssetOut(BaseModel):
    """Asset output schema."""
    id: int
    tenant_id: int
    content_hash: str
    original_filename: str
    original_size_bytes: int
    original_width: int
    original_height: int
    in_use_count: int
    renditions: List[RenditionOut]
    
    class Config:
        from_attributes = True


class ComparePresetResult(BaseModel):
    """Result for a single preset in compare endpoint."""
    preset: str
    size_bytes: int
    width: int
    height: int
    quality_metric: float  # Simple metric (dimension-to-size ratio)


class CompareResponse(BaseModel):
    """Compare endpoint response."""
    results: List[ComparePresetResult]
    recommended: str  # Recommended preset name


class PurgeRequest(BaseModel):
    """Purge endpoint request."""
    dry_run: bool = True
    confirm_token: Optional[str] = None


class PurgeResponse(BaseModel):
    """Purge endpoint response."""
    dry_run: bool
    candidates: List[str]  # List of content_hashes
    deleted_count: int = 0


class MetricsResponse(BaseModel):
    """Metrics endpoint response."""
    tenant_counts: dict  # {tenant_name: asset_count}
    bytes_per_preset: dict  # {preset: total_bytes}

