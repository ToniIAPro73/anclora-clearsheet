from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from models import User
from auth import get_current_user_optional
from storage import storage

router = APIRouter(prefix="/storage", tags=["storage"])

class DirectUploadRequest(BaseModel):
    filename: str
    content_type: Optional[str] = "application/octet-stream"

@router.post("/direct-upload-url")
def request_direct_upload_url(
    req: DirectUploadRequest,
    user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Phase 2: Generates direct browser-to-storage signed upload credentials.
    Allows massive files (up to 250MB) to upload directly to Private Storage (Vercel Private Blob or local storage adapter),
    bypassing frontend server RAM and preventing server saturation.
    """
    ext = Path(req.filename).suffix.lower()
    credentials = storage.generate_direct_upload_url(extension=ext, content_type=req.content_type)
    return credentials

@router.put("/direct-upload/{object_key}")
async def receive_direct_upload(
    object_key: str,
    request: Request
):
    """
    Direct upload receiver stream writing to storage adapter.
    """
    total_written = await storage.save_direct_stream(object_key, request.stream())
    return {
        "status": "uploaded",
        "storage_key": object_key,
        "bytes_written": total_written
    }
