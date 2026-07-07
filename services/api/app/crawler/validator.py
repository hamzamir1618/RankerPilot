import asyncio
import socket
import urllib.parse
import ipaddress
from typing import Tuple

class SSRFViolation(Exception):
    """Raised when a URL resolves to a forbidden or private IP address."""
    pass

async def resolve_hostname(hostname: str) -> str:
    """Resolve a hostname to an IP address asynchronously."""
    loop = asyncio.get_event_loop()
    try:
        # Resolve to any IP (IPv4 or IPv6)
        info = await loop.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        if not info:
            raise SSRFViolation(f"Could not resolve hostname: {hostname}")
        # Return the first resolved IP
        return info[0][4][0]
    except socket.gaierror as e:
        raise SSRFViolation(f"DNS resolution failed for {hostname}: {e}")

async def validate_target_url(url: str) -> str:
    """
    Validates a URL against SSRF attacks.
    - Rejects non-http(s) schemes.
    - Resolves DNS and rejects private/reserved IP ranges.
    - Returns the validated IP address for pinning.
    """
    parsed = urllib.parse.urlparse(url)
    
    if parsed.scheme not in ('http', 'https'):
        raise SSRFViolation(f"Invalid scheme: {parsed.scheme}. Only http and https are allowed.")
        
    hostname = parsed.hostname
    if not hostname:
        raise SSRFViolation("No hostname found in URL.")
        
    ip_str = await resolve_hostname(hostname)
    
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        raise SSRFViolation(f"Invalid IP address format resolved: {ip_str}")
        
    # Check explicitly forbidden ranges
    if ip.is_private or ip.is_loopback or ip.is_link_local:
        raise SSRFViolation(f"Forbidden IP range: {ip_str} is private, loopback, or link-local.")
        
    # Explicitly block AWS metadata IP (which might be covered by link-local, but explicit is better)
    if str(ip) == "169.254.169.254":
        raise SSRFViolation("Forbidden IP: AWS Metadata endpoint is blocked.")
        
    return ip_str
