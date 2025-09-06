#!/usr/bin/env python3
"""
Run outbox table migration for Kumon AI Receptionist

This script creates the outbox_messages table needed for persistent
message storage between planner and delivery phases.
"""

import os
import sys
import psycopg2
from urllib.parse import urlparse

def run_migration():
    """Run the outbox table migration"""
    
    # Get database URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        print("Please set DATABASE_URL to your PostgreSQL connection string")
        sys.exit(1)
    
    try:
        # Parse database URL
        result = urlparse(database_url)
        
        # Connect to database
        conn = psycopg2.connect(
            database=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
        
        print(f"✅ Connected to database: {result.hostname}:{result.port}/{result.path[1:]}")
        
        # Read migration SQL
        migration_path = os.path.join(os.path.dirname(__file__), "migrations", "create_outbox_table.sql")
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        
        # Execute migration
        with conn.cursor() as cur:
            cur.execute(migration_sql)
            conn.commit()
            print("✅ Outbox table migration completed successfully")
        
        # Verify table creation
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name, column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'outbox_messages' 
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            
            if columns:
                print(f"✅ Table 'outbox_messages' created with {len(columns)} columns:")
                for table, col, dtype, nullable in columns[:5]:  # Show first 5 columns
                    null_str = "NULL" if nullable == "YES" else "NOT NULL"
                    print(f"  - {col}: {dtype} {null_str}")
                if len(columns) > 5:
                    print(f"  ... and {len(columns) - 5} more columns")
            else:
                print("❌ Table verification failed - no columns found")
        
        # Check indexes
        with conn.cursor() as cur:
            cur.execute("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'outbox_messages'
            """)
            indexes = cur.fetchall()
            
            if indexes:
                print(f"✅ Created {len(indexes)} indexes:")
                for (idx_name,) in indexes:
                    print(f"  - {idx_name}")
        
        conn.close()
        print("✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("🚀 Running outbox table migration...")
    run_migration()