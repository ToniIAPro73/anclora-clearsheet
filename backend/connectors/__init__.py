from typing import Dict, Any
from connectors.base import ExternalStorageConnector
from connectors.s3_connector import S3CompatibleConnector

def get_connector(provider_type: str, config: Dict[str, Any]) -> ExternalStorageConnector:
    """
    Factory that instantiates provider-neutral ExternalStorageConnector.
    Allows seamlessly adding Google Drive, OneDrive, etc. without modifying caller code.
    """
    if provider_type in ["s3_compatible", "s3"]:
        return S3CompatibleConnector(
            bucket_name=config.get("bucket_name", ""),
            access_key_id=config.get("access_key_id", ""),
            secret_access_key=config.get("secret_access_key", ""),
            region_name=config.get("region_name", "us-east-1"),
            endpoint_url=config.get("endpoint_url")
        )
    raise ValueError(f"Proveedor de almacenamiento externo no soportado: '{provider_type}'")
