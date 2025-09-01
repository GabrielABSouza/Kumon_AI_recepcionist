#!/usr/bin/env python3
"""
Script para criar tabela workflow_checkpoints no Railway PostgreSQL
"""

import os
import asyncio
import asyncpg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def create_workflow_checkpoints_table():
    """Cria tabela workflow_checkpoints no Railway PostgreSQL"""
    
    # Get DATABASE_URL from environment
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL not found in environment")
        print("   Make sure Railway DATABASE_URL is set")
        return False
    
    print(f"🔗 Connecting to Railway PostgreSQL...")
    print(f"   Database: {database_url.split('@')[1] if '@' in database_url else 'Unknown'}")
    
    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        print("✅ Connected successfully")
        
        # Enable UUID extension if needed
        print("🔧 Enabling uuid-ossp extension...")
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
        
        # Create workflow_checkpoints table
        print("🏗️  Creating workflow_checkpoints table...")
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS workflow_checkpoints (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            thread_id VARCHAR(100) NOT NULL,
            checkpoint_id VARCHAR(100) NOT NULL,
            
            -- Checkpoint content (LangGraph serialized state)
            checkpoint_data JSONB NOT NULL,
            metadata JSONB DEFAULT '{}'::jsonb NOT NULL,
            
            -- Workflow tracking
            stage VARCHAR(50) NOT NULL DEFAULT 'unknown',
            checkpoint_type VARCHAR(30) DEFAULT 'automatic',
            checkpoint_reason TEXT,
            
            -- Recovery and reliability
            recovery_attempts INTEGER DEFAULT 0 CHECK (recovery_attempts >= 0),
            recovery_success BOOLEAN DEFAULT NULL,
            
            -- Timestamps
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            
            -- Constraints
            UNIQUE(thread_id, checkpoint_id)
        );
        """
        
        await conn.execute(create_table_sql)
        print("✅ Table workflow_checkpoints created successfully")
        
        # Create performance indexes
        print("📊 Creating performance indexes...")
        index_sql = """
        CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_thread ON workflow_checkpoints(thread_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_stage ON workflow_checkpoints(stage, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_recent ON workflow_checkpoints(created_at DESC) 
            WHERE created_at > NOW() - INTERVAL '7 days';
        """
        
        await conn.execute(index_sql)
        print("✅ Indexes created successfully")
        
        # Create update trigger
        print("⚡ Creating update trigger...")
        trigger_sql = """
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER tr_workflow_checkpoints_updated_at
            BEFORE UPDATE ON workflow_checkpoints
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        """
        
        await conn.execute(trigger_sql)
        print("✅ Update trigger created successfully")
        
        # Verify table exists
        print("🔍 Verifying table creation...")
        result = await conn.fetchrow("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'workflow_checkpoints' 
            AND column_name = 'id'
        """)
        
        if result:
            print("✅ Table verification successful")
            print(f"   Table: {result['table_name']}")
            print(f"   Primary Key: {result['column_name']} ({result['data_type']})")
        else:
            print("❌ Table verification failed")
            return False
        
        # Show table info
        print("📋 Table summary:")
        count_result = await conn.fetchrow("SELECT COUNT(*) FROM workflow_checkpoints")
        print(f"   Records: {count_result['count']}")
        
        await conn.close()
        print("🎉 Railway PostgreSQL setup completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error creating table: {e}")
        return False

async def main():
    """Main function"""
    print("🚀 Creating workflow_checkpoints table on Railway PostgreSQL")
    print("=" * 60)
    
    success = await create_workflow_checkpoints_table()
    
    print("=" * 60)
    if success:
        print("🎉 SUCCESS: workflow_checkpoints table created on Railway!")
        print("   The LangGraph PostgreSQL checkpointer is now ready to use.")
    else:
        print("💥 FAILED: Could not create workflow_checkpoints table")
        print("   Check the error messages above for details.")

if __name__ == "__main__":
    asyncio.run(main())