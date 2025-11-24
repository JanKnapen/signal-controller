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
from pydantic import BaseModel, Field
from typing import Optional, List
import uvicorn
from datetime import datetime
import logging
import asyncio
import httpx
import json

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
            raw_data=json.dumps(data)
        )
        
        # Update conversation
        db.update_conversation(
            contact_number=source_number,
            contact_name=source_name,
            last_message_at=datetime.fromtimestamp(timestamp / 1000)
        )
        
        logger.info(f"Stored message {message_id} from {source_number}: {message_body[:50]}")
        
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
async def send_message(
    request: SendMessageRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Send a Signal message via signal-cli
    Requires valid API key in X-API-Key header
    """
    try:
        logger.info(f"Sending message to {request.to}")
        
        # Send via signal-cli
        result = await signal_client.send_message(
            recipient=request.to,
            message=request.message,
            attachment=request.attachment
        )
        
        logger.info(f"Message sent successfully to {request.to}")
        
        return SendMessageResponse(
            status="sent",
            timestamp=datetime.now().isoformat(),
            recipient=request.to,
            message_preview=request.message[:50] + "..." if len(request.message) > 50 else request.message
        )
        
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@private_app.get("/messages")
async def get_messages(
    limit: int = 100,
    offset: int = 0,
    sender: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """
    Retrieve stored messages from database
    Requires valid API key in X-API-Key header
    """
    try:
        messages = db.get_messages(limit=limit, offset=offset, sender=sender)
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
async def get_message(
    message_id: int,
    api_key: str = Depends(verify_api_key)
):
    """
    Retrieve a specific message by ID
    Requires valid API key in X-API-Key header
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


@private_app.get("/stats")
async def get_stats(api_key: str = Depends(verify_api_key)):
    """
    Get message statistics
    Requires valid API key in X-API-Key header
    """
    try:
        stats = db.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error retrieving stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics: {str(e)}")


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
        # Check if SSL certificates are configured
        use_ssl = (
            config.SSL_CERT_FILE and 
            config.SSL_KEY_FILE and 
            os.path.exists(config.SSL_CERT_FILE) and 
            os.path.exists(config.SSL_KEY_FILE)
        )
        
        if use_ssl:
            logger.info("Starting public interface on port 8443 with SSL")
            uvicorn.run(
                public_app,
                host="0.0.0.0",
                port=8443,
                ssl_keyfile=config.SSL_KEY_FILE,
                ssl_certfile=config.SSL_CERT_FILE,
                log_level="info"
            )
        else:
            logger.info("Starting public interface on port 8888 (HTTP - SSL handled by reverse proxy)")
            uvicorn.run(
                public_app,
                host="0.0.0.0",
                port=8888,
                log_level="info"
            )
    elif interface == "private":
        logger.info("Starting private interface on port 9000")
        uvicorn.run(
            private_app,
            host="127.0.0.1",  # Only bind to localhost for security
            port=9000,
            log_level="info"
        )
    else:
        print(f"Unknown interface: {interface}")
        print("Usage: python main.py [public|private]")
        sys.exit(1)
