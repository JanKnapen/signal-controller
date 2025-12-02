"""
SignalController - Main FastAPI Application
This service provides two interfaces:
1. Public interface (port 8443) - Receives incoming Signal messages
2. Private interface (port 9000) - Sends Signal messages (internal only)
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException, Request, Depends, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
import uvicorn
from datetime import datetime
import logging
import asyncio
import httpx
import json
import hmac
import hashlib
import secrets
from urllib.parse import urlparse
import ipaddress

from database.db import Database
from backend.signal_client import SignalClient
from backend.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/signal-controller/app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Initialize
config = Config()
db = Database(config.DATABASE_PATH)
signal_client = SignalClient(config.SIGNAL_CLI_URL)

# API Key security for private interface
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify API key for private interface"""
    if api_key != config.API_KEY:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

def verify_ip_whitelist(request: Request):
    """Verify client IP is in whitelist for private interface"""
    client_ip = request.client.host
    
    if client_ip not in config.PRIVATE_API_WHITELIST:
        logger.warning(f"Unauthorized IP access attempt from {client_ip}")
        raise HTTPException(
            status_code=403, 
            detail=f"Access denied: IP {client_ip} not in whitelist"
        )
    
    return client_ip


def is_private_network_url(url: str) -> bool:
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


async def send_webhook_challenge(callback_url: str) -> Optional[str]:
    """
    Send a challenge to verify webhook endpoint
    
    Returns:
        Challenge token if successful, None if failed
    """
    challenge = secrets.token_urlsafe(32)
    
    try:
        payload = {
            "event": "challenge",
            "challenge": challenge
        }
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                callback_url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('challenge') == challenge:
                    return challenge
                    
    except Exception as e:
        logger.error(f"Challenge failed for {callback_url}: {e}")
    
    return None


            detail=f"Access denied: IP {client_ip} not in whitelist"
        )
    
    return client_ip


async def listen_to_signal_events():
    """
    Background task to listen to signal-cli SSE stream for incoming messages
    """
    logger.info("Starting SSE listener for signal-cli events")
    
    while True:
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream('GET', f'{config.SIGNAL_CLI_URL}/api/v1/events') as response:
                    logger.info("Connected to signal-cli events stream")
                    
                    async for line in response.aiter_lines():
                        if line.startswith('data:'):
                            # Extract JSON data from SSE format
                            json_data = line[5:].strip()  # Remove 'data:' prefix
                            
                            try:
                                data = json.loads(json_data)
                                await process_incoming_message(data)
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse SSE data: {e}")
                                
        except Exception as e:
            logger.error(f"SSE connection error: {e}")
            logger.info("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)


def compute_hmac(payload: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload"""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


async def notify_webhook_subscriber(callback_url: str, secret: str, message_data: dict, retry_count: int = 0):
    """
    Send webhook notification to a single subscriber with HMAC signing
    
    Args:
        callback_url: URL to send the webhook to
        secret: Secret for HMAC signing
        message_data: Message payload
        retry_count: Current retry attempt (for exponential backoff)
    """
    try:
        # Serialize payload
        payload = json.dumps(message_data, separators=(',', ':'))
        
        # Compute HMAC signature
        signature = compute_hmac(payload, secret)
        
        headers = {
            "Content-Type": "application/json",
            "X-Signal-HMAC": signature
        }
        
        timeout = httpx.Timeout(5.0, connect=2.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                callback_url,
                content=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                logger.info(f"Webhook delivered to {callback_url}")
                db.update_webhook_success(callback_url)
            else:
                logger.warning(f"Webhook {callback_url} returned status {response.status_code}")
                db.update_webhook_failure(callback_url)
                
    except Exception as e:
        logger.error(f"Failed to deliver webhook to {callback_url}: {e}")
        db.update_webhook_failure(callback_url)
        
        # Exponential backoff retry (max 3 attempts)
        if retry_count < 3:
            await asyncio.sleep(2 ** retry_count)
            await notify_webhook_subscriber(callback_url, secret, message_data, retry_count + 1)


async def notify_all_webhooks(message_data: dict):
    """Send webhook notifications to all active subscribers"""
    subscriptions = db.get_webhook_subscriptions(enabled_only=True)
    
    if not subscriptions:
        logger.debug("No active webhook subscriptions")
        return
    
    logger.info(f"Notifying {len(subscriptions)} webhook subscribers")
    
    # Send to all subscribers concurrently
    tasks = [
        notify_webhook_subscriber(sub['callback_url'], sub['secret'], message_data)
        for sub in subscriptions
    ]
    
    await asyncio.gather(*tasks, return_exceptions=True)


async def process_incoming_message(data: dict):
    """Process an incoming message from signal-cli"""
    try:
        envelope = data.get('envelope', {})
        
        # Skip non-message events (typing indicators, receipts, etc.)
        if 'dataMessage' not in envelope:
            return
        
        # Extract message data
        source_number = envelope.get('sourceNumber', envelope.get('source', 'unknown'))
        source_name = envelope.get('sourceName', '')
        timestamp = envelope.get('timestamp', int(datetime.now().timestamp() * 1000))
        
        # Get message content
        data_message = envelope.get('dataMessage', {})
        message_body = data_message.get('message', '')
        
        # Get group info if this is a group message
        group_info = data_message.get('groupInfo', {})
        group_id = group_info.get('groupId') if group_info else None
        group_name = group_info.get('groupName') if group_info else None
        
        # Get attachments if any
        attachments = data_message.get('attachments', [])
        attachment_info = []
        for att in attachments:
            attachment_info.append({
                'content_type': att.get('contentType', ''),
                'filename': att.get('filename', ''),
                'id': att.get('id', ''),
                'size': att.get('size', 0)
            })
        
        # Store message in database
        message_id = db.store_message(
            sender_number=source_number,
            sender_name=source_name,
            timestamp=timestamp,
            message_body=message_body,
            attachments=json.dumps(attachment_info) if attachment_info else None,
            raw_data=json.dumps(data),
            group_id=group_id,
            group_name=group_name
        )
        
        if group_id:
            logger.info(f"Stored group message {message_id} from {source_number} in group '{group_name}': {message_body[:50]}")
        else:
            # Update individual conversation
            db.update_conversation(
                contact_number=source_number,
                contact_name=source_name,
                last_message_at=datetime.fromtimestamp(timestamp / 1000)
            )
            logger.info(f"Stored message {message_id} from {source_number}: {message_body[:50]}")
        
        # Send webhook notification to all subscribers
        webhook_data = {
            "event": "new_message",
            "message_id": message_id,
            "sender_number": source_number,
            "sender_name": source_name,
            "message_body": message_body,
            "timestamp": timestamp,
            "group_id": group_id,
            "group_name": group_name,
            "attachments": attachment_info
        }
        asyncio.create_task(notify_all_webhooks(webhook_data))
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)


# ============================================================================
# PUBLIC INTERFACE - Port 8888 (Exposed to Internet)
# ============================================================================

public_app = FastAPI(
    title="SignalController - Public Interface",
    description="Receives incoming Signal messages via SSE from signal-cli",
    version="1.0.0"
)


@public_app.on_event("startup")
async def startup_event():
    """Start background tasks on application startup"""
    logger.info("Starting background SSE listener")
    asyncio.create_task(listen_to_signal_events())


class IncomingMessage(BaseModel):
    """Model for incoming Signal messages from signal-cli webhook"""
    envelope: dict
    account: str


@public_app.post("/webhook/signal")
async def receive_signal_message(request: Request):
    """
    Webhook endpoint for signal-cli to send incoming messages
    This endpoint is exposed to the internet via reverse proxy
    """
    try:
        data = await request.json()
        logger.info(f"Received webhook data: {data}")
        
        # Parse the signal-cli webhook format
        envelope = data.get('envelope', {})
        
        # Extract message data
        source_number = envelope.get('sourceNumber', envelope.get('source', 'unknown'))
        source_name = envelope.get('sourceName', envelope.get('sourceUuid', ''))
        timestamp = envelope.get('timestamp', int(datetime.now().timestamp() * 1000))
        
        # Get message content
        data_message = envelope.get('dataMessage', {})
        message_body = data_message.get('message', '')
        
        # Get attachments if any
        attachments = data_message.get('attachments', [])
        attachment_info = []
        for att in attachments:
            attachment_info.append({
                'content_type': att.get('contentType', ''),
                'filename': att.get('filename', ''),
                'id': att.get('id', ''),
                'size': att.get('size', 0)
            })
        
        # Store message in database
        message_id = db.store_message(
            sender_number=source_number,
            sender_name=source_name,
            timestamp=timestamp,
            message_body=message_body,
            attachments=attachment_info
        )
        
        logger.info(f"Stored message {message_id} from {source_number}")
        
        return {
            "status": "success",
            "message_id": message_id,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


@public_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "SignalController-Public",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# PRIVATE INTERFACE - Port 9000 (Internal Only)
# ============================================================================

private_app = FastAPI(
    title="SignalController - Private Interface",
    description="Internal API for sending Signal messages and querying stored messages",
    version="1.0.0"
)


@private_app.middleware("http")
async def security_middleware(request: Request, call_next):
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


class SendMessageRequest(BaseModel):
    """Request model for sending messages"""
    to: str = Field(..., description="Phone number or username to send to")
    message: str = Field(..., description="Message text to send")
    attachment: Optional[str] = Field(None, description="Path to attachment file (optional)")


class SendMessageResponse(BaseModel):
    """Response model for send message"""
    status: str
    timestamp: str
    recipient: str
    message_preview: str


@private_app.post("/send", response_model=SendMessageResponse)
async def send_message(request_data: SendMessageRequest):
    """
    Send a Signal message via signal-cli
    Requires valid API key in X-API-Key header and whitelisted IP
    """
    try:
        logger.info(f"Sending message to {request_data.to}")
        
        # Send via signal-cli
        result = await signal_client.send_message(
            recipient=request_data.to,
            message=request_data.message,
            attachment=request_data.attachment
        )
        
        logger.info(f"Message sent successfully to {request_data.to}")
        
        # Store sent message in database
        try:
            timestamp = int(datetime.now().timestamp() * 1000)
            
            # Determine if this is a group message (group IDs are base64 strings with = padding)
            is_group = '=' in request_data.to or len(request_data.to) > 20
            group_id = request_data.to if is_group else None
            
            # Get group name from conversations if it exists
            group_name = None
            if is_group:
                conversations = db.get_conversations()
                for conv in conversations:
                    if conv.get('group_id') == group_id:
                        group_name = conv.get('contact_name')
                        break
            
            # Store the sent message
            message_id = db.store_message(
                sender_number=config.SIGNAL_PHONE_NUMBER,
                sender_name="Me",
                timestamp=timestamp,
                message_body=request_data.message,
                attachments=None,
                raw_data=None,
                group_id=group_id,
                group_name=group_name,
                recipient_number=request_data.to if not is_group else None
            )
            
            logger.info(f"Stored sent message {message_id} to {request_data.to}")
        except Exception as db_error:
            logger.error(f"Failed to store sent message: {db_error}", exc_info=True)
            # Don't fail the request if database storage fails
        
        return SendMessageResponse(
            status="sent",
            timestamp=datetime.now().isoformat(),
            recipient=request_data.to,
            message_preview=request_data.message[:50] + "..." if len(request_data.message) > 50 else request_data.message
        )
        
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@private_app.get("/messages")
async def get_messages(
    limit: int = 100,
    offset: int = 0,
    sender: Optional[str] = None,
    recipient: Optional[str] = None,
    group_id: Optional[str] = None
):
    """
    Retrieve stored messages from database
    Supports filtering by sender, recipient, or group_id
    Requires valid API key in X-API-Key header and whitelisted IP
    Examples:
      /messages - Get all messages
      /messages?sender=+1234567890 - Get messages from specific sender
      /messages?recipient=+1234567890 - Get messages to specific recipient
      /messages?sender=+1234567890&recipient=+0987654321 - Get conversation between two numbers
      /messages?group_id=J60Zsn1Msd9SWoeMHvhbNroMRUV32H7BY5n/oOqNlUc= - Get group messages
    """
    try:
        if group_id:
            messages = db.get_group_messages(group_id, limit, offset)
        else:
            messages = db.get_messages(limit=limit, offset=offset, sender=sender, recipient=recipient)
        return {
            "count": len(messages),
            "limit": limit,
            "offset": offset,
            "messages": messages
        }
    except Exception as e:
        logger.error(f"Error retrieving messages: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve messages: {str(e)}")


@private_app.get("/messages/{message_id}")
async def get_message(message_id: int):
    """
    Retrieve a specific message by ID
    Requires valid API key in X-API-Key header and whitelisted IP
    """
    try:
        message = db.get_message_by_id(message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        return message
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving message: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve message: {str(e)}")


@private_app.get("/conversations")
async def get_conversations():
    """
    Get all conversations with message counts
    Requires valid API key in X-API-Key header and whitelisted IP
    """
    try:
        conversations = db.get_conversations()
        return {
            "conversations": conversations,
            "count": len(conversations)
        }
    except Exception as e:
        logger.error(f"Error retrieving conversations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve conversations: {str(e)}")


@private_app.get("/groups")
async def get_groups():
    """
    Get all group conversations
    Requires valid API key in X-API-Key header and whitelisted IP
    """
    try:
        groups = db.get_group_conversations()
        return {
            "groups": groups,
            "count": len(groups)
        }
    except Exception as e:
        logger.error(f"Error retrieving groups: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve groups: {str(e)}")


@private_app.get("/groups/{group_id}/messages")
async def get_group_messages(
    group_id: str,
    limit: int = 100,
    offset: int = 0
):
    """
    Get messages from a specific group
    Requires valid API key in X-API-Key header and whitelisted IP
    Note: group_id must be URL-encoded
    """
    try:
        messages = db.get_group_messages(group_id, limit, offset)
        return {
            "group_id": group_id,
            "count": len(messages),
            "limit": limit,
            "offset": offset,
            "messages": messages
        }
    except Exception as e:
        logger.error(f"Error retrieving group messages: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve group messages: {str(e)}")


@private_app.get("/stats")
async def get_stats():
    """
    Get message statistics
    Requires valid API key in X-API-Key header and whitelisted IP
    """
    try:
        stats = db.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error retrieving stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics: {str(e)}")


# ============================================================================
# Webhook Subscription Endpoints
# ============================================================================

class WebhookSubscribeRequest(BaseModel):
    """Request model for webhook subscription"""
    callback_url: HttpUrl
    secret: Optional[str] = None


class WebhookUnsubscribeRequest(BaseModel):
    """Request model for webhook unsubscription"""
    callback_url: HttpUrl


@private_app.post("/api/webhooks/subscribe")
async def subscribe_webhook(request: WebhookSubscribeRequest):
    """
    Subscribe to webhook notifications
    
    Request body:
        callback_url: Your webhook endpoint URL
        secret: Optional secret for HMAC signing (will be generated if not provided)
    
    Returns:
        Subscription details including the secret for HMAC verification
    """
    try:
        callback_url = str(request.callback_url)
        
        # Validate URL is in private network
        if not is_private_network_url(callback_url):
            raise HTTPException(
                status_code=403,
                detail="Webhook URL must be within a private network (192.168.x.x, 10.x.x.x, 172.16-31.x.x, or localhost)"
            )
        
        # Generate secret if not provided
        secret = request.secret or secrets.token_urlsafe(32)
        
        # Send challenge to verify endpoint
        logger.info(f"Sending challenge to {callback_url}")
        challenge_result = await send_webhook_challenge(callback_url)
        
        if not challenge_result:
            raise HTTPException(
                status_code=400,
                detail="Webhook challenge failed. Endpoint must respond to challenge requests"
            )
        
        # Add subscription to database
        sub_id = db.add_webhook_subscription(callback_url, secret)
        
        logger.info(f"Webhook subscription created: {callback_url}")
        
        return {
            "status": "subscribed",
            "subscription_id": sub_id,
            "callback_url": callback_url,
            "secret": secret,
            "message": "Webhook subscription created successfully. Use the secret to verify HMAC signatures."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error subscribing webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to subscribe webhook: {str(e)}")


@private_app.post("/api/webhooks/unsubscribe")
async def unsubscribe_webhook(request: WebhookUnsubscribeRequest):
    """
    Unsubscribe from webhook notifications
    
    Request body:
        callback_url: Your webhook endpoint URL
    
    Returns:
        Confirmation of unsubscription
    """
    try:
        callback_url = str(request.callback_url)
        
        success = db.remove_webhook_subscription(callback_url)
        
        if not success:
            raise HTTPException(status_code=404, detail="Webhook subscription not found")
        
        logger.info(f"Webhook unsubscribed: {callback_url}")
        
        return {
            "status": "unsubscribed",
            "callback_url": callback_url,
            "message": "Webhook subscription removed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unsubscribing webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to unsubscribe webhook: {str(e)}")


@private_app.get("/api/webhooks/subscribers")
async def list_webhook_subscribers(include_disabled: bool = False):
    """
    List all webhook subscribers
    
    Query params:
        include_disabled: Include disabled subscriptions (default: false)
    
    Returns:
        List of webhook subscriptions (secrets are hidden)
    """
    try:
        subscriptions = db.get_webhook_subscriptions(enabled_only=not include_disabled)
        
        # Hide secrets in response
        for sub in subscriptions:
            sub['secret'] = '***hidden***'
        
        return {
            "subscribers": subscriptions,
            "count": len(subscriptions)
        }
        
    except Exception as e:
        logger.error(f"Error listing webhooks: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list webhooks: {str(e)}")


@private_app.post("/api/webhooks/test")
async def test_webhook(request: WebhookSubscribeRequest):
    """
    Test webhook connectivity without subscribing
    
    Request body:
        callback_url: Webhook URL to test
        secret: Secret for HMAC signing (optional)
    
    Returns:
        Test result
    """
    try:
        callback_url = str(request.callback_url)
        secret = request.secret or "test_secret"
        
        # Send test message
        test_payload = {
            "event": "test",
            "message": "This is a test webhook from SignalController",
            "timestamp": int(datetime.now().timestamp() * 1000)
        }
        
        await notify_webhook_subscriber(callback_url, secret, test_payload)
        
        return {
            "status": "success",
            "message": "Test webhook sent successfully",
            "callback_url": callback_url
        }
        
    except Exception as e:
        logger.error(f"Error testing webhook: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Webhook test failed: {str(e)}")


@private_app.get("/health")
async def health_check():
    """Health check endpoint (no auth required)"""
    return {
        "status": "healthy",
        "service": "SignalController-Private",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import sys
    import os
    
    if len(sys.argv) < 2:
        print("Usage: python main.py [public|private]")
        sys.exit(1)
    
    interface = sys.argv[1]
    
    if interface == "public":
        # Public interface - SSL handled by Cloudflare Tunnel
        logger.info("Starting public interface on port 8888 (HTTP - SSL handled by Cloudflare)")
        uvicorn.run(
            public_app,
            host="0.0.0.0",
            port=8888,
            log_level="info"
        )
    elif interface == "private":
        logger.info(f"Starting private interface on port 9000 (IP whitelist: {config.PRIVATE_API_WHITELIST})")
        uvicorn.run(
            private_app,
            host="0.0.0.0",  # Bind to all interfaces, IP whitelist in middleware
            port=9000,
            log_level="info"
        )
    else:
        print(f"Unknown interface: {interface}")
        print("Usage: python main.py [public|private]")
        sys.exit(1)
