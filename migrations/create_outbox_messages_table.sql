-- Create outbox_messages table for reliable message delivery
-- Migration: create_outbox_messages_table
-- Description: Creates table for persistent outbox message storage with delivery tracking

-- Drop table if exists (for clean migration)
DROP TABLE IF EXISTS outbox_messages CASCADE;

-- Create outbox_messages table
CREATE TABLE outbox_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    text TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'whatsapp',
    meta JSONB DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'SENT', 'FAILED')),
    message_order INTEGER NOT NULL DEFAULT 0,
    provider_message_id TEXT,
    error_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ
);

-- Create indexes for optimal query performance
CREATE INDEX idx_outbox_conversation_status ON outbox_messages (conversation_id, status);
CREATE INDEX idx_outbox_status_created ON outbox_messages (status, created_at);
CREATE INDEX idx_outbox_conversation_order ON outbox_messages (conversation_id, message_order);
CREATE INDEX idx_outbox_created_at ON outbox_messages (created_at);
CREATE UNIQUE INDEX idx_outbox_idempotency ON outbox_messages (idempotency_key);
CREATE INDEX idx_outbox_provider_id ON outbox_messages (provider_message_id) WHERE provider_message_id IS NOT NULL;

-- Add comment to table
COMMENT ON TABLE outbox_messages IS 'Persistent storage for planned messages with delivery tracking';
COMMENT ON COLUMN outbox_messages.conversation_id IS 'Unique conversation identifier';
COMMENT ON COLUMN outbox_messages.idempotency_key IS 'Unique key to prevent duplicate processing';
COMMENT ON COLUMN outbox_messages.text IS 'Message text content';
COMMENT ON COLUMN outbox_messages.channel IS 'Delivery channel (whatsapp, web, app)';
COMMENT ON COLUMN outbox_messages.meta IS 'Additional message metadata as JSON';
COMMENT ON COLUMN outbox_messages.status IS 'Message delivery status';
COMMENT ON COLUMN outbox_messages.message_order IS 'Order of message within conversation';
COMMENT ON COLUMN outbox_messages.provider_message_id IS 'Message ID from delivery provider';
COMMENT ON COLUMN outbox_messages.error_reason IS 'Reason for delivery failure';
COMMENT ON COLUMN outbox_messages.created_at IS 'When message was created';
COMMENT ON COLUMN outbox_messages.sent_at IS 'When message was successfully sent';
COMMENT ON COLUMN outbox_messages.failed_at IS 'When message delivery failed';

-- Grant necessary permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON outbox_messages TO kumon_app;

-- Migration completed successfully
SELECT 'outbox_messages table created successfully' as migration_result;