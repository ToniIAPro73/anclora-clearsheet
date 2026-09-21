import os
import base64
import json
import logging
from typing import Dict, Any, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("cleansheet.crypto")

# Master secret from environment
MASTER_SECRET = os.environ.get("CLEANSHEET_MASTER_KEY", "cleansheet-enterprise-secure-master-key-2026")

def _derive_key_v1() -> bytes:
    """Derives a fixed 256-bit (32 bytes) key using SHA-256 for AES-256-GCM."""
    import hashlib
    return hashlib.sha256(MASTER_SECRET.encode("utf-8")).digest()

def encrypt_secret(plain_secret: str) -> str:
    """
    Encrypts sensitive text using authenticated AES-256-GCM.
    Format: enc_gcm_v1.<nonce_b64>.<ciphertext_and_tag_b64>
    Preserves backwards compatibility with legacy enc_ format.
    """
    if not plain_secret:
        return ""
    key = _derive_key_v1()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12) # 96-bit nonce recommended for AES-GCM
    data = plain_secret.encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, data, None)
    
    nonce_b64 = base64.urlsafe_b64encode(nonce).decode("utf-8")
    ct_b64 = base64.urlsafe_b64encode(ciphertext).decode("utf-8")
    return f"enc_gcm_v1.{nonce_b64}.{ct_b64}"

def decrypt_secret(stored_secret: str) -> str:
    """
    Decrypts authenticated ciphertext.
    Supports both enc_gcm_v1 (AES-256-GCM) and legacy enc_ (keystream XOR).
    """
    if not stored_secret:
        return ""
    
    # AES-256-GCM version 1
    if stored_secret.startswith("enc_gcm_v1."):
        parts = stored_secret.split(".")
        if len(parts) == 3:
            _, nonce_b64, ct_b64 = parts
            nonce = base64.urlsafe_b64decode(nonce_b64.encode("utf-8"))
            ciphertext = base64.urlsafe_b64decode(ct_b64.encode("utf-8"))
            key = _derive_key_v1()
            aesgcm = AESGCM(key)
            decrypted = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted.decode("utf-8")

    # Legacy enc_ XOR keystream
    if stored_secret.startswith("enc_"):
        enc_data = stored_secret[4:]
        raw_bytes = base64.urlsafe_b64decode(enc_data.encode("utf-8"))
        import hashlib
        key = hashlib.sha256(MASTER_SECRET.encode("utf-8")).digest()
        decrypted = bytearray()
        for i, b in enumerate(raw_bytes):
            decrypted.append(b ^ key[i % len(key)])
        return bytes(decrypted).decode("utf-8")

    # Plain text fallback
    return stored_secret

def encrypt_dict(data: Dict[str, Any]) -> str:
    """Serializes a dictionary to JSON and encrypts it with AES-256-GCM."""
    payload = json.dumps(data)
    return encrypt_secret(payload)

def decrypt_dict(encrypted_str: str) -> Dict[str, Any]:
    """Decrypts AES-256-GCM string and parses JSON dictionary."""
    if not encrypted_str:
        return {}
    decrypted = decrypt_secret(encrypted_str)
    try:
        return json.loads(decrypted)
    except Exception:
        return {}
