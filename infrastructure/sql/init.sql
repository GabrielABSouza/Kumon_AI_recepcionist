-- PostgreSQL Initialization Script for Kumon Conversation Analytics
-- Optimized for ML pipelines and BI analytics

-- ============================================================================
-- EXTENSIONS AND CONFIGURATION
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";     -- Trigram matching for similarity
CREATE EXTENSION IF NOT EXISTS "btree_gin";   -- GIN indexes for composite types
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"; -- Query performance monitoring

-- Set timezone to UTC for consistency
SET timezone = 'UTC';

-- Configure for analytics workload
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';
ALTER SYSTEM SET random_page_cost = 1.1;

-- Reload configuration
SELECT pg_reload_conf();

-- ============================================================================
-- WORKFLOW STATE MANAGEMENT (CeciliaWorkflow LangGraph Integration)
-- ============================================================================

-- Workflow checkpoints for LangGraph persistence
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

-- Workflow states for conversation management
CREATE TABLE IF NOT EXISTS workflow_states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    thread_id VARCHAR(100) NOT NULL UNIQUE,
    
    -- Core conversation state
    phone_number VARCHAR(20) NOT NULL,
    current_stage VARCHAR(50) NOT NULL DEFAULT 'greeting',
    current_step VARCHAR(50) NOT NULL DEFAULT 'welcome',
    last_user_message TEXT NOT NULL DEFAULT '',
    
    -- Collected data and metrics
    collected_data JSONB DEFAULT '{}'::jsonb NOT NULL,
    conversation_metrics JSONB DEFAULT '{}'::jsonb NOT NULL,
    data_validation JSONB DEFAULT '{}'::jsonb NOT NULL,
    decision_trail JSONB DEFAULT '{}'::jsonb NOT NULL,
    
    -- Status and lifecycle
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'completed', 'failed')),
    version INTEGER DEFAULT 1 CHECK (version > 0),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Performance indexes for workflow tables
CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_thread ON workflow_checkpoints(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_stage ON workflow_checkpoints(stage, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_checkpoints_recent ON workflow_checkpoints(created_at DESC) 
    WHERE created_at > NOW() - INTERVAL '7 days';

CREATE INDEX IF NOT EXISTS idx_workflow_states_phone ON workflow_states(phone_number);
CREATE INDEX IF NOT EXISTS idx_workflow_states_stage ON workflow_states(current_stage, current_step);
CREATE INDEX IF NOT EXISTS idx_workflow_states_active ON workflow_states(last_activity DESC) 
    WHERE status = 'active';

-- ============================================================================
-- CREATE ANALYTICS DATABASE SCHEMA
-- ============================================================================

-- User profiles dimension table (ML features + business data)
CREATE TABLE IF NOT EXISTS user_profiles (
    -- Primary identifiers
    user_id VARCHAR(50) PRIMARY KEY,
    phone_number VARCHAR(20) UNIQUE NOT NULL,
    
    -- Timestamps (critical for time-series analysis)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_interaction TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Personal information (collected during conversations)
    parent_name TEXT,
    preferred_name TEXT,
    child_name TEXT,
    child_age INTEGER CHECK (child_age > 0 AND child_age < 18),
    
    -- Preferences and interests (JSONB for flexible ML feature extraction)
    program_interests JSONB DEFAULT '[]'::jsonb NOT NULL,
    availability_preferences JSONB DEFAULT '{}'::jsonb NOT NULL,
    communication_preferences JSONB DEFAULT '{}'::jsonb NOT NULL,
    
    -- Aggregated behavioral metrics (computed from conversation data)
    total_interactions INTEGER DEFAULT 0 CHECK (total_interactions >= 0),
    total_messages INTEGER DEFAULT 0 CHECK (total_messages >= 0),
    avg_session_duration DECIMAL(10,2) DEFAULT 0 CHECK (avg_session_duration >= 0),
    conversion_events JSONB DEFAULT '[]'::jsonb NOT NULL,
    
    -- ML computed features (updated by analytics pipeline)
    engagement_score DECIMAL(5,4) DEFAULT 0 CHECK (engagement_score >= 0 AND engagement_score <= 1),
    churn_probability DECIMAL(5,4) DEFAULT 0 CHECK (churn_probability >= 0 AND churn_probability <= 1),
    lifetime_value_prediction DECIMAL(10,2) DEFAULT 0 CHECK (lifetime_value_prediction >= 0),
    persona_cluster TEXT,
    
    -- Metadata for schema evolution
    schema_version VARCHAR(10) DEFAULT '1.0' NOT NULL,
    
    -- Audit fields
    created_by VARCHAR(50) DEFAULT 'system',
    updated_by VARCHAR(50) DEFAULT 'system'
);

-- Conversation sessions fact table (main analytics table)
CREATE TABLE IF NOT EXISTS conversation_sessions (
    -- Primary identifiers
    session_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    
    -- Timestamps (partitioned by created_at for performance)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    
    -- Status and progression (categorical features for ML)
    status VARCHAR(20) NOT NULL DEFAULT 'active' 
        CHECK (status IN ('active', 'paused', 'completed', 'abandoned', 'escalated')),
    current_stage VARCHAR(30) NOT NULL DEFAULT 'greeting',
    current_step VARCHAR(50) NOT NULL DEFAULT 'welcome',
    
    -- Engagement metrics (numerical features for ML)
    message_count INTEGER DEFAULT 0 CHECK (message_count >= 0),
    duration_seconds INTEGER DEFAULT 0 CHECK (duration_seconds >= 0),
    failed_attempts INTEGER DEFAULT 0 CHECK (failed_attempts >= 0),
    sentiment_score_avg DECIMAL(5,4) DEFAULT 0 CHECK (sentiment_score_avg >= -1 AND sentiment_score_avg <= 1),
    satisfaction_score DECIMAL(5,4) DEFAULT 0 CHECK (satisfaction_score >= 0 AND satisfaction_score <= 1),
    
    -- Business metrics (target variables for ML)
    lead_score INTEGER DEFAULT 0 CHECK (lead_score >= 0 AND lead_score <= 100),
    lead_score_category VARCHAR(20) DEFAULT 'unqualified' 
        CHECK (lead_score_category IN ('hot', 'warm', 'cold', 'qualified', 'unqualified')),
    conversion_probability DECIMAL(5,4) DEFAULT 0 CHECK (conversion_probability >= 0 AND conversion_probability <= 1),
    estimated_value DECIMAL(10,2) DEFAULT 0 CHECK (estimated_value >= 0),
    
    -- ML features and predictions (flexible JSON for model evolution)
    session_features JSONB DEFAULT '{}'::jsonb NOT NULL,
    predictions JSONB DEFAULT '{}'::jsonb NOT NULL,
    labels JSONB DEFAULT '{}'::jsonb NOT NULL,
    
    -- Historical context (time-series data for analysis)
    stage_history JSONB DEFAULT '[]'::jsonb NOT NULL,
    conversion_events JSONB DEFAULT '[]'::jsonb NOT NULL,
    scheduling_context JSONB DEFAULT '{}'::jsonb NOT NULL,
    
    -- Metadata
    schema_version VARCHAR(10) DEFAULT '1.0' NOT NULL,
    created_by VARCHAR(50) DEFAULT 'system',
    updated_by VARCHAR(50) DEFAULT 'system',
    
    -- Foreign key constraint
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

-- Messages fact table (time-series optimized for NLP analysis)
CREATE TABLE IF NOT EXISTS conversation_messages (
    -- Primary identifiers
    message_id VARCHAR(50) PRIMARY KEY,
    conversation_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    
    -- Timestamp (primary partition key for time-series queries)
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Message content and metadata
    content TEXT NOT NULL,
    is_from_user BOOLEAN NOT NULL,
    message_type VARCHAR(20) DEFAULT 'text' 
        CHECK (message_type IN ('text', 'image', 'button', 'audio', 'document')),
    message_length INTEGER GENERATED ALWAYS AS (char_length(content)) STORED,
    
    -- NLP analysis results (computed by ML pipeline)
    intent VARCHAR(30),
    intent_confidence DECIMAL(5,4) DEFAULT 0 CHECK (intent_confidence >= 0 AND intent_confidence <= 1),
    sentiment VARCHAR(20) CHECK (sentiment IN ('very_positive', 'positive', 'neutral', 'negative', 'very_negative')),
    sentiment_score DECIMAL(5,4) DEFAULT 0 CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
    entities JSONB DEFAULT '[]'::jsonb NOT NULL,
    
    -- Conversation context
    conversation_stage VARCHAR(30) NOT NULL,
    conversation_step VARCHAR(50) NOT NULL,
    response_time_seconds DECIMAL(8,3) CHECK (response_time_seconds >= 0),
    
    -- ML features and embeddings
    features JSONB DEFAULT '{}'::jsonb NOT NULL,
    embeddings REAL[], -- Vector embeddings for semantic similarity
    
    -- Metadata
    schema_version VARCHAR(10) DEFAULT '1.0' NOT NULL,
    
    -- Foreign key constraints
    CONSTRAINT fk_message_session FOREIGN KEY (conversation_id) REFERENCES conversation_sessions(session_id),
    CONSTRAINT fk_message_user FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
);

-- Daily aggregation table for analytics dashboards
CREATE TABLE IF NOT EXISTS daily_conversation_metrics (
    date DATE PRIMARY KEY,
    
    -- Volume metrics
    total_sessions INTEGER DEFAULT 0 CHECK (total_sessions >= 0),
    active_sessions INTEGER DEFAULT 0 CHECK (active_sessions >= 0),
    completed_sessions INTEGER DEFAULT 0 CHECK (completed_sessions >= 0),
    abandoned_sessions INTEGER DEFAULT 0 CHECK (abandoned_sessions >= 0),
    escalated_sessions INTEGER DEFAULT 0 CHECK (escalated_sessions >= 0),
    
    -- Engagement metrics
    total_messages INTEGER DEFAULT 0 CHECK (total_messages >= 0),
    avg_session_duration DECIMAL(10,2) DEFAULT 0 CHECK (avg_session_duration >= 0),
    avg_messages_per_session DECIMAL(8,2) DEFAULT 0 CHECK (avg_messages_per_session >= 0),
    
    -- Quality metrics
    conversion_rate DECIMAL(5,4) DEFAULT 0 CHECK (conversion_rate >= 0 AND conversion_rate <= 1),
    satisfaction_avg DECIMAL(5,4) DEFAULT 0 CHECK (satisfaction_avg >= 0 AND satisfaction_avg <= 1),
    sentiment_avg DECIMAL(5,4) DEFAULT 0 CHECK (sentiment_avg >= -1 AND sentiment_avg <= 1),
    
    -- Business metrics
    total_conversions INTEGER DEFAULT 0 CHECK (total_conversions >= 0),
    estimated_revenue DECIMAL(12,2) DEFAULT 0 CHECK (estimated_revenue >= 0),
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hourly metrics for real-time monitoring
CREATE TABLE IF NOT EXISTS hourly_conversation_metrics (
    date DATE NOT NULL,
    hour INTEGER NOT NULL CHECK (hour >= 0 AND hour <= 23),
    
    -- Key metrics (subset of daily metrics for real-time dashboards)
    active_sessions INTEGER DEFAULT 0,
    new_sessions INTEGER DEFAULT 0,
    completed_sessions INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0,
    avg_response_time DECIMAL(8,3) DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    PRIMARY KEY (date, hour)
);

-- ============================================================================
-- PERFORMANCE INDEXES
-- ============================================================================

-- User profiles indexes
CREATE INDEX IF NOT EXISTS idx_user_profiles_phone ON user_profiles(phone_number);
CREATE INDEX IF NOT EXISTS idx_user_profiles_updated ON user_profiles(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_profiles_last_interaction ON user_profiles(last_interaction DESC);
CREATE INDEX IF NOT EXISTS idx_user_profiles_engagement ON user_profiles(engagement_score DESC);
CREATE INDEX IF NOT EXISTS idx_user_profiles_cluster ON user_profiles(persona_cluster) WHERE persona_cluster IS NOT NULL;

-- Session indexes (optimized for analytics queries)
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON conversation_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON conversation_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON conversation_sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_stage ON conversation_sessions(current_stage);
CREATE INDEX IF NOT EXISTS idx_sessions_lead_score ON conversation_sessions(lead_score_category);
CREATE INDEX IF NOT EXISTS idx_sessions_phone ON conversation_sessions(phone_number);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON conversation_sessions(user_id, status) WHERE status = 'active';

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_sessions_analytics ON conversation_sessions(created_at DESC, status, lead_score_category);
CREATE INDEX IF NOT EXISTS idx_sessions_conversion ON conversation_sessions(created_at DESC) WHERE conversion_events != '[]'::jsonb;

-- Message indexes (time-series optimized)
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON conversation_messages(conversation_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON conversation_messages(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON conversation_messages(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_intent ON conversation_messages(intent) WHERE intent IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_sentiment ON conversation_messages(sentiment) WHERE sentiment IS NOT NULL;

-- User message vs bot message analysis
CREATE INDEX IF NOT EXISTS idx_messages_user_type ON conversation_messages(is_from_user, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_length ON conversation_messages(message_length) WHERE message_length > 0;

-- ============================================================================
-- ADVANCED INDEXES FOR ML/BI QUERIES
-- ============================================================================

-- GIN indexes for JSONB fields (ML feature queries)
CREATE INDEX IF NOT EXISTS idx_user_profiles_interests ON user_profiles USING gin(program_interests);
CREATE INDEX IF NOT EXISTS idx_user_profiles_preferences ON user_profiles USING gin(availability_preferences);

CREATE INDEX IF NOT EXISTS idx_sessions_features ON conversation_sessions USING gin(session_features);
CREATE INDEX IF NOT EXISTS idx_sessions_predictions ON conversation_sessions USING gin(predictions);
CREATE INDEX IF NOT EXISTS idx_sessions_stage_history ON conversation_sessions USING gin(stage_history);

CREATE INDEX IF NOT EXISTS idx_messages_features ON conversation_messages USING gin(features);
CREATE INDEX IF NOT EXISTS idx_messages_entities ON conversation_messages USING gin(entities);

-- Full-text search indexes (Portuguese language)
CREATE INDEX IF NOT EXISTS idx_messages_content_fts ON conversation_messages 
    USING gin(to_tsvector('portuguese', content));
CREATE INDEX IF NOT EXISTS idx_user_profiles_names_fts ON user_profiles 
    USING gin(to_tsvector('portuguese', coalesce(parent_name, '') || ' ' || coalesce(child_name, '')));

-- Partial indexes for specific use cases
CREATE INDEX IF NOT EXISTS idx_sessions_recent_active ON conversation_sessions(last_activity DESC) 
    WHERE status = 'active' AND last_activity > NOW() - INTERVAL '7 days';

CREATE INDEX IF NOT EXISTS idx_messages_recent ON conversation_messages(timestamp DESC) 
    WHERE timestamp > NOW() - INTERVAL '30 days';

-- ============================================================================
-- TRIGGERS FOR DATA CONSISTENCY
-- ============================================================================

-- Update timestamps trigger function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply update triggers
CREATE TRIGGER tr_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_sessions_updated_at
    BEFORE UPDATE ON conversation_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Workflow table triggers
CREATE TRIGGER tr_workflow_checkpoints_updated_at
    BEFORE UPDATE ON workflow_checkpoints
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER tr_workflow_states_updated_at
    BEFORE UPDATE ON workflow_states
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- User profile metrics update trigger
CREATE OR REPLACE FUNCTION update_user_profile_metrics()
RETURNS TRIGGER AS $$
BEGIN
    -- Update user profile aggregated metrics when session changes
    UPDATE user_profiles SET
        total_interactions = (
            SELECT COUNT(*) FROM conversation_sessions 
            WHERE user_id = NEW.user_id
        ),
        total_messages = (
            SELECT COALESCE(SUM(message_count), 0) FROM conversation_sessions 
            WHERE user_id = NEW.user_id
        ),
        avg_session_duration = (
            SELECT COALESCE(AVG(duration_seconds), 0) FROM conversation_sessions 
            WHERE user_id = NEW.user_id AND duration_seconds > 0
        ),
        last_interaction = GREATEST(last_interaction, NEW.last_activity)
    WHERE user_id = NEW.user_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_sessions_update_user_metrics
    AFTER INSERT OR UPDATE ON conversation_sessions
    FOR EACH ROW EXECUTE FUNCTION update_user_profile_metrics();

-- ============================================================================
-- ANALYTICS VIEWS FOR BI DASHBOARDS
-- ============================================================================

-- Daily conversation summary view
CREATE OR REPLACE VIEW v_daily_conversation_summary AS
SELECT 
    date_trunc('day', created_at)::date as date,
    COUNT(*) as total_sessions,
    COUNT(*) FILTER (WHERE status = 'completed') as completed_sessions,
    COUNT(*) FILTER (WHERE status = 'abandoned') as abandoned_sessions,
    COUNT(*) FILTER (WHERE status = 'escalated') as escalated_sessions,
    AVG(duration_seconds) as avg_duration_seconds,
    AVG(message_count) as avg_messages,
    AVG(satisfaction_score) as avg_satisfaction,
    COUNT(*) FILTER (WHERE conversion_events != '[]'::jsonb) as total_conversions,
    AVG(lead_score) as avg_lead_score
FROM conversation_sessions
WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY date_trunc('day', created_at)
ORDER BY date DESC;

-- User engagement analysis view
CREATE OR REPLACE VIEW v_user_engagement_analysis AS
SELECT 
    up.user_id,
    up.phone_number,
    up.parent_name,
    up.child_name,
    up.total_interactions,
    up.total_messages,
    up.avg_session_duration,
    up.engagement_score,
    up.persona_cluster,
    CASE 
        WHEN up.last_interaction > NOW() - INTERVAL '7 days' THEN 'active'
        WHEN up.last_interaction > NOW() - INTERVAL '30 days' THEN 'recent'
        WHEN up.last_interaction > NOW() - INTERVAL '90 days' THEN 'dormant'
        ELSE 'inactive'
    END as activity_status,
    array_length(up.program_interests, 1) as interests_count,
    (SELECT COUNT(*) FROM conversation_sessions cs WHERE cs.user_id = up.user_id AND cs.status = 'completed') as completed_sessions,
    (SELECT MAX(created_at) FROM conversation_sessions cs WHERE cs.user_id = up.user_id) as last_session_date
FROM user_profiles up
ORDER BY up.engagement_score DESC, up.last_interaction DESC;

-- Hourly conversation trends view
CREATE OR REPLACE VIEW v_hourly_conversation_trends AS
SELECT 
    date_trunc('hour', created_at) as hour,
    COUNT(*) as sessions_started,
    COUNT(*) FILTER (WHERE status = 'completed') as sessions_completed,
    AVG(EXTRACT(EPOCH FROM (last_activity - created_at))) as avg_duration_seconds,
    AVG(message_count) as avg_messages
FROM conversation_sessions
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY date_trunc('hour', created_at)
ORDER BY hour DESC;

-- Message intent analysis view
CREATE OR REPLACE VIEW v_message_intent_analysis AS
SELECT 
    intent,
    COUNT(*) as message_count,
    AVG(intent_confidence) as avg_confidence,
    AVG(sentiment_score) as avg_sentiment,
    COUNT(DISTINCT conversation_id) as unique_conversations,
    AVG(message_length) as avg_message_length
FROM conversation_messages
WHERE intent IS NOT NULL 
    AND timestamp >= NOW() - INTERVAL '30 days'
GROUP BY intent
ORDER BY message_count DESC;

-- ============================================================================
-- STORED PROCEDURES FOR ANALYTICS
-- ============================================================================

-- Function to calculate conversion funnel
CREATE OR REPLACE FUNCTION get_conversion_funnel(
    start_date DATE DEFAULT CURRENT_DATE - INTERVAL '30 days',
    end_date DATE DEFAULT CURRENT_DATE
)
RETURNS TABLE (
    stage VARCHAR(30),
    session_count BIGINT,
    conversion_rate DECIMAL(5,4)
) AS $$
BEGIN
    RETURN QUERY
    WITH stage_counts AS (
        SELECT 
            current_stage,
            COUNT(*) as count
        FROM conversation_sessions
        WHERE created_at::date BETWEEN start_date AND end_date
        GROUP BY current_stage
    ),
    total_sessions AS (
        SELECT SUM(count) as total FROM stage_counts
    )
    SELECT 
        sc.current_stage::VARCHAR(30),
        sc.count,
        (sc.count::DECIMAL / ts.total)::DECIMAL(5,4) as rate
    FROM stage_counts sc
    CROSS JOIN total_sessions ts
    ORDER BY 
        CASE sc.current_stage
            WHEN 'greeting' THEN 1
            WHEN 'qualification' THEN 2
            WHEN 'information_gathering' THEN 3
            WHEN 'scheduling' THEN 4
            WHEN 'confirmation' THEN 5
            WHEN 'completed' THEN 6
            ELSE 7
        END;
END;
$$ LANGUAGE plpgsql;

-- Function to get user cohort analysis
CREATE OR REPLACE FUNCTION get_user_cohort_analysis(
    cohort_period VARCHAR(10) DEFAULT 'month' -- 'week' or 'month'
)
RETURNS TABLE (
    cohort_period_value TEXT,
    users_acquired BIGINT,
    retained_1_period BIGINT,
    retained_2_period BIGINT,
    retained_3_period BIGINT,
    retention_rate_1 DECIMAL(5,4),
    retention_rate_2 DECIMAL(5,4),
    retention_rate_3 DECIMAL(5,4)
) AS $$
BEGIN
    -- Implementation would depend on specific retention definition
    -- This is a placeholder for the actual cohort analysis logic
    RETURN QUERY
    SELECT 
        'placeholder'::TEXT,
        0::BIGINT, 0::BIGINT, 0::BIGINT, 0::BIGINT,
        0::DECIMAL(5,4), 0::DECIMAL(5,4), 0::DECIMAL(5,4)
    LIMIT 0; -- Return empty result for now
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- DATA QUALITY AND MONITORING
-- ============================================================================

-- Data quality check function
CREATE OR REPLACE FUNCTION check_data_quality()
RETURNS TABLE (
    check_name TEXT,
    status TEXT,
    details TEXT
) AS $$
BEGIN
    -- Check for orphaned sessions
    RETURN QUERY
    SELECT 
        'orphaned_sessions'::TEXT,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END::TEXT,
        COUNT(*)::TEXT || ' sessions without valid user profiles'
    FROM conversation_sessions cs
    LEFT JOIN user_profiles up ON cs.user_id = up.user_id
    WHERE up.user_id IS NULL;

    -- Check for sessions without messages
    RETURN QUERY
    SELECT 
        'sessions_without_messages'::TEXT,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'WARN' END::TEXT,
        COUNT(*)::TEXT || ' sessions have no messages'
    FROM conversation_sessions cs
    LEFT JOIN conversation_messages cm ON cs.session_id = cm.conversation_id
    WHERE cm.conversation_id IS NULL
    AND cs.created_at > NOW() - INTERVAL '1 day';

    -- Check message count consistency
    RETURN QUERY
    SELECT 
        'message_count_consistency'::TEXT,
        CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END::TEXT,
        COUNT(*)::TEXT || ' sessions have inconsistent message counts'
    FROM conversation_sessions cs
    LEFT JOIN (
        SELECT conversation_id, COUNT(*) as actual_count
        FROM conversation_messages
        GROUP BY conversation_id
    ) mc ON cs.session_id = mc.conversation_id
    WHERE cs.message_count != COALESCE(mc.actual_count, 0);
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- INITIAL DATA AND CONFIGURATION
-- ============================================================================

-- Insert system user for auditing
INSERT INTO user_profiles (
    user_id, phone_number, parent_name, created_at, updated_at, last_interaction
) VALUES (
    'system_user', 'system', 'System User', NOW(), NOW(), NOW()
) ON CONFLICT (user_id) DO NOTHING;

-- Create scheduled job for daily metrics aggregation (if pg_cron is available)
-- SELECT cron.schedule('daily-metrics', '0 1 * * *', 'CALL aggregate_daily_metrics();');

-- Log initialization completion
DO $$
BEGIN
    RAISE NOTICE 'Kumon Conversation Analytics database initialized successfully at %', NOW();
    RAISE NOTICE 'Schema version: 1.0';
    RAISE NOTICE 'Tables created: user_profiles, conversation_sessions, conversation_messages, daily_conversation_metrics, hourly_conversation_metrics';
    RAISE NOTICE 'Views created: v_daily_conversation_summary, v_user_engagement_analysis, v_hourly_conversation_trends, v_message_intent_analysis';
    RAISE NOTICE 'Functions created: get_conversion_funnel, get_user_cohort_analysis, check_data_quality';
END $$;