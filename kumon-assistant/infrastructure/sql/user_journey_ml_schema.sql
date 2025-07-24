-- ============================================================================
-- USER JOURNEY & ML ANALYTICS SCHEMA
-- Captures complete user interaction data for ML analysis and conversion prediction
-- ============================================================================

-- ============================================================================
-- USER SESSIONS - Complete conversation sessions with outcome tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) UNIQUE NOT NULL, -- Derived from phone + timestamp
    whatsapp_number VARCHAR(20) NOT NULL,
    contact_name VARCHAR(255),
    
    -- SESSION TIMELINE
    session_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    session_end TIMESTAMP,
    session_duration_minutes INTEGER, -- Calculated field
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- SESSION OUTCOME (TARGET VARIABLE FOR ML)
    session_outcome VARCHAR(50) DEFAULT 'ongoing', -- ongoing, appointment_scheduled, abandoned, converted_direct, information_only
    conversion_achieved BOOLEAN DEFAULT FALSE, -- Main ML target
    abandonment_stage VARCHAR(50), -- welcome, information, pricing, scheduling, other
    abandonment_reason VARCHAR(100), -- timeout, no_response, pricing_concern, scheduling_conflict, other
    
    -- BEHAVIORAL FEATURES (for ML)
    total_messages_sent INTEGER DEFAULT 0,
    total_messages_received INTEGER DEFAULT 0,
    avg_response_time_seconds DECIMAL(10,2),
    max_response_time_seconds INTEGER,
    total_session_pauses INTEGER DEFAULT 0, -- Long gaps in conversation
    user_initiated_topics INTEGER DEFAULT 0, -- How many topics user brought up
    
    -- ENGAGEMENT FEATURES
    engagement_score DECIMAL(3,2), -- 0.00 to 1.00 calculated engagement
    question_asking_frequency DECIMAL(3,2), -- Questions per message ratio
    message_length_avg DECIMAL(5,2), -- Average message length
    emoji_usage_count INTEGER DEFAULT 0,
    politeness_indicators INTEGER DEFAULT 0, -- "por favor", "obrigado", etc.
    urgency_indicators INTEGER DEFAULT 0, -- "urgente", "rápido", "hoje", etc.
    
    -- DEMOGRAPHIC FEATURES (extracted from conversation)
    mentioned_student_age INTEGER,
    mentioned_student_grade VARCHAR(20),
    mentioned_subjects TEXT[], -- math, reading, both
    location_mentioned VARCHAR(100),
    income_bracket VARCHAR(20), -- high, medium, low (inferred from conversation)
    
    -- TEMPORAL FEATURES
    start_hour INTEGER, -- 0-23
    start_day_of_week INTEGER, -- 0-6 (Sunday=0)
    start_month INTEGER, -- 1-12
    is_weekend BOOLEAN DEFAULT FALSE,
    is_business_hours BOOLEAN DEFAULT TRUE,
    
    -- SENTIMENT & LANGUAGE FEATURES
    overall_sentiment VARCHAR(20) DEFAULT 'neutral', -- positive, negative, neutral
    sentiment_progression JSONB, -- Array of sentiment scores over time
    dominant_emotions TEXT[], -- curiosity, concern, excitement, frustration
    language_complexity_score DECIMAL(3,2), -- Reading level of user messages
    technical_questions_count INTEGER DEFAULT 0,
    
    -- INTERACTION PATTERNS
    interaction_pattern VARCHAR(50), -- quick_decider, researcher, hesitant, comparison_shopper
    information_seeking_intensity VARCHAR(20), -- high, medium, low
    price_sensitivity_level VARCHAR(20), -- high, medium, low, unknown
    decision_timeline VARCHAR(50), -- immediate, this_week, this_month, exploring
    
    -- TOUCHPOINTS BEFORE SESSION
    referral_source VARCHAR(100), -- google_search, friend_referral, social_media, walk_in, other
    prior_brand_familiarity VARCHAR(20), -- high, medium, low, none
    competitor_mentions INTEGER DEFAULT 0,
    
    -- ML PREDICTION SCORES (updated by ML models)
    conversion_probability DECIMAL(3,2), -- Model prediction 0.00-1.00
    predicted_conversion_timeline VARCHAR(50), -- immediate, 1_week, 1_month, unlikely
    recommended_intervention VARCHAR(100), -- follow_up_call, discount_offer, success_stories, etc.
    churn_risk_score DECIMAL(3,2), -- 0.00-1.00 risk of abandoning
    
    -- METADATA
    user_agent VARCHAR(255), -- WhatsApp client info if available
    message_platform VARCHAR(50) DEFAULT 'whatsapp',
    is_returning_user BOOLEAN DEFAULT FALSE,
    previous_session_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- USER BEHAVIOR EVENTS - Granular event tracking within sessions
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.user_behavior_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES public.user_sessions(id) ON DELETE CASCADE,
    whatsapp_message_id VARCHAR(255), -- Link to Evolution API message
    
    -- EVENT DETAILS
    event_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(50) NOT NULL, -- message_sent, message_received, pause_start, pause_end, topic_change, intent_detected
    event_sequence INTEGER, -- Order within session
    
    -- MESSAGE ANALYSIS (for message events)
    message_content TEXT,
    message_length INTEGER,
    message_type VARCHAR(30), -- text, image, audio, document
    detected_intent VARCHAR(100), -- ask_price, schedule_visit, ask_methodology, etc.
    intent_confidence DECIMAL(3,2),
    sentiment_score DECIMAL(3,2), -- -1.00 to 1.00
    
    -- BEHAVIORAL SIGNALS
    response_time_seconds INTEGER, -- Time to respond to bot
    typing_indicators INTEGER DEFAULT 0, -- How many times user started typing
    message_edit_count INTEGER DEFAULT 0, -- If user corrected themselves
    
    -- CONTENT ANALYSIS
    keywords_extracted TEXT[],
    entities_mentioned JSONB, -- {"person": ["Maria"], "age": [8], "subject": ["math"]}
    questions_asked TEXT[], -- Actual questions user asked
    concerns_expressed TEXT[], -- Worries or objections
    positive_signals TEXT[], -- Interest indicators
    
    -- CONTEXT
    previous_bot_message TEXT, -- What bot said that triggered this
    user_satisfaction_implied VARCHAR(20), -- satisfied, neutral, frustrated
    escalation_requested BOOLEAN DEFAULT FALSE, -- Asked for human help
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- CONVERSION FUNNEL STAGES - Track progression through sales funnel
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.conversion_funnel_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES public.user_sessions(id) ON DELETE CASCADE,
    
    -- FUNNEL STAGE PROGRESSION
    stage_name VARCHAR(50) NOT NULL, -- awareness, interest, consideration, intent, evaluation, purchase
    stage_entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    stage_duration_minutes INTEGER,
    stage_completed BOOLEAN DEFAULT FALSE,
    next_stage_reached BOOLEAN DEFAULT FALSE,
    
    -- STAGE-SPECIFIC METRICS
    stage_engagement_score DECIMAL(3,2),
    objections_raised INTEGER DEFAULT 0,
    questions_answered INTEGER DEFAULT 0,
    information_provided TEXT[], -- What info was shared at this stage
    
    -- ABANDONMENT ANALYSIS
    abandoned_at_stage BOOLEAN DEFAULT FALSE,
    abandonment_signals TEXT[], -- What indicated user might leave
    recovery_attempts INTEGER DEFAULT 0, -- How many times bot tried to re-engage
    recovery_successful BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- A/B TEST TRACKING - Test different approaches and measure impact
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.ab_test_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES public.user_sessions(id) ON DELETE CASCADE,
    
    test_name VARCHAR(100) NOT NULL, -- welcome_message_v2, pricing_reveal_timing, etc.
    test_variant VARCHAR(50) NOT NULL, -- control, variant_a, variant_b
    assignment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- TEST RESULTS
    primary_metric_value DECIMAL(10,4), -- Main KPI (conversion rate, engagement, etc.)
    secondary_metrics JSONB, -- Additional metrics
    test_completed BOOLEAN DEFAULT FALSE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- PREDICTIVE FEATURES VIEW - Pre-calculated features for ML models
-- ============================================================================
CREATE OR REPLACE VIEW public.ml_features_view AS
SELECT 
    us.id as session_id,
    us.whatsapp_number,
    us.conversion_achieved,
    
    -- TEMPORAL FEATURES
    us.start_hour,
    us.start_day_of_week,
    us.is_weekend,
    us.is_business_hours,
    
    -- BEHAVIORAL FEATURES  
    us.session_duration_minutes,
    us.total_messages_sent,
    us.total_messages_received,
    us.avg_response_time_seconds,
    us.engagement_score,
    us.question_asking_frequency,
    us.message_length_avg,
    
    -- DEMOGRAPHIC FEATURES
    us.mentioned_student_age,
    CASE WHEN us.mentioned_student_grade IS NOT NULL THEN 1 ELSE 0 END as has_grade_info,
    array_length(us.mentioned_subjects, 1) as subjects_mentioned_count,
    
    -- SENTIMENT FEATURES
    us.overall_sentiment,
    us.language_complexity_score,
    us.technical_questions_count,
    
    -- INTERACTION FEATURES
    us.information_seeking_intensity,
    us.price_sensitivity_level,
    us.competitor_mentions,
    us.is_returning_user,
    
    -- DERIVED FEATURES
    CASE WHEN us.session_duration_minutes > 30 THEN 1 ELSE 0 END as long_session,
    CASE WHEN us.total_messages_sent > 10 THEN 1 ELSE 0 END as high_engagement,
    us.total_messages_sent::DECIMAL / NULLIF(us.session_duration_minutes, 0) as messages_per_minute,
    
    -- AGGREGATED EVENT FEATURES
    COUNT(ube.id) FILTER (WHERE ube.event_type = 'message_sent') as user_messages_count,
    AVG(ube.sentiment_score) as avg_sentiment_score,
    COUNT(ube.id) FILTER (WHERE ube.escalation_requested = TRUE) as escalation_requests,
    
    us.created_at
FROM public.user_sessions us
LEFT JOIN public.user_behavior_events ube ON us.id = ube.session_id
GROUP BY us.id, us.whatsapp_number, us.conversion_achieved, us.start_hour, 
         us.start_day_of_week, us.is_weekend, us.is_business_hours,
         us.session_duration_minutes, us.total_messages_sent, us.total_messages_received,
         us.avg_response_time_seconds, us.engagement_score, us.question_asking_frequency,
         us.message_length_avg, us.mentioned_student_age, us.mentioned_student_grade,
         us.mentioned_subjects, us.overall_sentiment, us.language_complexity_score,
         us.technical_questions_count, us.information_seeking_intensity,
         us.price_sensitivity_level, us.competitor_mentions, us.is_returning_user,
         us.created_at;

-- ============================================================================
-- INDEXES for ML and Analytics Performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_user_sessions_outcome ON public.user_sessions(session_outcome);
CREATE INDEX IF NOT EXISTS idx_user_sessions_conversion ON public.user_sessions(conversion_achieved);
CREATE INDEX IF NOT EXISTS idx_user_sessions_start_time ON public.user_sessions(session_start);
CREATE INDEX IF NOT EXISTS idx_user_sessions_whatsapp ON public.user_sessions(whatsapp_number);
CREATE INDEX IF NOT EXISTS idx_user_sessions_abandonment_stage ON public.user_sessions(abandonment_stage);

CREATE INDEX IF NOT EXISTS idx_behavior_events_session ON public.user_behavior_events(session_id);
CREATE INDEX IF NOT EXISTS idx_behavior_events_timestamp ON public.user_behavior_events(event_timestamp);
CREATE INDEX IF NOT EXISTS idx_behavior_events_type ON public.user_behavior_events(event_type);
CREATE INDEX IF NOT EXISTS idx_behavior_events_intent ON public.user_behavior_events(detected_intent);

CREATE INDEX IF NOT EXISTS idx_funnel_tracking_session ON public.conversion_funnel_tracking(session_id);
CREATE INDEX IF NOT EXISTS idx_funnel_tracking_stage ON public.conversion_funnel_tracking(stage_name);

-- ============================================================================
-- TRIGGERS for automatic calculations
-- ============================================================================
CREATE OR REPLACE FUNCTION public.update_session_metrics()
RETURNS TRIGGER AS $$
BEGIN
    -- Update session duration when session ends
    IF NEW.session_end IS NOT NULL AND OLD.session_end IS NULL THEN
        NEW.session_duration_minutes = EXTRACT(EPOCH FROM (NEW.session_end - NEW.session_start)) / 60;
    END IF;
    
    -- Update temporal features
    NEW.start_hour = EXTRACT(HOUR FROM NEW.session_start);
    NEW.start_day_of_week = EXTRACT(DOW FROM NEW.session_start);
    NEW.start_month = EXTRACT(MONTH FROM NEW.session_start);
    NEW.is_weekend = EXTRACT(DOW FROM NEW.session_start) IN (0, 6);
    NEW.is_business_hours = NEW.start_hour BETWEEN 8 AND 18 AND NOT NEW.is_weekend;
    
    -- Update timestamp
    NEW.updated_at = CURRENT_TIMESTAMP;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_sessions_metrics 
    BEFORE UPDATE ON public.user_sessions 
    FOR EACH ROW EXECUTE FUNCTION public.update_session_metrics();

-- ============================================================================
-- SAMPLE DATA for testing ML pipeline
-- ============================================================================
INSERT INTO public.user_sessions (
    session_id, whatsapp_number, contact_name, session_outcome, conversion_achieved,
    total_messages_sent, total_messages_received, avg_response_time_seconds,
    engagement_score, mentioned_student_age, overall_sentiment, start_hour, is_weekend
) VALUES 
('test_session_1', '5511999999991', 'Ana Silva', 'appointment_scheduled', TRUE, 15, 12, 45.5, 0.85, 8, 'positive', 14, FALSE),
('test_session_2', '5511999999992', 'Carlos Lima', 'abandoned', FALSE, 5, 4, 120.0, 0.35, NULL, 'neutral', 10, FALSE),
('test_session_3', '5511999999993', 'Maria Santos', 'information_only', FALSE, 8, 7, 30.2, 0.60, 12, 'positive', 16, TRUE)
ON CONFLICT (session_id) DO NOTHING;

SELECT 'User Journey ML Schema created successfully!' as result; 