"""
Signal message processing and SSE listener
"""

import logging
import asyncio
import httpx
import json
from datetime import datetime

logger = logging.getLogger(__name__)


async def listen_to_signal_events(config, process_func):
    """
    Background task to listen to signal-cli SSE stream for incoming messages
    
    Args:
        config: Config instance
        process_func: Function to call for processing each message
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
                                await process_func(data)
                            except json.JSONDecodeError as e:
                                logger.error(f"Failed to parse SSE data: {e}")
                                
        except Exception as e:
            logger.error(f"SSE connection error: {e}")
            logger.info("Reconnecting in 5 seconds...")
            await asyncio.sleep(5)


async def process_incoming_message(db, notify_webhooks_func, data: dict):
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
        asyncio.create_task(notify_webhooks_func(webhook_data))
        
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
