import io
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError, EndpointConnectionError
from connectors.s3_connector import S3CompatibleConnector
from connectors.base import ObjectRef, ObjectMetadata, ObjectListResult
from ssrf_validator import validate_s3_endpoint_url, SSRFProtectionError

def test_ssrf_validator_blocks_internal_and_metadata_ips():
    # Loopback
    valid, err = validate_s3_endpoint_url("http://127.0.0.1:9000")
    assert not valid
    assert "loopback" in err.lower() or "restringido" in err.lower()

    valid, err = validate_s3_endpoint_url("http://localhost:9000")
    assert not valid
    assert "restringido" in err.lower()

    # AWS Metadata 169.254.169.254
    valid, err = validate_s3_endpoint_url("http://169.254.169.254/latest/meta-data")
    assert not valid
    assert "metadata" in err.lower() or "link-local" in err.lower()

    # Private IP 10.0.0.1
    valid, err = validate_s3_endpoint_url("http://10.0.0.1:9000")
    assert not valid
    assert "privada" in err.lower()

    # Non-http scheme
    valid, err = validate_s3_endpoint_url("ftp://files.example.com")
    assert not valid
    assert "protocolo no permitido" in err.lower()

    # Valid public HTTPS S3 endpoint
    valid, err = validate_s3_endpoint_url("https://s3.us-west-2.amazonaws.com")
    assert valid
    assert err is None

def test_s3_connector_constructor_blocks_ssrf():
    with pytest.raises(SSRFProtectionError):
        S3CompatibleConnector(
            bucket_name="my-bucket",
            access_key_id="key123",
            secret_access_key="sec123",
            endpoint_url="http://169.254.169.254"
        )

@patch("boto3.client")
def test_s3_connector_test_connection_success(mock_boto):
    mock_s3 = MagicMock()
    mock_boto.return_value = mock_s3

    connector = S3CompatibleConnector(
        bucket_name="analytics-bucket",
        access_key_id="AKIA12345",
        secret_access_key="SECRET54321",
        region_name="eu-west-1"
    )

    res = connector.test_connection()
    assert res["success"] is True
    assert "analytics-bucket" in res["message"]
    mock_s3.head_bucket.assert_called_once_with(Bucket="analytics-bucket")

@patch("boto3.client")
def test_s3_connector_test_connection_bucket_not_found(mock_boto):
    mock_s3 = MagicMock()
    mock_s3.head_bucket.side_effect = ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket")
    mock_boto.return_value = mock_s3

    connector = S3CompatibleConnector(
        bucket_name="nonexistent-bucket",
        access_key_id="AKIA12345",
        secret_access_key="SECRET54321"
    )

    res = connector.test_connection()
    assert res["success"] is False
    assert "no existe" in res["message"]

@patch("boto3.client")
def test_s3_connector_test_connection_access_denied(mock_boto):
    mock_s3 = MagicMock()
    mock_s3.head_bucket.side_effect = ClientError({"Error": {"Code": "403", "Message": "Access Denied"}}, "HeadBucket")
    mock_boto.return_value = mock_s3

    connector = S3CompatibleConnector(
        bucket_name="protected-bucket",
        access_key_id="AKIA12345",
        secret_access_key="SECRET54321"
    )

    res = connector.test_connection()
    assert res["success"] is False
    assert "Acceso denegado" in res["message"]

@patch("boto3.client")
def test_s3_connector_list_and_metadata(mock_boto):
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "raw/erp_2026.csv", "Size": 1024, "ETag": '"abc123etag"'}
        ],
        "NextContinuationToken": "cursor-999",
        "IsTruncated": True
    }
    mock_s3.head_object.return_value = {
        "ContentLength": 1024,
        "ETag": '"abc123etag"',
        "ContentType": "text/csv"
    }
    mock_boto.return_value = mock_s3

    connector = S3CompatibleConnector(
        bucket_name="data-lake",
        access_key_id="KEY",
        secret_access_key="SECRET"
    )

    # 1. List objects
    list_res = connector.list_objects(prefix="raw/", max_keys=10)
    assert len(list_res.objects) == 1
    assert list_res.objects[0].key == "raw/erp_2026.csv"
    assert list_res.next_cursor == "cursor-999"
    assert list_res.is_truncated is True

    # 2. Get metadata
    meta = connector.get_object_metadata("raw/erp_2026.csv")
    assert meta.key == "raw/erp_2026.csv"
    assert meta.size_bytes == 1024
    assert meta.etag == "abc123etag"
    assert meta.content_type == "text/csv"

@patch("boto3.client")
def test_s3_connector_streaming_read_and_write(mock_boto):
    mock_s3 = MagicMock()
    mock_body = MagicMock()
    # Stream 2 chunks of 10 bytes then empty
    mock_body.read.side_effect = [b"1234567890", b"abcdefghij", b""]
    mock_s3.get_object.return_value = {"Body": mock_body}
    mock_s3.put_object.return_value = {"ETag": '"upload-etag-xyz"'}
    mock_boto.return_value = mock_s3

    connector = S3CompatibleConnector(
        bucket_name="pipeline-bucket",
        access_key_id="KEY",
        secret_access_key="SECRET"
    )

    # Stream read
    chunks = list(connector.read_stream("source.csv", chunk_size=10))
    assert len(chunks) == 2
    assert b"".join(chunks) == b"1234567890abcdefghij"

    # Stream write
    write_buf = io.BytesIO(b"normalized-content-csv")
    write_res = connector.write_stream("target/clean.csv", write_buf, content_type="text/csv")
    assert write_res["key"] == "target/clean.csv"
    assert write_res["etag"] == "upload-etag-xyz"
