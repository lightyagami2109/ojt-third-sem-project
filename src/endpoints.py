"""API endpoints for image processing pipeline."""
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
import asyncio

from src.db import get_db
from src.models import Asset, Rendition, Tenant, Job
from src.schemas import (
    AssetOut, CompareResponse, ComparePresetResult,
    PurgeRequest, PurgeResponse, MetricsResponse
)
from src.settings import settings
from src.storage import get_storage_adapter
from src.image_utils import (
    compute_content_hash, compute_phash, is_near_duplicate,
    generate_rendition_bytes, open_image_from_bytes, compute_quality_metric
)

router = APIRouter(prefix=settings.API_V1_PREFIX)


async def get_or_create_tenant(db: AsyncSession, tenant_name: str) -> Tenant:
    """Get or create a tenant."""
    result = await db.execute(select(Tenant).where(Tenant.name == tenant_name))
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        tenant = Tenant(name=tenant_name)
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
    
    return tenant


@router.post("/images", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def upload_image(
    tenant: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload an image and generate renditions.
    
    Implements idempotency via content_hash: same content returns existing asset.
    Implements perceptual hash reuse: near-duplicates reuse existing renditions.
    
    Note: Rendition generation happens inline. For production with heavy workloads,
    move this to an external worker (Render/Railway) with a job queue.
    """
    # Validate file size
    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {settings.MAX_UPLOAD_BYTES} bytes"
        )
    
    # Compute content hash for idempotency
    content_hash = compute_content_hash(file_bytes)
    
    # Check if asset with this content_hash already exists
    result = await db.execute(
        select(Asset).where(Asset.content_hash == content_hash)
    )
    existing_asset = result.scalar_one_or_none()
    
    if existing_asset:
        # Return existing asset with renditions
        await db.refresh(existing_asset, ["renditions", "tenant"])
        return AssetOut.model_validate(existing_asset)
    
    # Open image and get metadata
    try:
        image = open_image_from_bytes(file_bytes)
        original_width, original_height = image.size
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image file: {str(e)}"
        )
    
    # Compute perceptual hash
    phash = compute_phash(image)
    
    # Get or create tenant
    tenant_obj = await get_or_create_tenant(db, tenant)
    
    # Create asset
    asset = Asset(
        tenant_id=tenant_obj.id,
        content_hash=content_hash,
        original_filename=file.filename or "unknown",
        original_size_bytes=len(file_bytes),
        original_width=original_width,
        original_height=original_height,
        phash=phash,
        in_use_count=0
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    
    # Generate renditions inline (for production, move to external worker)
    storage = get_storage_adapter()
    renditions_created = []
    
    for preset_name, (width, height) in settings.PRESETS.items():
        # Check for near-duplicate rendition by perceptual hash
        # Look for existing renditions with similar phash
        result = await db.execute(
            select(Rendition).where(
                Rendition.preset == preset_name,
                Rendition.asset_id != asset.id  # Different asset
            )
        )
        existing_renditions = result.scalars().all()
        
        reuse_rendition = None
        for existing_rend in existing_renditions:
            if is_near_duplicate(phash, existing_rend.phash):
                # Reuse existing rendition
                reuse_rendition = existing_rend
                break
        
        if reuse_rendition:
            # Create new rendition record pointing to reused storage
            rendition = Rendition(
                asset_id=asset.id,
                preset=preset_name,
                url=reuse_rendition.url,  # Reuse storage URL
                size_bytes=reuse_rendition.size_bytes,
                width=reuse_rendition.width,
                height=reuse_rendition.height,
                quality=reuse_rendition.quality,
                phash=reuse_rendition.phash
            )
            db.add(rendition)
            renditions_created.append(rendition)
        else:
            # Generate new rendition
            rendition_bytes, actual_width, actual_height = generate_rendition_bytes(
                image, preset_name, width, height, quality=85
            )
            
            # Compute phash of rendition
            rendition_image = open_image_from_bytes(rendition_bytes)
            rendition_phash = compute_phash(rendition_image)
            
            # Save to storage
            storage_key = f"renditions/{content_hash[:8]}/{preset_name}.jpg"
            storage_url = await storage.save(storage_key, rendition_bytes)
            
            # Create rendition record
            rendition = Rendition(
                asset_id=asset.id,
                preset=preset_name,
                url=storage_url,
                size_bytes=len(rendition_bytes),
                width=actual_width,
                height=actual_height,
                quality=85,
                phash=rendition_phash
            )
            db.add(rendition)
            renditions_created.append(rendition)
    
    await db.commit()
    
    # Refresh to load relationships
    await db.refresh(asset, ["renditions", "tenant"])
    
    return AssetOut.model_validate(asset)


@router.get("/images/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get asset by ID with renditions."""
    result = await db.execute(
        select(Asset).where(Asset.id == asset_id)
    )
    asset = result.scalar_one_or_none()
    
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset {asset_id} not found"
        )
    
    await db.refresh(asset, ["renditions", "tenant"])
    return AssetOut.model_validate(asset)


@router.post("/compare", response_model=CompareResponse)
async def compare_image(
    file: UploadFile = File(...)
):
    """
    Compare image against presets and return size/quality metrics.
    
    Returns recommended preset based on quality metric.
    """
    file_bytes = await file.read()
    
    if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {settings.MAX_UPLOAD_BYTES} bytes"
        )
    
    try:
        image = open_image_from_bytes(file_bytes)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid image file: {str(e)}"
        )
    
    results = []
    
    for preset_name, (width, height) in settings.PRESETS.items():
        # Generate rendition to measure
        rendition_bytes, actual_width, actual_height = generate_rendition_bytes(
            image, preset_name, width, height, quality=85
        )
        
        quality_metric = compute_quality_metric(
            actual_width, actual_height, len(rendition_bytes)
        )
        
        results.append(ComparePresetResult(
            preset=preset_name,
            size_bytes=len(rendition_bytes),
            width=actual_width,
            height=actual_height,
            quality_metric=quality_metric
        ))
    
    # Recommend preset with highest quality metric
    recommended = max(results, key=lambda r: r.quality_metric).preset
    
    return CompareResponse(results=results, recommended=recommended)


@router.post("/purge", response_model=PurgeResponse)
async def purge_assets(
    request: PurgeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Purge unused assets (in_use_count == 0).
    
    Requires confirm_token for non-dry-run operations.
    Never deletes assets with in_use_count > 0.
    """
    if not request.dry_run:
        if not request.confirm_token or request.confirm_token != settings.PURGE_CONFIRM_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="confirm_token required and must match configured token for destructive operations"
            )
    
    # Find candidates (assets with in_use_count == 0)
    result = await db.execute(
        select(Asset).where(Asset.in_use_count == 0)
    )
    candidates = result.scalars().all()
    candidate_hashes = [asset.content_hash for asset in candidates]
    
    if request.dry_run:
        return PurgeResponse(
            dry_run=True,
            candidates=candidate_hashes,
            deleted_count=0
        )
    
    # Delete candidates
    storage = get_storage_adapter()
    deleted_count = 0
    
    for asset in candidates:
        # Delete renditions from storage
        for rendition in asset.renditions:
            try:
                await storage.delete(rendition.url)
            except Exception:
                pass  # Continue even if storage delete fails
        
        # Delete asset (cascade will delete renditions from DB)
        await db.delete(asset)
        deleted_count += 1
    
    await db.commit()
    
    return PurgeResponse(
        dry_run=False,
        candidates=candidate_hashes,
        deleted_count=deleted_count
    )


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics(
    db: AsyncSession = Depends(get_db)
):
    """Get usage metrics: tenant counts and bytes per preset."""
    # Tenant asset counts
    result = await db.execute(
        select(Tenant.name, func.count(Asset.id).label("count"))
        .join(Asset)
        .group_by(Tenant.name)
    )
    tenant_counts = {row[0]: row[1] for row in result.all()}
    
    # Bytes per preset
    result = await db.execute(
        select(Rendition.preset, func.sum(Rendition.size_bytes).label("total_bytes"))
        .group_by(Rendition.preset)
    )
    bytes_per_preset = {row[0]: row[1] or 0 for row in result.all()}
    
    return MetricsResponse(
        tenant_counts=tenant_counts,
        bytes_per_preset=bytes_per_preset
    )

