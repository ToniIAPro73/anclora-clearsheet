import pytest
import io
import os
import time
from pathlib import Path
from storage import LocalStorageAdapter, VercelBlobStorageAdapter, S3StorageAdapter, get_storage_adapter

def test_local_storage_adapter_crud():
    adapter = LocalStorageAdapter("/tmp/test_storage_adapter")
    data = b"Hello Anclora CleanSheet Storage Adapter"

    # Save
    key = adapter.save_file(io.BytesIO(data), "csv")
    assert key.endswith(".csv")

    # Read path
    file_path = adapter.get_file_path(key)
    assert os.path.exists(file_path)
    with open(file_path, "rb") as f:
        assert f.read() == data

    # Direct destination path
    dest_path, key2 = adapter.create_destination_path("xlsx")
    assert dest_path.name.endswith(".xlsx")
    assert key2.endswith(".xlsx")

    # Delete
    assert adapter.delete_file(key) is True
    assert not os.path.exists(file_path)

def test_storage_ttl_cleanup():
    adapter = LocalStorageAdapter("/tmp/test_storage_ttl")
    key = adapter.save_file(io.BytesIO(b"old_data"), "csv")
    file_path = adapter.get_file_path(key)

    # Artificially modify mtime to 2 hours ago
    past_time = time.time() - 7200
    os.utime(file_path, (past_time, past_time))

    # Clean files older than 3600 seconds
    deleted = adapter.cleanup_expired_files(max_age_seconds=3600)
    assert deleted >= 1
    assert not os.path.exists(file_path)

def test_vercel_blob_adapter_fallback_contract():
    # Adapter without token operates safely via local cache preserving exact interface
    adapter = VercelBlobStorageAdapter(token=None)
    key = adapter.save_file(io.BytesIO(b"Blob content"), "xlsx")
    assert key.endswith(".xlsx")

    path = adapter.get_file_path(key)
    assert os.path.exists(path)
    assert adapter.delete_file(key) is True

def test_s3_adapter_contract():
    adapter = S3StorageAdapter(bucket="test-bucket")
    key = adapter.save_file(io.BytesIO(b"S3 content"), "csv")
    assert key.endswith(".csv")
    assert adapter.delete_file(key) is True
