import fnmatch
from typing import Optional, List
from connectors.base import ExternalStorageConnector, ObjectRef

def select_target_object(
    connector: ExternalStorageConnector,
    selector_type: str,
    pattern: str
) -> Optional[ObjectRef]:
    """
    Selects the target remote object based on selector strategy:
    - exact: checks if the exact key exists.
    - prefix: lists objects under prefix and takes first matching supported file.
    - latest_matching: lists objects under pattern/prefix and selects the one with the latest last_modified.
    """
    clean_pattern = pattern.strip()

    if selector_type == "exact":
        try:
            meta = connector.get_object_metadata(clean_pattern)
            return ObjectRef(
                key=meta.key,
                size_bytes=meta.size_bytes,
                last_modified=meta.last_modified,
                etag=meta.etag,
                content_type=meta.content_type
            )
        except Exception:
            return None

    # For prefix or latest_matching, list objects
    prefix = clean_pattern.split("*")[0] if "*" in clean_pattern else clean_pattern
    list_result = connector.list_objects(prefix=prefix, max_keys=200)
    candidates = list_result.objects

    # Filter by pattern if wildcards exist
    if "*" in clean_pattern:
        candidates = [obj for obj in candidates if fnmatch.fnmatch(obj.key, clean_pattern)]

    # Filter to supported formats (.csv, .xlsx, .xls)
    candidates = [
        obj for obj in candidates
        if obj.key.lower().endswith((".csv", ".xlsx", ".xls"))
    ]

    if not candidates:
        return None

    if selector_type == "latest_matching":
        # Sort by last_modified descending (fallback to key name)
        candidates.sort(
            key=lambda o: (o.last_modified or 0, o.key),
            reverse=True
        )
        return candidates[0]

    # For prefix, return the first one alphabetically
    candidates.sort(key=lambda o: o.key)
    return candidates[0]
