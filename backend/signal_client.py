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
        Send a message via signal-cli REST API
        
        Args:
            recipient: Phone number or group ID
            message: Message text
            attachment: Path to attachment file (optional)
            
        Returns:
            Response from signal-cli
        """
        endpoint = f"{self.base_url}/v2/send"
        
        payload = {
            "message": message,
            "number": recipient,
            "recipients": [recipient]
        }
        
        # Handle attachments if provided
        if attachment:
            # For attachments, we need to use multipart form data
            files = {'attachment': open(attachment, 'rb')}
            response = await self.client.post(
                endpoint,
                data=payload,
                files=files
            )
        else:
            response = await self.client.post(
                endpoint,
                json=payload
            )
        
        response.raise_for_status()
        logger.info(f"Message sent to {recipient}: {response.status_code}")
        
        return response.json()
    
    async def send_group_message(
        self,
        group_id: str,
        message: str,
        attachment: Optional[str] = None
    ) -> dict:
        """
        Send a message to a Signal group
        
        Args:
            group_id: Internal group ID
            message: Message text
            attachment: Path to attachment file (optional)
            
        Returns:
            Response from signal-cli
        """
        endpoint = f"{self.base_url}/v2/send"
        
        payload = {
            "message": message,
            "group_id": group_id
        }
        
        if attachment:
            files = {'attachment': open(attachment, 'rb')}
            response = await self.client.post(
                endpoint,
                data=payload,
                files=files
            )
        else:
            response = await self.client.post(
                endpoint,
                json=payload
            )
        
        response.raise_for_status()
        return response.json()
    
    async def get_registered_numbers(self) -> List[str]:
        """Get list of registered phone numbers in signal-cli"""
        endpoint = f"{self.base_url}/v1/accounts"
        
        response = await self.client.get(endpoint)
        response.raise_for_status()
        
        return response.json()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
