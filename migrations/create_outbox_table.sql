-- Create outbox_messages table for persistent message storage
-- This table ensures messages are not lost between planner and delivery phases

CREATE TABLE IF NOT EXISTS outbox_messages (
    id SERIAL PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL,
    turn_id VARCHAR(255) NOT NULL,
    item_index INTEGER NOT NULL DEFAULT 0,
    payload JSONB NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    idempotency_key VARCHAR(255) NOT NULL,
    sent_provider_id VARCHAR(255),
    sent_at TIMESTAMP WITH TIME ZONE,
    failed_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure uniqueness per turn and item
    UNIQUE(conversation_id, turn_id, item_index)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_outbox_conversation_turn ON outbox_messages(conversation_id, turn_id);
CREATE INDEX IF NOT EXISTS idx_outbox_status ON outbox_messages(status);
CREATE INDEX IF NOT EXISTS idx_outbox_idempotency ON outbox_messages(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_outbox_created_at ON outbox_messages(created_at);

-- Create updated_at trigger for auto-updating timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_outbox_messages_updated_at ON outbox_messages;
CREATE TRIGGER update_outbox_messages_updated_at 
    BEFORE UPDATE ON outbox_messages 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Check for valid status values
ALTER TABLE outbox_messages DROP CONSTRAINT IF EXISTS chk_outbox_status;
ALTER TABLE outbox_messages ADD CONSTRAINT chk_outbox_status 
    CHECK (status IN ('queued', 'sent', 'failed', 'discarded'));
    
-- Comments for documentation
COMMENT ON TABLE outbox_messages IS 'Persistent storage for planned responses to prevent loss between planning and delivery phases';
COMMENT ON COLUMN outbox_messages.conversation_id IS 'Unique identifier for the conversation/session';
COMMENT ON COLUMN outbox_messages.turn_id IS 'Unique identifier for the conversation turn from TurnController';
COMMENT ON COLUMN outbox_messages.item_index IS 'Index of the message within the turn (typically 0 for single response per turn)';
COMMENT ON COLUMN outbox_messages.payload IS 'JSON payload containing message text, channel, meta, and other delivery info';
COMMENT ON COLUMN outbox_messages.status IS 'Processing status: queued, sent, failed, discarded';
COMMENT ON COLUMN outbox_messages.idempotency_key IS 'Unique key to prevent duplicate message delivery';
COMMENT ON COLUMN outbox_messages.sent_provider_id IS 'Provider message ID returned after successful delivery';