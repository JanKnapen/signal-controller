"""
Webhook management API endpoints
"""

import logging
import secrets
from datetime import datetime
from fastapi import APIRouter, HTTPException

from backend.models import WebhookSubscribeRequest, WebhookUnsubscribeRequest
from backend.webhooks import send_webhook_challenge, notify_webhook_subscriber
from backend.security import is_private_network_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


def create_webhooks_router(config, db):
    """
    Factory function to create webhooks router with dependencies
    
    Args:
        config: Config instance
        db: Database instance
    """
    
    @router.post("/subscribe")
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
            if not is_private_network_url(config, callback_url):
                raise HTTPException(
                    status_code=403,
                    detail="Webhook URL must be on a whitelisted IP address"
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


    @router.post("/unsubscribe")
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


    @router.get("/subscribers")
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


    @router.post("/test")
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
            
            await notify_webhook_subscriber(db, callback_url, secret, test_payload)
            
            return {
                "status": "success",
                "message": "Test webhook sent successfully",
                "callback_url": callback_url
            }
            
        except Exception as e:
            logger.error(f"Error testing webhook: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Webhook test failed: {str(e)}")
    
    return router
