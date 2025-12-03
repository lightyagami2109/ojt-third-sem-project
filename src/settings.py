"""Application settings using Pydantic BaseSettings."""
from pydantic_settings import BaseSettings
from typing import Dict, Tuple
import os


class Settings(BaseSettings):
    """Application configuration."""
    
    # Database
    # For local dev: sqlite+aiosqlite:///./catalog_images.db
    # For Vercel: Use Vercel Postgres connection string from environment
    # Format: postgresql+asyncpg://user:password@host:port/database
    DATABASE_URL: str = "sqlite+aiosqlite:///./catalog_images.db"
    
    # Storage
    # Auto-detect: if BLOB_READ_WRITE_TOKEN exists, use vercel_blob, else local
    _blob_token = os.getenv("BLOB_READ_WRITE_TOKEN")
    STORAGE_TYPE: str = "vercel_blob" if _blob_token else "local"  # 'local', 'vercel_blob', or 's3'
    STORAGE_BASE_PATH: str = "./storage"  # For local storage
    
    # Vercel Blob Storage (when STORAGE_TYPE=vercel_blob)
    # BLOB_READ_WRITE_TOKEN is automatically set by Vercel when Blob Storage is enabled
    
    # S3 settings (for future S3 adapter)
    # AWS_ACCESS_KEY_ID: str = ""
    # AWS_SECRET_ACCESS_KEY: str = ""
    # AWS_S3_BUCKET: str = ""
    # AWS_S3_REGION: str = "us-east-1"
    
    # Upload limits
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10MB
    
    # Image presets: (width, height) tuples
    PRESETS: Dict[str, Tuple[int, int]] = {
        "thumb": (200, 200),
        "card": (600, 400),
        "zoom": (1600, 1600),
    }
    
    # Perceptual hash settings
    PHASH_SIZE: int = 8  # aHash size (8x8 = 64 bits)
    PHASH_HAMMING_THRESHOLD: int = 5  # Max hamming distance for near-duplicate detection
    
    # Purge settings
    PURGE_CONFIRM_TOKEN: str = "DELETE_CONFIRMED"  # In production, use secure token
    
    # Server settings
    API_V1_PREFIX: str = "/v1"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
