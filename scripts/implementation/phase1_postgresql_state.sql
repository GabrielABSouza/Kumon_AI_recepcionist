-- FASE 1: PostgreSQL Workflow State Persistence
-- SuperClaude Framework Implementation Script

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search optimization

-- Drop existing tables if needed (BE CAREFUL IN PRODUCTION!)
-- DROP TABLE IF EXISTS workflow_checkpoints CASCADE;
-- DROP TABLE IF EXISTS workflow_states CASCADE;

-- =====================================================
-- WORKFLOW STATE PERSISTENCE
-- =====================================================

-- Main workflow state table
CREATE TABLE IF NOT EXISTS workflow_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR(20) NOT NULL,
    thread_id VARCHAR(100) NOT NULL UNIQUE,
    current_stage VARCHAR(50) NOT NULL,
    current_step VARCHAR(50),
    state_data JSONB NOT NULL DEFAULT '{}',
    
    -- Conversation context
    conversation_history JSONB DEFAULT '[]',
    user_profile JSONB DEFAULT '{}',
    
    -- Intent and scheduling data
    detected_intent VARCHAR(100),
    scheduling_data JSONB DEFAULT '{}',
    validation_status VARCHAR(50),
    
    -- Timestamps
    last_activity TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Performance tracking
    message_count INTEGER DEFAULT 0,
    total_processing_time_ms NUMERIC DEFAULT 0,
    
    -- Constraints
    CONSTRAINT valid_stage CHECK (
        current_stage IN (
            'greeting', 'qualification', 'information',
            'scheduling', 'validation', 'confirmation',
            'handoff', 'completed', 'error'
        )
    )
);

-- Indexes for fast lookups
CREATE INDEX idx_phone_activity ON workflow_states(phone_number, last_activity DESC);
CREATE INDEX idx_thread ON workflow_states(thread_id);
CREATE INDEX idx_stage ON workflow_states(current_stage);
CREATE INDEX idx_active_sessions ON workflow_states(last_activity) 
    WHERE current_stage NOT IN ('completed', 'error');

-- GIN index for JSONB queries
CREATE INDEX idx_state_data ON workflow_states USING GIN (state_data);
CREATE INDEX idx_user_profile ON workflow_states USING GIN (user_profile);

-- =====================================================
-- WORKFLOW CHECKPOINTS (For Recovery)
-- =====================================================

CREATE TABLE IF NOT EXISTS workflow_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(100) NOT NULL,
    stage VARCHAR(50) NOT NULL,
    checkpoint_data JSONB NOT NULL,
    
    -- Checkpoint metadata
    checkpoint_type VARCHAR(50) DEFAULT 'auto', -- auto, manual, error
    checkpoint_reason TEXT,
    
    -- Recovery information
    is_recoverable BOOLEAN DEFAULT TRUE,
    recovery_attempts INTEGER DEFAULT 0,
    last_recovery_attempt TIMESTAMP WITH TIME ZONE,
    
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Foreign key
    CONSTRAINT fk_workflow_state 
        FOREIGN KEY (thread_id) 
        REFERENCES workflow_states(thread_id) 
        ON DELETE CASCADE
);

-- Indexes for checkpoints
CREATE INDEX idx_thread_checkpoint ON workflow_checkpoints(thread_id, created_at DESC);
CREATE INDEX idx_checkpoint_type ON workflow_checkpoints(checkpoint_type);
CREATE INDEX idx_recoverable ON workflow_checkpoints(is_recoverable) 
    WHERE is_recoverable = TRUE;

-- =====================================================
-- PERFORMANCE TRACKING TABLE
-- =====================================================

CREATE TABLE IF NOT EXISTS workflow_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(100) NOT NULL,
    
    -- Performance metrics
    operation_type VARCHAR(50) NOT NULL, -- 'message_processing', 'state_transition', etc
    duration_ms INTEGER NOT NULL,
    
    -- Context
    from_stage VARCHAR(50),
    to_stage VARCHAR(50),
    
    -- Resource usage
    tokens_used INTEGER,
    cache_hits INTEGER DEFAULT 0,
    cache_misses INTEGER DEFAULT 0,
    
    -- Timestamp
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Foreign key
    CONSTRAINT fk_workflow_perf 
        FOREIGN KEY (thread_id) 
        REFERENCES workflow_states(thread_id) 
        ON DELETE CASCADE
);

-- Performance indexes
CREATE INDEX idx_perf_thread ON workflow_performance(thread_id);
CREATE INDEX idx_perf_time ON workflow_performance(recorded_at DESC);
CREATE INDEX idx_perf_operation ON workflow_performance(operation_type);

-- =====================================================
-- FUNCTIONS FOR STATE MANAGEMENT
-- =====================================================

-- Function to update workflow state with automatic timestamp
CREATE OR REPLACE FUNCTION update_workflow_state(
    p_thread_id VARCHAR(100),
    p_stage VARCHAR(50),
    p_step VARCHAR(50),
    p_state_data JSONB
) RETURNS UUID AS $$
DECLARE
    v_state_id UUID;
BEGIN
    UPDATE workflow_states
    SET 
        current_stage = p_stage,
        current_step = p_step,
        state_data = state_data || p_state_data,
        last_activity = NOW(),
        updated_at = NOW(),
        message_count = message_count + 1
    WHERE thread_id = p_thread_id
    RETURNING id INTO v_state_id;
    
    -- Create checkpoint for important stages
    IF p_stage IN ('scheduling', 'validation', 'confirmation') THEN
        INSERT INTO workflow_checkpoints (
            thread_id,
            stage,
            checkpoint_data,
            checkpoint_type
        ) VALUES (
            p_thread_id,
            p_stage,
            p_state_data,
            'auto'
        );
    END IF;
    
    RETURN v_state_id;
END;
$$ LANGUAGE plpgsql;

-- Function to recover from checkpoint
CREATE OR REPLACE FUNCTION recover_from_checkpoint(
    p_thread_id VARCHAR(100)
) RETURNS JSONB AS $$
DECLARE
    v_checkpoint RECORD;
    v_result JSONB;
BEGIN
    -- Get latest recoverable checkpoint
    SELECT * INTO v_checkpoint
    FROM workflow_checkpoints
    WHERE thread_id = p_thread_id
      AND is_recoverable = TRUE
    ORDER BY created_at DESC
    LIMIT 1;
    
    IF v_checkpoint IS NULL THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'No recoverable checkpoint found'
        );
    END IF;
    
    -- Update recovery attempt
    UPDATE workflow_checkpoints
    SET 
        recovery_attempts = recovery_attempts + 1,
        last_recovery_attempt = NOW()
    WHERE id = v_checkpoint.id;
    
    -- Restore state
    UPDATE workflow_states
    SET 
        current_stage = v_checkpoint.stage,
        state_data = state_data || v_checkpoint.checkpoint_data,
        last_activity = NOW()
    WHERE thread_id = p_thread_id;
    
    RETURN jsonb_build_object(
        'success', true,
        'checkpoint_id', v_checkpoint.id,
        'stage', v_checkpoint.stage,
        'data', v_checkpoint.checkpoint_data
    );
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- MATERIALIZED VIEWS FOR ANALYTICS
-- =====================================================

-- Active sessions view
CREATE MATERIALIZED VIEW IF NOT EXISTS active_sessions_stats AS
SELECT 
    DATE_TRUNC('hour', last_activity) as hour,
    COUNT(*) as active_sessions,
    COUNT(DISTINCT phone_number) as unique_users,
    AVG(message_count) as avg_messages_per_session,
    AVG(total_processing_time_ms / NULLIF(message_count, 0)) as avg_response_time_ms
FROM workflow_states
WHERE last_activity > NOW() - INTERVAL '24 hours'
  AND current_stage NOT IN ('completed', 'error')
GROUP BY DATE_TRUNC('hour', last_activity)
WITH DATA;

-- Create indexes on materialized view
CREATE INDEX idx_active_sessions_hour ON active_sessions_stats(hour DESC);

-- Refresh function
CREATE OR REPLACE FUNCTION refresh_session_stats() RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY active_sessions_stats;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- PARTITIONING FOR SCALABILITY (Optional)
-- =====================================================

-- Partition workflow_performance by month for better performance
-- CREATE TABLE workflow_performance_2025_01 PARTITION OF workflow_performance
-- FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');

-- =====================================================
-- INITIAL DATA AND PERMISSIONS
-- =====================================================

-- Grant permissions (adjust user as needed)
GRANT ALL ON ALL TABLES IN SCHEMA public TO kumon_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO kumon_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO kumon_user;

-- =====================================================
-- MONITORING QUERIES
-- =====================================================

-- Query to check active sessions
/*
SELECT 
    phone_number,
    current_stage,
    current_step,
    EXTRACT(EPOCH FROM (NOW() - last_activity))::INT as seconds_inactive,
    message_count
FROM workflow_states
WHERE last_activity > NOW() - INTERVAL '1 hour'
  AND current_stage NOT IN ('completed', 'error')
ORDER BY last_activity DESC;
*/

-- Query to check performance metrics
/*
SELECT 
    operation_type,
    COUNT(*) as operation_count,
    AVG(duration_ms) as avg_duration_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) as p95_duration_ms,
    MAX(duration_ms) as max_duration_ms
FROM workflow_performance
WHERE recorded_at > NOW() - INTERVAL '1 hour'
GROUP BY operation_type
ORDER BY avg_duration_ms DESC;
*/

-- Create notification for slow queries
CREATE OR REPLACE FUNCTION notify_slow_operation() RETURNS TRIGGER AS $$
BEGIN
    IF NEW.duration_ms > 1000 THEN
        PERFORM pg_notify(
            'slow_operation',
            json_build_object(
                'thread_id', NEW.thread_id,
                'operation', NEW.operation_type,
                'duration_ms', NEW.duration_ms
            )::text
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_slow_operation
AFTER INSERT ON workflow_performance
FOR EACH ROW
EXECUTE FUNCTION notify_slow_operation();

-- =====================================================
-- MIGRATION HELPERS
-- =====================================================

-- Function to migrate from memory-only to persistent state
CREATE OR REPLACE FUNCTION migrate_memory_sessions(
    p_sessions JSONB
) RETURNS INTEGER AS $$
DECLARE
    v_session JSONB;
    v_count INTEGER := 0;
BEGIN
    FOR v_session IN SELECT * FROM jsonb_array_elements(p_sessions)
    LOOP
        INSERT INTO workflow_states (
            phone_number,
            thread_id,
            current_stage,
            current_step,
            state_data,
            conversation_history,
            user_profile
        ) VALUES (
            v_session->>'phone_number',
            v_session->>'thread_id',
            v_session->>'current_stage',
            v_session->>'current_step',
            COALESCE(v_session->'state_data', '{}'),
            COALESCE(v_session->'messages', '[]'),
            COALESCE(v_session->'user_profile', '{}')
        ) ON CONFLICT (thread_id) DO UPDATE
        SET 
            state_data = EXCLUDED.state_data,
            last_activity = NOW();
        
        v_count := v_count + 1;
    END LOOP;
    
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- SUCCESS MESSAGE
-- =====================================================
DO $$
BEGIN
    RAISE NOTICE 'PostgreSQL Workflow State Persistence setup completed successfully!';
    RAISE NOTICE 'Tables created: workflow_states, workflow_checkpoints, workflow_performance';
    RAISE NOTICE 'Functions created: update_workflow_state, recover_from_checkpoint';
    RAISE NOTICE 'Materialized view created: active_sessions_stats';
    RAISE NOTICE 'Run refresh_session_stats() periodically to update analytics';
END $$;