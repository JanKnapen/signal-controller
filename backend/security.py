"""
Security utilities for authentication and authorization
"""

import logging
from urllib.parse import urlparse
import ipaddress
from fastapi import HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# API Key security for private interface
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


def verify_api_key(config, api_key: str = Security(api_key_header)):
    """Verify API key for private interface"""
    if api_key != config.API_KEY:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


def verify_ip_whitelist(config, request: Request):
    """Verify client IP is in whitelist for private interface"""
    client_ip = request.client.host
    
    if client_ip not in config.PRIVATE_API_WHITELIST:
        logger.warning(f"Unauthorized IP access attempt from {client_ip}")
        raise HTTPException(
            status_code=403, 
            detail=f"Access denied: IP {client_ip} not in whitelist"
        )
    
    return client_ip


def is_private_network_url(config, url: str) -> bool:
    """
    Check if webhook URL hostname/IP is in the private API whitelist.
    Uses the same whitelist as the private interface security.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        
        if not hostname:
            return False
        
        # Check if hostname is directly in whitelist
        if hostname in config.PRIVATE_API_WHITELIST:
            return True
        
        # Try to parse as IP address and check against whitelist
        try:
            ip_addr = ipaddress.ip_address(hostname)
            # Check if this IP is in the whitelist
            for whitelisted in config.PRIVATE_API_WHITELIST:
                try:
                    whitelisted_ip = ipaddress.ip_address(whitelisted)
                    if ip_addr == whitelisted_ip:
                        return True
                except ValueError:
                    # Whitelisted entry is not an IP (might be hostname)
                    continue
        except ValueError:
            # hostname is not an IP address, it's a domain name
            # Domain names are allowed if they're in the whitelist
            pass
            
        return False
            
    except Exception as e:
        logger.error(f"Error validating webhook URL: {e}")
        return False


async def security_middleware(config, request: Request, call_next):
    """Middleware to check IP whitelist and API key for all private interface requests"""
    client_ip = request.client.host
    
    # Skip checks for health endpoint
    if request.url.path == "/health":
        return await call_next(request)
    
    # Check IP whitelist
    if client_ip not in config.PRIVATE_API_WHITELIST:
        logger.warning(f"Unauthorized IP access attempt from {client_ip} to {request.url.path}")
        return JSONResponse(
            status_code=403,
            content={"detail": f"Access denied: IP {client_ip} not in whitelist"}
        )
    
    # Check API key
    api_key = request.headers.get("X-API-Key")
    if api_key != config.API_KEY:
        logger.warning(f"Invalid API key attempt from {client_ip}")
        return JSONResponse(
            status_code=403,
            content={"detail": "Invalid API key"}
        )
    
    return await call_next(request)
