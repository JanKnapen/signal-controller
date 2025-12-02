"""
Pydantic models for request/response validation
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional


class IncomingMessage(BaseModel):
    """Model for incoming Signal messages from signal-cli"""
    envelope: dict


class SendMessageRequest(BaseModel):
    """Request model for sending messages"""
    to: str = Field(..., description="Phone number or username to send to")
    message: str = Field(..., description="Message text to send")
    attachment: Optional[str] = Field(None, description="Path to attachment file (optional)")


class SendMessageResponse(BaseModel):
    """Response model for sent messages"""
    success: bool
    timestamp: int
    recipient: str
    message_text: str
    message_id: Optional[int] = None


class WebhookSubscribeRequest(BaseModel):
    """Request model for webhook subscription"""
    callback_url: HttpUrl = Field(..., description="URL to receive webhook notifications")
    secret: Optional[str] = Field(None, description="Optional secret for HMAC signing (will be generated if not provided)")


class WebhookUnsubscribeRequest(BaseModel):
    """Request model for webhook unsubscription"""
    callback_url: HttpUrl = Field(..., description="URL to unsubscribe from webhook notifications")
