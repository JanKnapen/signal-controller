"""
Message-related API endpoints
"""

import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException

from backend.models import SendMessageRequest, SendMessageResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def create_messages_router(config, db, signal_client):
    """
    Factory function to create messages router with dependencies
    
    Args:
        config: Config instance
        db: Database instance
        signal_client: SignalClient instance
    """
    
    @router.post("/send", response_model=SendMessageResponse)
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
                success=True,
                timestamp=int(datetime.now().timestamp() * 1000),
                recipient=request_data.to,
                message_text=request_data.message,
                message_id=message_id if 'message_id' in locals() else None
            )
            
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


    @router.get("/messages")
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


    @router.get("/messages/{message_id}")
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


    @router.get("/conversations")
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


    @router.get("/groups")
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


    @router.get("/groups/{group_id}/messages")
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


    @router.get("/stats")
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
    
    return router
