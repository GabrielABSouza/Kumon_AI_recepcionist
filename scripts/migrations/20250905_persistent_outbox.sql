-- Migration: Persistent Outbox Table for LangGraph Workflow
-- Date: 2025-09-05
-- Purpose: Solve outbox loss between Planner and Delivery nodes
-- Architecture: Planner saves → Delivery reads from DB → Mark sent

-- Create persistent outbox table
CREATE TABLE IF NOT EXISTS persistent_outbox (
  -- Primary key
  id SERIAL PRIMARY KEY,
  
  -- Conversation identification
  conversation_id TEXT NOT NULL,
  
  -- Idempotency control (unique per conversation)
  idempotency_key TEXT NOT NULL,
  
  -- Message payload (JSON)
  payload JSONB NOT NULL,
  
  -- Delivery status tracking
  status TEXT NOT NULL DEFAULT 'pending', -- pending | sent | failed
  
  -- Evolution API tracking
  evolution_message_id TEXT,
  
  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at TIMESTAMPTZ,
  
  -- Unique constraint for idempotency
  CONSTRAINT unique_conversation_idempotency 
    UNIQUE (conversation_id, idempotency_key)
);

-- Index for fast queries by conversation + status
CREATE INDEX IF NOT EXISTS idx_persistent_outbox_conversation_status
  ON persistent_outbox (conversation_id, status, created_at);

-- Index for cleanup by timestamp
CREATE INDEX IF NOT EXISTS idx_persistent_outbox_created_at
  ON persistent_outbox (created_at);

-- Comments for documentation
COMMENT ON TABLE persistent_outbox IS 'Persistent storage for LangGraph workflow outbox messages';
COMMENT ON COLUMN persistent_outbox.conversation_id IS 'Session ID from conversation_sessions table';
COMMENT ON COLUMN persistent_outbox.idempotency_key IS 'Unique key to prevent duplicate message generation per conversation';
COMMENT ON COLUMN persistent_outbox.payload IS 'MessageEnvelope serialized as JSON';
COMMENT ON COLUMN persistent_outbox.status IS 'pending: ready to send | sent: delivered via Evolution API | failed: delivery error';
COMMENT ON COLUMN persistent_outbox.evolution_message_id IS 'Message ID returned by Evolution API after successful delivery';