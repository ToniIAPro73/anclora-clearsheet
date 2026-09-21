import ipaddress
import socket
from urllib.parse import urlparse
from typing import Optional, Tuple

class SSRFProtectionError(ValueError):
    pass

def validate_s3_endpoint_url(endpoint_url: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Validates that a custom S3 endpoint URL does not target loopback, private networks,
    link-local addresses (e.g. 169.254.169.254 AWS metadata), or non-http/https protocols.
    Returns (is_valid, error_message).
    """
    if not endpoint_url or not endpoint_url.strip():
        # Standard AWS default endpoint
        return True, None

    url = endpoint_url.strip()
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"URL de endpoint mal formada: {str(e)}"

    if parsed.scheme.lower() not in ["https", "http"]:
        return False, f"Protocolo no permitido ({parsed.scheme}). Debe ser HTTPS (o HTTP en pruebas explícitas)."

    hostname = parsed.hostname
    if not hostname:
        return False, "El endpoint no contiene un nombre de host válido."

    # Block well-known loopbacks by name
    lower_host = hostname.lower()
    if lower_host in ["localhost", "127.0.0.1", "::1", "metadata.google.internal"]:
        return False, f"Acceso restringido: no se permite conectar a hosts locales o de metadata ({hostname})."

    # Resolve IP address to test for private/link-local ranges
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
        ips = {info[4][0] for info in addr_infos}
    except Exception:
        # If DNS resolution fails here in test environments, check direct IP parsing
        ips = {hostname}

    for ip_str in ips:
        try:
            ip = ipaddress.ip_address(ip_str)
            if ip.is_loopback:
                return False, f"Bloqueo SSRF: La dirección IP {ip_str} es loopback."
            if ip.is_link_local:
                return False, f"Bloqueo SSRF: La dirección IP {ip_str} es link-local / endpoint de metadata."
            if ip.is_private:
                return False, f"Bloqueo SSRF: La dirección IP {ip_str} pertenece a una red privada no autorizada."
            if ip.is_reserved or ip.is_multicast:
                return False, f"Bloqueo SSRF: La dirección IP {ip_str} está reservada."
        except ValueError:
            # Not a raw IP literal, passed through
            pass

    return True, None
