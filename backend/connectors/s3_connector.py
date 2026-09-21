import io
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError
from typing import Optional, Generator, BinaryIO, Dict, Any

from connectors.base import ExternalStorageConnector, ObjectRef, ObjectMetadata, ObjectListResult
from ssrf_validator import validate_s3_endpoint_url, SSRFProtectionError

class S3CompatibleConnector(ExternalStorageConnector):
    """
    S3-Compatible Connector implementation for AWS S3, Wasabi, MinIO, Cloudflare R2, Backblaze B2, etc.
    Enforces SSRF prevention on custom endpoint URLs, streaming data transfer, and strict error handling.
    """

    def __init__(
        self,
        bucket_name: str,
        access_key_id: str,
        secret_access_key: str,
        region_name: str = "us-east-1",
        endpoint_url: Optional[str] = None
    ):
        self.bucket_name = bucket_name.strip()
        self.access_key_id = access_key_id.strip()
        self.secret_access_key = secret_access_key.strip()
        self.region_name = (region_name or "us-east-1").strip()
        self.endpoint_url = endpoint_url.strip() if endpoint_url and endpoint_url.strip() else None

        # Validate endpoint URL against SSRF
        is_valid_url, err_msg = validate_s3_endpoint_url(self.endpoint_url)
        if not is_valid_url:
            raise SSRFProtectionError(f"Endpoint S3 rechazado por seguridad: {err_msg}")

        # Boto3 client with bounded connect and read timeouts
        client_config = Config(
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 2}
        )

        self._s3_client = boto3.client(
            "s3",
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region_name,
            endpoint_url=self.endpoint_url,
            config=client_config
        )

    def test_connection(self) -> Dict[str, Any]:
        """
        Tests read and basic bucket accessibility with minimal permissions (head_bucket and list_objects).
        """
        try:
            self._s3_client.head_bucket(Bucket=self.bucket_name)
            # Try a lightweight list to verify listing permissions
            self._s3_client.list_objects_v2(Bucket=self.bucket_name, MaxKeys=1)
            return {
                "success": True,
                "message": f"Conexión exitosa con el bucket '{self.bucket_name}'.",
                "details": {
                    "bucket": self.bucket_name,
                    "region": self.region_name,
                    "endpoint": self.endpoint_url or "AWS Default"
                }
            }
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            msg = e.response.get("Error", {}).get("Message", str(e))
            if code == "404" or code == "NoSuchBucket":
                return {"success": False, "message": f"El bucket '{self.bucket_name}' no existe.", "code": code}
            if code == "403" or code == "AccessDenied":
                return {"success": False, "message": f"Acceso denegado al bucket '{self.bucket_name}'. Revisa las credenciales y permisos IAM.", "code": code}
            return {"success": False, "message": f"Error de autenticación/permisos S3 ({code}): {msg}", "code": code}
        except EndpointConnectionError:
            return {"success": False, "message": f"No se pudo establecer conexión con el endpoint '{self.endpoint_url}'.", "code": "EndpointConnectionError"}
        except Exception as e:
            return {"success": False, "message": f"Fallo al conectar con el almacenamiento S3: {str(e)}", "code": "UnknownError"}

    def list_objects(self, prefix: str = "", cursor: Optional[str] = None, max_keys: int = 100) -> ObjectListResult:
        params: Dict[str, Any] = {
            "Bucket": self.bucket_name,
            "MaxKeys": min(max(max_keys, 1), 1000)
        }
        if prefix:
            params["Prefix"] = prefix
        if cursor:
            params["ContinuationToken"] = cursor

        try:
            res = self._s3_client.list_objects_v2(**params)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            msg = e.response.get("Error", {}).get("Message", str(e))
            raise RuntimeError(f"Error listando objetos S3 ({code}): {msg}")

        objects = []
        for item in res.get("Contents", []):
            objects.append(ObjectRef(
                key=item["Key"],
                size_bytes=item["Size"],
                last_modified=item.get("LastModified"),
                etag=item.get("ETag", "").strip('"')
            ))

        return ObjectListResult(
            objects=objects,
            next_cursor=res.get("NextContinuationToken"),
            is_truncated=res.get("IsTruncated", False),
            prefix=prefix
        )

    def get_object_metadata(self, key: str) -> ObjectMetadata:
        try:
            res = self._s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return ObjectMetadata(
                key=key,
                size_bytes=res.get("ContentLength", 0),
                last_modified=res.get("LastModified"),
                etag=res.get("ETag", "").strip('"'),
                content_type=res.get("ContentType"),
                custom_metadata=res.get("Metadata", {})
            )
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            if code in ["404", "NoSuchKey"]:
                raise FileNotFoundError(f"Objeto '{key}' no encontrado en el bucket '{self.bucket_name}'.")
            raise RuntimeError(f"Error leyendo metadata de '{key}' ({code}): {str(e)}")

    def read_stream(self, key: str, chunk_size: int = 1024 * 1024) -> Generator[bytes, None, None]:
        try:
            res = self._s3_client.get_object(Bucket=self.bucket_name, Key=key)
            body = res["Body"]
            while True:
                chunk = body.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            if code in ["404", "NoSuchKey"]:
                raise FileNotFoundError(f"Objeto '{key}' no encontrado en el bucket '{self.bucket_name}'.")
            raise RuntimeError(f"Error en streaming de lectura S3 ({code}): {str(e)}")

    def write_stream(self, key: str, stream: BinaryIO, content_type: str = "application/octet-stream") -> Dict[str, Any]:
        try:
            res = self._s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=stream,
                ContentType=content_type
            )
            return {
                "key": key,
                "etag": res.get("ETag", "").strip('"'),
                "bucket": self.bucket_name
            }
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "Unknown")
            raise PermissionError(f"Error escribiendo objeto en S3 ({code}): {str(e)}")
