#!/usr/bin/env python3
"""
Run outbox_messages table migration
Applies the database migration for persistent message delivery
"""

import os
import sys
import logging
from pathlib import Path

# Add app to path for imports
sys.path.append(str(Path(__file__).parent))

from app.core.database.connection import get_database_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Run the outbox_messages table migration"""
    
    # Get database connection
    conn = get_database_connection()
    if not conn:
        logger.error("❌ Cannot connect to database. Check DATABASE_URL environment variable.")
        return False
    
    try:
        # Read migration SQL
        migration_file = Path(__file__).parent / "migrations" / "create_outbox_messages_table.sql"
        
        if not migration_file.exists():
            logger.error(f"❌ Migration file not found: {migration_file}")
            return False
        
        migration_sql = migration_file.read_text()
        
        # Execute migration
        logger.info("🔄 Running outbox_messages table migration...")
        
        with conn.cursor() as cur:
            cur.execute(migration_sql)
            
            # Get result message
            result = cur.fetchone()
            if result:
                logger.info(f"✅ {result[0]}")
            else:
                logger.info("✅ Migration executed successfully")
        
        logger.info("🎉 Outbox messages table migration completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


def verify_migration():
    """Verify that the migration was successful"""
    
    conn = get_database_connection()
    if not conn:
        logger.error("❌ Cannot connect to database for verification")
        return False
    
    try:
        with conn.cursor() as cur:
            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'outbox_messages'
                );
            """)
            
            table_exists = cur.fetchone()[0]
            
            if table_exists:
                # Check table structure
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'outbox_messages'
                    ORDER BY ordinal_position;
                """)
                
                columns = cur.fetchall()
                logger.info(f"✅ Table 'outbox_messages' exists with {len(columns)} columns:")
                
                for col_name, data_type, nullable in columns:
                    null_str = "NULL" if nullable == "YES" else "NOT NULL"
                    logger.info(f"   - {col_name}: {data_type} {null_str}")
                
                # Check indexes
                cur.execute("""
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename = 'outbox_messages'
                    ORDER BY indexname;
                """)
                
                indexes = cur.fetchall()
                logger.info(f"✅ Found {len(indexes)} indexes:")
                for idx in indexes:
                    logger.info(f"   - {idx[0]}")
                
                return True
            else:
                logger.error("❌ Table 'outbox_messages' was not created")
                return False
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        return False
        
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    print("🚀 Kumon AI Receptionist - Outbox Migration")
    print("=" * 50)
    
    # Run migration
    if run_migration():
        print("\n🔍 Verifying migration...")
        if verify_migration():
            print("\n🎉 Migration completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Migration verification failed!")
            sys.exit(1)
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)