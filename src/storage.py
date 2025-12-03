"""Storage adapter interface and implementations."""
from abc import ABC, abstractmethod
from typing import BinaryIO
import os
from pathlib import Path
from src.settings import settings


class StorageAdapter(ABC):
    """Abstract storage adapter interface (S3-style)."""
    
    @abstractmethod
    async def save(self, key: str, data: bytes) -> str:
        """
        Save data to storage and return URL/path.
        
        Args:
            key: Storage key/path (e.g., "renditions/abc123/thumb.jpg")
            data: Binary data to save
            
        Returns:
            URL or path string
        """
        pass
    
    @abstractmethod
    async def get(self, key: str) -> bytes:
        """
        Retrieve data from storage.
        
        Args:
            key: Storage key/path
            
        Returns:
            Binary data
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete data from storage.
        
        Args:
            key: Storage key/path
            
        Returns:
            True if deleted, False if not found
        """
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in storage.
        
        Args:
            key: Storage key/path
            
        Returns:
            True if exists, False otherwise
        """
        pass


class LocalStorageAdapter(StorageAdapter):
    """Local filesystem storage adapter (for development)."""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path or settings.STORAGE_BASE_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def _get_full_path(self, key: str) -> Path:
        """Get full filesystem path for a key."""
        # Sanitize key to prevent directory traversal
        key = key.lstrip("/")
        return self.base_path / key
    
    async def save(self, key: str, data: bytes) -> str:
        """Save data to local filesystem."""
        full_path = self._get_full_path(key)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, "wb") as f:
            f.write(data)
        
        # Return relative path as URL for local storage
        return str(full_path.relative_to(self.base_path))
    
    async def get(self, key: str) -> bytes:
        """Retrieve data from local filesystem."""
        full_path = self._get_full_path(key)
        if not full_path.exists():
            raise FileNotFoundError(f"Key not found: {key}")
        
        with open(full_path, "rb") as f:
            return f.read()
    
    async def delete(self, key: str) -> bool:
        """Delete data from local filesystem."""
        full_path = self._get_full_path(key)
        if not full_path.exists():
            return False
        
        full_path.unlink()
        return True
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in local filesystem."""
        full_path = self._get_full_path(key)
        return full_path.exists()


# Future S3 adapter (not implemented, placeholder for production)
# class S3StorageAdapter(StorageAdapter):
#     """S3 storage adapter (for production).
#     
#     In production, implement using boto3:
#     - Use settings.AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
#     - Use settings.AWS_S3_BUCKET, AWS_S3_REGION
#     - Generate presigned URLs for GET requests
#     - Handle retries and backoff for network errors
#     """
#     pass


def get_storage_adapter() -> StorageAdapter:
    """Factory function to get storage adapter based on settings."""
    if settings.STORAGE_TYPE == "local":
        return LocalStorageAdapter()
    # elif settings.STORAGE_TYPE == "s3":
    #     return S3StorageAdapter()
    else:
        raise ValueError(f"Unknown storage type: {settings.STORAGE_TYPE}")

