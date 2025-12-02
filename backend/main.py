"""
SignalController - Main FastAPI Application
This service provides two interfaces:
1. Public interface (port 8888) - Receives incoming Signal messages
2. Private interface (port 9000) - Sends Signal messages (internal only)
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from datetime import datetime
import logging
import asyncio
from functools import partial

from database.db import Database
from backend.signal_client import SignalClient
from backend.config import Config
from backend.models import IncomingMessage
from backend.security import security_middleware
from backend.signal_processor import listen_to_signal_events, process_incoming_message
from backend.webhooks import notify_all_webhooks
from backend.routers.messages import create_messages_router
from backend.routers.webhooks import create_webhooks_router

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
    
    # Create bound process function with db and notify_webhooks
    notify_func = partial(notify_all_webhooks, db)
    process_func = partial(process_incoming_message, db, notify_func)
    
    # Start listener with config and process function
    asyncio.create_task(listen_to_signal_events(config, process_func))


@public_app.post("/api/v1/receive")
async def receive_signal_message(request: Request):
    """
    Endpoint to receive messages from signal-cli via HTTP POST
    This is an alternative to SSE for receiving messages
    """
    try:
        data = await request.json()
        logger.info(f"Received message via POST: {data}")
        
        # Create bound process function
        notify_func = partial(notify_all_webhooks, db)
        process_func = partial(process_incoming_message, db, notify_func)
        
        # Process the message
        await process_func(data)
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Error processing received message: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to process message: {str(e)}"}
        )


@public_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "SignalController-Public",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# PRIVATE INTERFACE - Port 9000 (Internal Network Only)
# ============================================================================

private_app = FastAPI(
    title="SignalController - Private Interface",
    description="Internal API for sending Signal messages (IP whitelist + API key required)",
    version="1.0.0"
)


# Add security middleware
@private_app.middleware("http")
async def apply_security_middleware(request: Request, call_next):
    """Apply IP whitelist and API key checks"""
    return await security_middleware(config, request, call_next)


# Include routers
messages_router = create_messages_router(config, db, signal_client)
webhooks_router = create_webhooks_router(config, db)

private_app.include_router(messages_router)
private_app.include_router(webhooks_router)


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
