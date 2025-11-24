#!/usr/bin/env python3
"""
Database migration script to add group support
Adds group_id and group_name columns to messages table
Adds is_group and group_id columns to conversations table
"""

import sqlite3
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

DB_PATH = '/var/lib/signal-controller/messages.db'


def migrate_database():
    """Add group support columns to existing database"""
    print(f"Migrating database: {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Add columns to messages table
        print("Adding group columns to messages table...")
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN group_id TEXT')
            print("  ✓ Added group_id column")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print("  ✓ group_id column already exists")
            else:
                raise
        
        try:
            cursor.execute('ALTER TABLE messages ADD COLUMN group_name TEXT')
            print("  ✓ Added group_name column")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print("  ✓ group_name column already exists")
            else:
                raise
        
        # Add columns to conversations table
        print("Adding group columns to conversations table...")
        try:
            cursor.execute('ALTER TABLE conversations ADD COLUMN is_group BOOLEAN DEFAULT 0')
            print("  ✓ Added is_group column")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print("  ✓ is_group column already exists")
            else:
                raise
        
        try:
            cursor.execute('ALTER TABLE conversations ADD COLUMN group_id TEXT')
            print("  ✓ Added group_id column")
        except sqlite3.OperationalError as e:
            if 'duplicate column name' in str(e):
                print("  ✓ group_id column already exists")
            else:
                raise
        
        # Create index for group_id
        print("Creating index for group_id...")
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_id ON messages(group_id)')
            print("  ✓ Created index on messages.group_id")
        except Exception as e:
            print(f"  ⚠ Index creation failed (may already exist): {e}")
        
        # Backfill group data from raw_data JSON
        print("\nBackfilling group data from existing messages...")
        cursor.execute('SELECT id, raw_data FROM messages WHERE raw_data IS NOT NULL AND group_id IS NULL')
        rows = cursor.fetchall()
        
        updated_count = 0
        group_messages_count = 0
        
        for row_id, raw_data_str in rows:
            try:
                # Handle both string and already-parsed dict
                if isinstance(raw_data_str, str):
                    raw_data = json.loads(raw_data_str)
                else:
                    raw_data = raw_data_str
                
                envelope = raw_data.get('envelope', {})
                data_message = envelope.get('dataMessage', {})
                group_info = data_message.get('groupInfo', {})
                
                if group_info:
                    group_id = group_info.get('groupId')
                    group_name = group_info.get('groupName')
                    
                    if group_id:
                        cursor.execute('''
                            UPDATE messages 
                            SET group_id = ?, group_name = ?
                            WHERE id = ?
                        ''', (group_id, group_name, row_id))
                        
                        updated_count += 1
                        group_messages_count += 1
                        
            except (json.JSONDecodeError, KeyError, AttributeError) as e:
                print(f"  ⚠ Could not parse message {row_id}: {e}")
                continue
        
        print(f"  ✓ Updated {updated_count} existing group messages")
        
        # Create group conversations from group messages
        if group_messages_count > 0:
            print("\nCreating group conversation entries...")
            cursor.execute('''
                SELECT DISTINCT group_id, group_name, MAX(timestamp) as last_ts
                FROM messages
                WHERE group_id IS NOT NULL
                GROUP BY group_id
            ''')
            
            group_rows = cursor.fetchall()
            for group_id, group_name, last_ts in group_rows:
                # Count messages in this group
                cursor.execute('SELECT COUNT(*) FROM messages WHERE group_id = ?', (group_id,))
                msg_count = cursor.fetchone()[0]
                
                # Insert or update conversation
                cursor.execute('''
                    INSERT INTO conversations (contact_number, contact_name, last_message_at, message_count, is_group, group_id)
                    VALUES (?, ?, datetime(?, 'unixepoch', 'subsec'), ?, 1, ?)
                    ON CONFLICT(contact_number) DO UPDATE SET
                        contact_name = excluded.contact_name,
                        last_message_at = excluded.last_message_at,
                        message_count = excluded.message_count,
                        is_group = 1,
                        group_id = excluded.group_id
                ''', (group_id, group_name, last_ts / 1000.0, msg_count, group_id))
            
            print(f"  ✓ Created {len(group_rows)} group conversation entries")
        
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
