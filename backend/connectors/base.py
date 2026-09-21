from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, BinaryIO, Generator, Any, Dict

@dataclass
class ObjectRef:
    """Provider-neutral representation of a remote storage object."""
    key: str
    size_bytes: int
    last_modified: Optional[datetime] = None
    etag: Optional[str] = None
    content_type: Optional[str] = None

@dataclass
class ObjectMetadata:
    """Detailed metadata for a specific remote object."""
    key: str
    size_bytes: int
    last_modified: Optional[datetime] = None
    etag: Optional[str] = None
    content_type: Optional[str] = None
    custom_metadata: Optional[Dict[str, str]] = None

@dataclass
class ObjectListResult:
    """Paginated listing of objects from external storage."""
    objects: List[ObjectRef]
    next_cursor: Optional[str] = None
    is_truncated: bool = False
    prefix: str = ""

class ExternalStorageConnector(ABC):
    """
    Abstract interface for user-owned external storage connectors (S3, Google Drive, OneDrive, etc.).
    Keeps domain and execution logic 100% agnostic of specific cloud provider SDKs.
    """

    @abstractmethod
    def test_connection(self) -> Dict[str, Any]:
        """
        Validates credentials and permissions against the remote service.
        Returns a dict: {"success": bool, "message": str, "details": Optional[dict]}.
        """
        pass

    @abstractmethod
    def list_objects(self, prefix: str = "", cursor: Optional[str] = None, max_keys: int = 100) -> ObjectListResult:
        """Lists objects under a given prefix with pagination support."""
        pass

    @abstractmethod
    def get_object_metadata(self, key: str) -> ObjectMetadata:
        """Retrieves metadata (size, content-type, etag, last_modified) for a specific object."""
        pass

    @abstractmethod
    def read_stream(self, key: str, chunk_size: int = 1024 * 1024) -> Generator[bytes, None, None]:
        """Streams object bytes in chunks without loading the entire object into memory."""
        pass

    @abstractmethod
    def write_stream(self, key: str, stream: BinaryIO, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        """Uploads a data stream to the target path. Returns metadata of the written object."""
        pass
