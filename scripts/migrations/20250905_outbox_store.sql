-- Migration: Outbox Messages Store
-- Date: 2025-09-05
-- Purpose: Persistent storage for planned responses (1 per turn)
-- Architecture: TurnController → Planner → Delivery

-- Create outbox_messages table for durable outbox persistence
CREATE TABLE IF NOT EXISTS outbox_messages (
  -- Primary key: conversation + turn + item sequence
  conversation_id TEXT NOT NULL,
  turn_id TEXT NOT NULL, 
  item_index INT NOT NULL,
  
  -- Message payload and metadata
  payload JSONB NOT NULL,
  
  -- Delivery status tracking
  status TEXT NOT NULL DEFAULT 'queued', -- queued | sent | failed | discarded
  idempotency_key TEXT NOT NULL,
  
  -- Provider tracking
  sent_provider_id TEXT,
  
  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  sent_at TIMESTAMPTZ,
  
  -- Composite primary key
  PRIMARY KEY (conversation_id, turn_id, item_index)
);

-- Unique index for idempotency per conversation
CREATE UNIQUE INDEX IF NOT EXISTS outbox_idem_idx
  ON outbox_messages (conversation_id, idempotency_key);

-- Index for querying pending messages by conversation
CREATE INDEX IF NOT EXISTS outbox_pending_idx
  ON outbox_messages (conversation_id, status, created_at)
  WHERE status IN ('queued', 'failed');

-- Index for delivery status queries  
CREATE INDEX IF NOT EXISTS outbox_status_idx
  ON outbox_messages (status, created_at);

-- Comments for documentation
COMMENT ON TABLE outbox_messages IS 'Persistent storage for planned responses - 1 per turn via TurnController';
COMMENT ON COLUMN outbox_messages.turn_id IS 'Deterministic turn ID from TurnController.make_turn_id()';
COMMENT ON COLUMN outbox_messages.payload IS 'Serialized OutboxItem with text, channel, meta';
COMMENT ON COLUMN outbox_messages.idempotency_key IS 'Per-turn idempotency key for deduplication';
COMMENT ON COLUMN outbox_messages.sent_provider_id IS 'Provider ID returned by WhatsApp/SMS API';