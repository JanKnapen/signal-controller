#!/usr/bin/env python3
"""
Database migration script to add recipient_number column
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = '/var/lib/signal-controller/messages.db'


def migrate_database():
    """Add recipient_number column to messages table"""
    print(f"Migrating database: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Add recipient_number column
        print("Adding recipient_number column to messages table...")
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN recipient_number TEXT')
            print("  ✓ Added recipient_number column")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print("  ✓ recipient_number column already exists")
            else:
                raise
        
        # Create index for recipient_number
        print("Creating index for recipient_number...")
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_recipient ON messages(recipient_number)')
            print("  ✓ Created index on messages.recipient_number")
        except Exception as e:
            print(f"  ⚠ Index creation failed (may already exist): {e}")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    migrate_database()
