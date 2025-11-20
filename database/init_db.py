"""
Database schema initialization and migration script
Run this to set up or upgrade the database
"""

import sqlite3
import sys
from pathlib import Path

# Schema version
SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Messages table
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
);

CREATE INDEX IF NOT EXISTS idx_sender ON messages(sender_number);
CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp);
CREATE INDEX IF NOT EXISTS idx_received ON messages(received_at);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_number TEXT UNIQUE NOT NULL,
    contact_name TEXT,
    last_message_at TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contact ON conversations(contact_number);

-- Sent messages log
CREATE TABLE IF NOT EXISTS sent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient TEXT NOT NULL,
    message_body TEXT,
    attachment_path TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'sent',
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_sent_timestamp ON sent_messages(sent_at);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init_database(db_path: str):
    """Initialize database with schema"""
    print(f"Initializing database at {db_path}")
    
    # Create parent directory if needed
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Execute schema
    cursor.executescript(SCHEMA_SQL)
    
    # Record schema version
    cursor.execute(
        "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
        (SCHEMA_VERSION,)
    )
    
    conn.commit()
    conn.close()
    
    print(f"Database initialized successfully (schema version {SCHEMA_VERSION})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python init_db.py <database_path>")
        sys.exit(1)
    
    db_path = sys.argv[1]
    init_database(db_path)
