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


class VercelBlobStorageAdapter(StorageAdapter):
    """Vercel Blob Storage adapter (for Vercel deployment).
    
    Uses Vercel Blob REST API directly.
    BLOB_READ_WRITE_TOKEN is automatically available in Vercel environment.
    """
    
    def __init__(self):
        import os
        self.token = os.getenv("BLOB_READ_WRITE_TOKEN")
        if not self.token:
            raise ValueError(
                "BLOB_READ_WRITE_TOKEN not found. "
                "This is automatically set in Vercel environment."
            )
        self.base_url = "https://blob.vercel-storage.com"
    
    async def save(self, key: str, data: bytes) -> str:
        """Save data to Vercel Blob Storage and return URL."""
        import aiohttp
        
        url = f"{self.base_url}/{key}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "image/jpeg",
            "x-content-type": "image/jpeg",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.put(url, data=data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("url", url)
                else:
                    error_text = await response.text()
                    raise Exception(f"Failed to upload to Vercel Blob: {error_text}")
    
    async def get(self, key: str) -> bytes:
        """Retrieve data from Vercel Blob Storage."""
        import aiohttp
        
        # If key is already a full URL, use it directly
        url = key if key.startswith("http") else f"{self.base_url}/{key}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    raise FileNotFoundError(f"Blob not found: {key}")
    
    async def delete(self, key: str) -> bool:
        """Delete data from Vercel Blob Storage."""
        import aiohttp
        
        # Extract URL from key if it's a full URL
        if key.startswith("http"):
            url = key
        else:
            url = f"{self.base_url}/{key}"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers) as response:
                    return response.status in [200, 204]
        except Exception:
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in Vercel Blob Storage."""
        try:
            await self.get(key)
            return True
        except Exception:
            return False


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
    elif settings.STORAGE_TYPE == "vercel_blob":
        return VercelBlobStorageAdapter()
    # elif settings.STORAGE_TYPE == "s3":
    #     return S3StorageAdapter()
    else:
        raise ValueError(f"Unknown storage type: {settings.STORAGE_TYPE}")

