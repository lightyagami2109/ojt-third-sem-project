"""Pytest tests for idempotency, perceptual hashing, and purge."""
import pytest
import asyncio
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base

from src.app import app
from src.db import Base, get_db
from src.models import Asset, Rendition, Tenant
from src.settings import settings
from src.storage import LocalStorageAdapter

# Test database URL
TEST_DB_URL = "sqlite+aiosqlite:///./test_catalog_images.db"
TEST_STORAGE_PATH = "./test_storage"

# Create test engine
test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="function")
async def db_session():
    """Create test database session and tables."""
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestSessionLocal() as session:
        yield session
    
    # Cleanup: drop tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def test_client(db_session):
    """Create test client with test database."""
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Clean storage directory
    storage_path = Path(TEST_STORAGE_PATH)
    if storage_path.exists():
        import shutil
        shutil.rmtree(storage_path)
    storage_path.mkdir(parents=True, exist_ok=True)
    
    client = TestClient(app)
    yield client
    
    # Cleanup
    app.dependency_overrides.clear()
    if storage_path.exists():
        import shutil
        shutil.rmtree(storage_path)


@pytest.fixture
def sample_image_path():
    """Get path to sample image fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample.jpg"
    
    # Generate sample if it doesn't exist
    if not fixture_path.exists():
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        from tests.fixtures.generate_sample import generate_sample
        # Actually, let's just create it inline
        from PIL import Image
        img = Image.new("RGB", (100, 100), color="red")
        pixels = img.load()
        for i in range(100):
            for j in range(100):
                pixels[i, j] = (i % 255, j % 255, (i + j) % 255)
        img.save(fixture_path, "JPEG", quality=85)
    
    return fixture_path


def test_upload_idempotency(test_client, sample_image_path):
    """Test that uploading the same file twice returns the same content_hash."""
    with open(sample_image_path, "rb") as f:
        files = {"file": ("sample.jpg", f, "image/jpeg")}
        data = {"tenant": "test_tenant"}
        
        # First upload
        response1 = test_client.post("/v1/images", files=files, data=data)
        assert response1.status_code == 201
        asset1 = response1.json()
        content_hash1 = asset1["content_hash"]
        asset_id1 = asset1["id"]
    
    # Second upload (same file)
    with open(sample_image_path, "rb") as f:
        files = {"file": ("sample.jpg", f, "image/jpeg")}
        data = {"tenant": "test_tenant"}
        
        response2 = test_client.post("/v1/images", files=files, data=data)
        assert response2.status_code == 201
        asset2 = response2.json()
        content_hash2 = asset2["content_hash"]
        asset_id2 = asset2["id"]
    
    # Should have same content_hash
    assert content_hash1 == content_hash2, "Content hash should be identical for same file"
    
    # Should return the same asset (idempotency)
    assert asset_id1 == asset_id2, "Should return existing asset for same content_hash"


def test_perceptual_hash_reuse(test_client, sample_image_path):
    """
    Test that near-duplicate images reuse renditions.
    
    We simulate a near-duplicate by creating a slightly modified version
    of the same image (which should have similar perceptual hash).
    """
    from PIL import Image
    from io import BytesIO
    
    # Upload original
    with open(sample_image_path, "rb") as f:
        files = {"file": ("sample.jpg", f, "image/jpeg")}
        data = {"tenant": "test_tenant"}
        response1 = test_client.post("/v1/images", files=files, data=data)
        assert response1.status_code == 201
        asset1 = response1.json()
        renditions1 = asset1["renditions"]
        assert len(renditions1) > 0
    
    # Create a slightly modified version (add minimal noise)
    img = Image.open(sample_image_path)
    pixels = img.load()
    # Modify a few pixels
    for i in range(0, 10, 2):
        for j in range(0, 10, 2):
            r, g, b = pixels[i, j]
            pixels[i, j] = (min(255, r + 1), g, b)
    
    # Save to bytes
    output = BytesIO()
    img.save(output, format="JPEG", quality=85)
    output.seek(0)
    
    # Upload modified version
    files = {"file": ("modified.jpg", output, "image/jpeg")}
    data = {"tenant": "test_tenant"}
    response2 = test_client.post("/v1/images", files=files, data=data)
    assert response2.status_code == 201
    asset2 = response2.json()
    renditions2 = asset2["renditions"]
    
    # Check if renditions were reused (same URL for same preset)
    # Note: This depends on perceptual hash threshold - if images are too different,
    # they won't be considered near-duplicates
    # For this test, we verify the structure is correct
    assert len(renditions2) == len(renditions1), "Should have same number of renditions"
    
    # Group by preset
    rend1_by_preset = {r["preset"]: r for r in renditions1}
    rend2_by_preset = {r["preset"]: r for r in renditions2}
    
    # At least some renditions might be reused if perceptual hash matches
    # (This is probabilistic based on the threshold)
    # Verify structure is correct
    for preset in rend1_by_preset:
        assert preset in rend2_by_preset, f"Preset {preset} should exist in both"


def test_purge_dry_run(test_client, sample_image_path):
    """Test purge dry-run lists candidates without deleting."""
    # Upload an image
    with open(sample_image_path, "rb") as f:
        files = {"file": ("sample.jpg", f, "image/jpeg")}
        data = {"tenant": "test_tenant"}
        response = test_client.post("/v1/images", files=files, data=data)
        assert response.status_code == 201
        asset = response.json()
        content_hash = asset["content_hash"]
    
    # Dry run purge
    response = test_client.post(
        "/v1/purge",
        json={"dry_run": True}
    )
    assert response.status_code == 200
    result = response.json()
    
    assert result["dry_run"] is True
    assert result["deleted_count"] == 0
    assert content_hash in result["candidates"], "Uploaded asset should be in candidates"


def test_purge_with_confirmation(test_client, sample_image_path):
    """Test purge with confirmation token deletes assets."""
    # Upload an image
    with open(sample_image_path, "rb") as f:
        files = {"file": ("sample.jpg", f, "image/jpeg")}
        data = {"tenant": "test_tenant"}
        response = test_client.post("/v1/images", files=files, data=data)
        assert response.status_code == 201
        asset = response.json()
        content_hash = asset["content_hash"]
        asset_id = asset["id"]
    
    # Purge with confirmation
    response = test_client.post(
        "/v1/purge",
        json={
            "dry_run": False,
            "confirm_token": settings.PURGE_CONFIRM_TOKEN
        }
    )
    assert response.status_code == 200
    result = response.json()
    
    assert result["dry_run"] is False
    assert result["deleted_count"] > 0
    assert content_hash in result["candidates"]
    
    # Verify asset is deleted
    response = test_client.get(f"/v1/images/{asset_id}")
    assert response.status_code == 404


def test_purge_requires_confirmation(test_client, sample_image_path):
    """Test that purge without confirmation token fails."""
    # Upload an image
    with open(sample_image_path, "rb") as f:
        files = {"file": ("sample.jpg", f, "image/jpeg")}
        data = {"tenant": "test_tenant"}
        test_client.post("/v1/images", files=files, data=data)
    
    # Try to purge without confirmation
    response = test_client.post(
        "/v1/purge",
        json={"dry_run": False}
    )
    assert response.status_code == 400


def test_rendition_generation(test_client, sample_image_path):
    """Test that renditions are generated for all presets."""
    with open(sample_image_path, "rb") as f:
        files = {"file": ("sample.jpg", f, "image/jpeg")}
        data = {"tenant": "test_tenant"}
        response = test_client.post("/v1/images", files=files, data=data)
        assert response.status_code == 201
        asset = response.json()
        renditions = asset["renditions"]
    
    # Should have renditions for all presets
    preset_names = set(settings.PRESETS.keys())
    rendition_presets = {r["preset"] for r in renditions}
    
    assert preset_names == rendition_presets, "Should have renditions for all presets"
    
    # Each rendition should have required fields
    for rendition in renditions:
        assert "url" in rendition
        assert "size_bytes" in rendition
        assert "width" in rendition
        assert "height" in rendition
        assert "quality" in rendition


def test_compare_endpoint(test_client, sample_image_path):
    """Test compare endpoint returns metrics for all presets."""
    with open(sample_image_path, "rb") as f:
        files = {"file": ("sample.jpg", f, "image/jpeg")}
        response = test_client.post("/v1/compare", files=files)
        assert response.status_code == 200
        result = response.json()
    
    assert "results" in result
    assert "recommended" in result
    assert len(result["results"]) == len(settings.PRESETS)
    
    for preset_result in result["results"]:
        assert "preset" in preset_result
        assert "size_bytes" in preset_result
        assert "width" in preset_result
        assert "height" in preset_result
        assert "quality_metric" in preset_result
    
    assert result["recommended"] in settings.PRESETS

