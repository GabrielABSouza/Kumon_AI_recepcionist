-- Script SQL para criar tabela workflow_checkpoints no Railway PostgreSQL
-- Execute este script diretamente no Railway PostgreSQL Query tool

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create workflow_checkpoints table
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

-- Create performance indexes
CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_thread ON workflow_checkpoints(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_stage ON workflow_checkpoints(stage, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_recent ON workflow_checkpoints(created_at DESC) 
    WHERE created_at > NOW() - INTERVAL '7 days';

-- Create update trigger function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create update trigger
CREATE TRIGGER tr_workflow_checkpoints_updated_at
    BEFORE UPDATE ON workflow_checkpoints
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Verify table creation
SELECT 
    'workflow_checkpoints' as table_name,
    COUNT(*) as record_count,
    'Table created successfully' as status
FROM workflow_checkpoints;