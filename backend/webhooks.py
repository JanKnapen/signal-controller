"""
Webhook system for notifying subscribers of new Signal messages
"""

import logging
import asyncio
import httpx
import json
import hmac
import hashlib
import secrets
from typing import Optional

logger = logging.getLogger(__name__)


def compute_hmac(payload: str, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload"""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


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


async def notify_webhook_subscriber(db, callback_url: str, secret: str, message_data: dict, retry_count: int = 0):
    """
    Send webhook notification to a single subscriber with HMAC signing
    
    Args:
        db: Database instance
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
            await notify_webhook_subscriber(db, callback_url, secret, message_data, retry_count + 1)


async def notify_all_webhooks(db, message_data: dict):
    """Send webhook notifications to all active subscribers"""
    subscriptions = db.get_webhook_subscriptions(enabled_only=True)
    
    if not subscriptions:
        logger.debug("No active webhook subscriptions")
        return
    
    logger.info(f"Notifying {len(subscriptions)} webhook subscribers")
    
    # Send to all subscribers concurrently
    tasks = [
        notify_webhook_subscriber(db, sub['callback_url'], sub['secret'], message_data)
        for sub in subscriptions
    ]
    
    await asyncio.gather(*tasks, return_exceptions=True)
