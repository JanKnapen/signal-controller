"""
Database module for SignalController
Handles message storage and retrieval using SQLite
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """SQLite database handler for Signal messages"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
        # Ensure parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
        
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    
    def _init_database(self):
        """Initialize database schema"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_number TEXT NOT NULL,
                sender_name TEXT,
                timestamp INTEGER NOT NULL,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_body TEXT,
                attachments TEXT,
                raw_data TEXT,
                processed BOOLEAN DEFAULT 0
            )
        ''')
        
        # Create indexes for messages table
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sender 
            ON messages(sender_number)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON messages(timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_received 
            ON messages(received_at)
        ''')
        
        # Conversations table (aggregate view)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_number TEXT UNIQUE NOT NULL,
                contact_name TEXT,
                last_message_at TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Sent messages log (optional)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient TEXT NOT NULL,
                message_body TEXT,
                attachment_path TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'sent',
                error_message TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database initialized at {self.db_path}")
    
    def store_message(
        self,
        sender_number: str,
        sender_name: str,
        timestamp: int,
        message_body: str,
        attachments: List[Dict] = None,
        raw_data: Dict = None
    ) -> int:
        """
        Store an incoming message
        
        Args:
            sender_number: Phone number of sender
            sender_name: Display name of sender
            timestamp: Message timestamp (milliseconds)
            message_body: Message text
            attachments: List of attachment metadata
            raw_data: Raw envelope data from signal-cli
            
        Returns:
            Message ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Convert attachments and raw_data to JSON strings
        attachments_json = json.dumps(attachments) if attachments else None
        raw_data_json = json.dumps(raw_data) if raw_data else None
        
        cursor.execute('''
            INSERT INTO messages (
                sender_number, sender_name, timestamp, message_body,
                attachments, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            sender_number,
            sender_name,
            timestamp,
            message_body,
            attachments_json,
            raw_data_json
        ))
        
        message_id = cursor.lastrowid
        
        # Update or create conversation entry
        cursor.execute('''
            INSERT INTO conversations (contact_number, contact_name, last_message_at, message_count)
            VALUES (?, ?, CURRENT_TIMESTAMP, 1)
            ON CONFLICT(contact_number) DO UPDATE SET
                contact_name = excluded.contact_name,
                last_message_at = CURRENT_TIMESTAMP,
                message_count = message_count + 1
        ''', (sender_number, sender_name))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Stored message {message_id} from {sender_number}")
        return message_id
    
    def get_messages(
        self,
        limit: int = 100,
        offset: int = 0,
        sender: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve messages from database
        
        Args:
            limit: Maximum number of messages to return
            offset: Number of messages to skip
            sender: Filter by sender number (optional)
            
        Returns:
            List of message dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if sender:
            cursor.execute('''
                SELECT * FROM messages
                WHERE sender_number = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (sender, limit, offset))
        else:
            cursor.execute('''
                SELECT * FROM messages
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            message = dict(row)
            # Parse JSON fields
            if message['attachments']:
                message['attachments'] = json.loads(message['attachments'])
            if message['raw_data']:
                message['raw_data'] = json.loads(message['raw_data'])
            messages.append(message)
        
        return messages
    
    def get_message_by_id(self, message_id: int) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific message by ID
        
        Args:
            message_id: Message ID
            
        Returns:
            Message dictionary or None
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM messages WHERE id = ?', (message_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        message = dict(row)
        if message['attachments']:
            message['attachments'] = json.loads(message['attachments'])
        if message['raw_data']:
            message['raw_data'] = json.loads(message['raw_data'])
        
        return message
    
    def get_conversations(self) -> List[Dict[str, Any]]:
        """
        Get all conversations with message counts
        
        Returns:
            List of conversation dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM conversations
            ORDER BY last_message_at DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def update_conversation(
        self,
        contact_number: str,
        contact_name: Optional[str] = None,
        last_message_at: Optional[datetime] = None
    ):
        """
        Update or create a conversation entry
        
        Args:
            contact_number: Contact phone number
            contact_name: Contact name (optional)
            last_message_at: Timestamp of last message (optional)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Note: This is also handled automatically in store_message,
        # but this method provides explicit control
        cursor.execute('''
            INSERT INTO conversations (contact_number, contact_name, last_message_at, message_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(contact_number) DO UPDATE SET
                contact_name = COALESCE(excluded.contact_name, contact_name),
                last_message_at = COALESCE(excluded.last_message_at, last_message_at),
                message_count = message_count + 1
        ''', (contact_number, contact_name, last_message_at))
        
        conn.commit()
        conn.close()
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics
        
        Returns:
            Dictionary with statistics
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Total messages
        cursor.execute('SELECT COUNT(*) as count FROM messages')
        total_messages = cursor.fetchone()['count']
        
        # Total conversations
        cursor.execute('SELECT COUNT(*) as count FROM conversations')
        total_conversations = cursor.fetchone()['count']
        
        # Messages today
        cursor.execute('''
            SELECT COUNT(*) as count FROM messages
            WHERE DATE(received_at) = DATE('now')
        ''')
        messages_today = cursor.fetchone()['count']
        
        # Top senders
        cursor.execute('''
            SELECT sender_number, sender_name, COUNT(*) as count
            FROM messages
            GROUP BY sender_number
            ORDER BY count DESC
            LIMIT 10
        ''')
        top_senders = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'total_messages': total_messages,
            'total_conversations': total_conversations,
            'messages_today': messages_today,
            'top_senders': top_senders,
            'database_path': self.db_path
        }
    
    def log_sent_message(
        self,
        recipient: str,
        message_body: str,
        attachment_path: Optional[str] = None,
        status: str = 'sent',
        error_message: Optional[str] = None
    ) -> int:
        """
        Log a sent message
        
        Args:
            recipient: Recipient number
            message_body: Message text
            attachment_path: Path to attachment if any
            status: Status of send operation
            error_message: Error message if failed
            
        Returns:
            Log entry ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sent_messages (
                recipient, message_body, attachment_path, status, error_message
            ) VALUES (?, ?, ?, ?, ?)
        ''', (recipient, message_body, attachment_path, status, error_message))
        
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return log_id
