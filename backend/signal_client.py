"""
Signal CLI client wrapper
Handles communication with signal-cli REST API
"""

import httpx
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class SignalClient:
    """Client for interacting with signal-cli REST API"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def send_message(
        self,
        recipient: str,
        message: str,
        attachment: Optional[str] = None
    ) -> dict:
        """
        Send a message via signal-cli JSON-RPC API
        
        Args:
            recipient: Phone number or group ID
            message: Message text
            attachment: Path to attachment file (optional)
            
        Returns:
            Response from signal-cli
        """
        endpoint = f"{self.base_url}/api/v1/rpc"
        
        # Build JSON-RPC request
        payload = {
            "jsonrpc": "2.0",
            "method": "send",
            "params": {
                "recipient": [recipient],
                "message": message
            },
            "id": 1
        }
        
        # Add attachment if provided
        if attachment:
            payload["params"]["attachments"] = [attachment]
        
        response = await self.client.post(
            endpoint,
            json=payload
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Check for JSON-RPC error
        if "error" in result:
            error_msg = result["error"].get("message", "Unknown error")
            logger.error(f"JSON-RPC error: {error_msg}")
            raise Exception(f"Signal API error: {error_msg}")
        
        logger.info(f"Message sent to {recipient}: {result.get('result', {})}")
        
        return result.get("result", {})
    
    async def send_group_message(
        self,
        group_id: str,
        message: str,
        attachment: Optional[str] = None
    ) -> dict:
        """
        Send a message to a Signal group via JSON-RPC API
        
        Args:
            group_id: Internal group ID (base64 encoded)
            message: Message text
            attachment: Path to attachment file (optional)
            
        Returns:
            Response from signal-cli
        """
        endpoint = f"{self.base_url}/api/v1/rpc"
        
        # Build JSON-RPC request
        payload = {
            "jsonrpc": "2.0",
            "method": "send",
            "params": {
                "groupId": group_id,
                "message": message
            },
            "id": 2
        }
        
        # Add attachment if provided
        if attachment:
            payload["params"]["attachments"] = [attachment]
        
        response = await self.client.post(
            endpoint,
            json=payload
        )
        
        response.raise_for_status()
        result = response.json()
        
        # Check for JSON-RPC error
        if "error" in result:
            error_msg = result["error"].get("message", "Unknown error")
            logger.error(f"JSON-RPC error: {error_msg}")
            raise Exception(f"Signal API error: {error_msg}")
        
        return result.get("result", {})
    
    async def get_registered_numbers(self) -> List[str]:
        """Get list of registered phone numbers in signal-cli via JSON-RPC"""
        endpoint = f"{self.base_url}/api/v1/rpc"
        
        payload = {
            "jsonrpc": "2.0",
            "method": "listAccounts",
            "params": {},
            "id": 3
        }
        
        response = await self.client.post(endpoint, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        # Check for JSON-RPC error
        if "error" in result:
            error_msg = result["error"].get("message", "Unknown error")
            logger.error(f"JSON-RPC error: {error_msg}")
            raise Exception(f"Signal API error: {error_msg}")
        
        return result.get("result", [])
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
