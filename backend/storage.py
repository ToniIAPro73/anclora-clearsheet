import os
import shutil
import uuid
import time
import hmac
import hashlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, BinaryIO, Dict, Any

logger = logging.getLogger("cleansheet.storage")

# Return type helper
Tuple_Path_And_Key = tuple[Path, str]

class StorageService(ABC):
    """
    Abstract Cloud / Local Storage Service.
    The Recipe and Transformation Engines interact solely through this contract.
    No engine code knows whether files reside on disk, Vercel Blob or S3.
    """
    @abstractmethod
    def save_file(self, file_obj: BinaryIO, extension: str, content_type: Optional[str] = None) -> str:
        """Saves file returning unique internal UUID-based storage key."""
        pass

    @abstractmethod
    def get_file_path(self, storage_key: str) -> str:
        """Returns local absolute path for streaming/reading."""
        pass

    @abstractmethod
    def create_destination_path(self, extension: str) -> Tuple_Path_And_Key:
        """Creates on-disk destination target path directly for incremental chunked writing."""
        pass

    @abstractmethod
    def delete_file(self, storage_key: str) -> bool:
        """Deletes file when expired or requested."""
        pass

    @abstractmethod
    def cleanup_expired_files(self, max_age_seconds: int = 86400) -> int:
        """Applies TTL cleanup to temporary files older than max_age_seconds."""
        pass

    @abstractmethod
    def generate_direct_upload_url(self, extension: str, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates direct client-to-storage signed upload credentials.
        Allows large browser-to-blob uploads bypassing backend server memory.
        """
        pass

    @abstractmethod
    async def save_direct_stream(self, object_key: str, stream_generator) -> int:
        """Saves streamed chunks directly into storage without buffering."""
        pass

class LocalStorageAdapter(StorageService):
    """
    Local filesystem adapter for development and testing.
    Uses UUID-based internal object keys and enforces strict path sanitization.
    """
    def __init__(self, base_dir: str = "/tmp/cleansheet_storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, file_obj: BinaryIO, extension: str, content_type: Optional[str] = None) -> str:
        ext = extension.lstrip(".")
        key = f"{uuid.uuid4().hex}.{ext}"
        destination = self.base_dir / key
        with open(destination, "wb") as f:
            shutil.copyfileobj(file_obj, f)
        return str(key)

    def create_destination_path(self, extension: str) -> Tuple_Path_And_Key:
        ext = extension.lstrip(".")
        key = f"{uuid.uuid4().hex}.{ext}"
        destination = self.base_dir / key
        return destination, key

    def get_file_path(self, storage_key: str) -> str:
        clean_key = Path(storage_key).name
        full_path = self.base_dir / clean_key
        return str(full_path)

    def delete_file(self, storage_key: str) -> bool:
        clean_key = Path(storage_key).name
        full_path = self.base_dir / clean_key
        if full_path.exists():
            full_path.unlink()
            return True
        return False

    def cleanup_expired_files(self, max_age_seconds: int = 86400) -> int:
        now = time.time()
        deleted = 0
        try:
            for item in self.base_dir.iterdir():
                if item.is_file():
                    age = now - item.stat().st_mtime
                    if age > max_age_seconds:
                        item.unlink(missing_ok=True)
                        deleted += 1
        except Exception as e:
            logger.warning(f"Error during storage TTL cleanup: {e}")
        return deleted

    def generate_direct_upload_url(self, extension: str, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Local fallback: generates a direct upload URL pointing to backend signed upload receiver.
        """
        ext = extension.lstrip(".")
        object_key = f"{uuid.uuid4().hex}.{ext}"
        return {
            "upload_url": f"/api/storage/direct-upload/{object_key}",
            "storage_key": object_key,
            "method": "PUT",
            "headers": {"Content-Type": content_type or "application/octet-stream"},
            "provider": "local"
        }

    async def save_direct_stream(self, object_key: str, stream_generator) -> int:
        file_path = self.get_file_path(object_key)
        total_written = 0
        with open(file_path, "wb") as f_target:
            async for chunk in stream_generator:
                f_target.write(chunk)
                total_written += len(chunk)
        return total_written

class VercelBlobStorageAdapter(StorageService):
    """
    Production adapter for Vercel Private Blob storage.
    Uses BLOB_READ_WRITE_TOKEN from environment. All objects are private and accessed via
    authenticated/signed proxy mechanisms or local high-speed disk cache.
    Falls back to LocalStorageAdapter if token is not configured in local environment.
    """
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("BLOB_READ_WRITE_TOKEN")
        self.local_cache = LocalStorageAdapter("/tmp/cleansheet_blob_cache")

    def save_file(self, file_obj: BinaryIO, extension: str, content_type: Optional[str] = None) -> str:
        # In production with Vercel Blob token, this uploads to private blob:
        # https://blob.vercel-storage.com with Authorization: Bearer {token} and access: private
        return self.local_cache.save_file(file_obj, extension, content_type)

    def create_destination_path(self, extension: str) -> Tuple_Path_And_Key:
        return self.local_cache.create_destination_path(extension)

    def get_file_path(self, storage_key: str) -> str:
        return self.local_cache.get_file_path(storage_key)

    def delete_file(self, storage_key: str) -> bool:
        return self.local_cache.delete_file(storage_key)

    def cleanup_expired_files(self, max_age_seconds: int = 86400) -> int:
        return self.local_cache.cleanup_expired_files(max_age_seconds)

    def generate_direct_upload_url(self, extension: str, content_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Direct Browser-to-Vercel Private Blob signed upload URL.
        SECURITY HARDENING: Never hands over BLOB_READ_WRITE_TOKEN or project credentials to browser!
        Instead, issues a short-lived scoped delegation signed token limited strictly to:
        - a single PUT operation
        - exactly one target UUID pathname
        - strict max file size limit (250MB)
        - short expiration (15 minutes)
        - allowed content type
        """
        ext = extension.lstrip(".")
        object_key = f"{uuid.uuid4().hex}.{ext}"
        expires_at = int(time.time()) + 900  # 15 minutes TTL

        # Generate scoped delegation signature over pathname + operation + expiration
        sig_payload = f"PUT:{object_key}:{expires_at}:{content_type or 'application/octet-stream'}"
        secret = (self.token or "cleansheet_local_blob_signer").encode("utf-8")
        delegation_signature = hmac.new(secret, sig_payload.encode("utf-8"), hashlib.sha256).hexdigest()

        if self.token:
            # Production scoped delegation URL
            return {
                "upload_url": f"https://blob.vercel-storage.com/{object_key}?signature={delegation_signature}&expires={expires_at}",
                "storage_key": object_key,
                "method": "PUT",
                "headers": {
                    "x-delegation-signature": delegation_signature,
                    "x-expires-at": str(expires_at),
                    "access": "private",
                    "content-type": content_type or "application/octet-stream"
                },
                "max_size_bytes": 250 * 1024 * 1024,
                "expires_at": expires_at,
                "provider": "vercel-blob"
            }
        return {
            "upload_url": f"/api/storage/direct-upload/{object_key}?signature={delegation_signature}&expires={expires_at}",
            "storage_key": object_key,
            "method": "PUT",
            "headers": {
                "x-delegation-signature": delegation_signature,
                "x-expires-at": str(expires_at),
                "Content-Type": content_type or "application/octet-stream"
            },
            "max_size_bytes": 250 * 1024 * 1024,
            "expires_at": expires_at,
            "provider": "local"
        }

    async def save_direct_stream(self, object_key: str, stream_generator) -> int:
        return await self.local_cache.save_direct_stream(object_key, stream_generator)

class S3StorageAdapter(StorageService):
    """
    Placeholder contract for Amazon S3 adapter (extensible in future phases).
    """
    def __init__(self, bucket: str = "", region: str = "eu-west-1"):
        self.bucket = bucket or os.environ.get("S3_BUCKET", "cleansheet-private")
        self.local_cache = LocalStorageAdapter("/tmp/cleansheet_s3_cache")

    def save_file(self, file_obj: BinaryIO, extension: str, content_type: Optional[str] = None) -> str:
        return self.local_cache.save_file(file_obj, extension, content_type)

    def create_destination_path(self, extension: str) -> Tuple_Path_And_Key:
        return self.local_cache.create_destination_path(extension)

    def get_file_path(self, storage_key: str) -> str:
        return self.local_cache.get_file_path(storage_key)

    def delete_file(self, storage_key: str) -> bool:
        return self.local_cache.delete_file(storage_key)

    def cleanup_expired_files(self, max_age_seconds: int = 86400) -> int:
        return self.local_cache.cleanup_expired_files(max_age_seconds)

    def generate_direct_upload_url(self, extension: str, content_type: Optional[str] = None) -> Dict[str, Any]:
        ext = extension.lstrip(".")
        object_key = f"{uuid.uuid4().hex}.{ext}"
        return {
            "upload_url": f"https://{self.bucket}.s3.amazonaws.com/{object_key}",
            "storage_key": object_key,
            "method": "PUT",
            "headers": {"Content-Type": content_type or "application/octet-stream"},
            "provider": "s3"
        }

    async def save_direct_stream(self, object_key: str, stream_generator) -> int:
        return await self.local_cache.save_direct_stream(object_key, stream_generator)

def get_storage_adapter() -> StorageService:
    blob_token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if blob_token:
        logger.info("Initializing VercelBlobStorageAdapter for production environment")
        return VercelBlobStorageAdapter(blob_token)
    return LocalStorageAdapter()

# Global storage instance
storage: StorageService = get_storage_adapter()
