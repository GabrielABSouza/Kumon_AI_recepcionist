-- ============================================================================
-- KUMON ASSISTANT - BUSINESS DATABASE SCHEMA
-- Captures and organizes customer data from WhatsApp interactions
-- ============================================================================

-- ============================================================================
-- LEADS TABLE - Potential customers identified from conversations
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    whatsapp_number VARCHAR(20) NOT NULL UNIQUE,
    contact_name VARCHAR(255),
    first_message_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    lead_source VARCHAR(50) DEFAULT 'whatsapp',
    lead_status VARCHAR(50) DEFAULT 'new', -- new, contacted, qualified, converted, lost
    interest_level VARCHAR(20) DEFAULT 'unknown', -- high, medium, low, unknown
    interested_subjects TEXT[], -- array of subjects: math, reading, both
    student_age INTEGER,
    student_grade VARCHAR(20),
    parent_contact_preference VARCHAR(50), -- whatsapp, phone, email
    notes TEXT,
    last_ai_analysis TIMESTAMP,
    conversion_probability DECIMAL(3,2), -- 0.00 to 1.00 probability score
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- APPOINTMENTS TABLE - Scheduled meetings and evaluations
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES public.leads(id) ON DELETE CASCADE,
    appointment_type VARCHAR(50) NOT NULL, -- evaluation, trial_class, enrollment, meeting
    appointment_date TIMESTAMP NOT NULL,
    appointment_duration INTEGER DEFAULT 60, -- minutes
    appointment_status VARCHAR(30) DEFAULT 'scheduled', -- scheduled, confirmed, completed, cancelled, no_show
    appointment_location VARCHAR(100) DEFAULT 'Kumon Vila A',
    appointment_notes TEXT,
    reminder_sent BOOLEAN DEFAULT FALSE,
    reminder_date TIMESTAMP,
    whatsapp_message_id VARCHAR(255), -- Link to Evolution API message
    created_by VARCHAR(50) DEFAULT 'ai_assistant',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- STUDENTS TABLE - Enrolled students
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.students (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES public.leads(id),
    student_name VARCHAR(255) NOT NULL,
    student_age INTEGER,
    student_grade VARCHAR(20),
    parent_name VARCHAR(255),
    parent_whatsapp VARCHAR(20),
    parent_email VARCHAR(255),
    enrollment_date DATE,
    subjects_enrolled TEXT[], -- math, reading, both
    current_level_math VARCHAR(20),
    current_level_reading VARCHAR(20),
    monthly_fee DECIMAL(10,2),
    payment_status VARCHAR(30) DEFAULT 'pending', -- pending, paid, overdue
    last_payment_date DATE,
    next_payment_due DATE,
    student_status VARCHAR(30) DEFAULT 'active', -- active, inactive, graduated, dropped
    emergency_contact VARCHAR(255),
    medical_notes TEXT,
    academic_goals TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- CONVERSATION ANALYSIS TABLE - AI insights from WhatsApp conversations
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.conversation_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES public.leads(id) ON DELETE CASCADE,
    whatsapp_message_id VARCHAR(255), -- Reference to Evolution API Message
    analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_sentiment VARCHAR(20), -- positive, negative, neutral
    extracted_intents TEXT[], -- schedule_visit, ask_price, ask_methodology, etc.
    mentioned_subjects TEXT[], -- math, reading
    mentioned_age INTEGER,
    mentioned_grade VARCHAR(20),
    urgency_level VARCHAR(20) DEFAULT 'normal', -- high, normal, low
    requires_human_attention BOOLEAN DEFAULT FALSE,
    confidence_score DECIMAL(3,2), -- AI confidence in analysis
    key_phrases TEXT[], -- Important phrases extracted
    next_recommended_action VARCHAR(255),
    ai_model_used VARCHAR(50) DEFAULT 'gpt-4o-mini',
    raw_analysis JSONB, -- Full AI response for debugging
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- BUSINESS METRICS TABLE - Track performance and KPIs
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.business_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date DATE DEFAULT CURRENT_DATE,
    metric_type VARCHAR(50) NOT NULL, -- daily_leads, conversion_rate, appointments_scheduled, etc.
    metric_value DECIMAL(10,2) NOT NULL,
    metric_details JSONB, -- Additional context
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- AUTOMATED RESPONSES TABLE - Track AI responses sent
-- ============================================================================
CREATE TABLE IF NOT EXISTS public.automated_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES public.leads(id) ON DELETE CASCADE,
    whatsapp_message_id VARCHAR(255), -- Triggering message
    response_type VARCHAR(50), -- welcome, faq_answer, appointment_confirmation, etc.
    response_content TEXT NOT NULL,
    response_sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    response_status VARCHAR(30) DEFAULT 'sent', -- sent, failed, queued
    ai_confidence DECIMAL(3,2),
    human_approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- INDEXES for better performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_leads_whatsapp_number ON public.leads(whatsapp_number);
CREATE INDEX IF NOT EXISTS idx_leads_last_interaction ON public.leads(last_interaction DESC);
CREATE INDEX IF NOT EXISTS idx_leads_status ON public.leads(lead_status);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON public.appointments(appointment_date);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON public.appointments(appointment_status);
CREATE INDEX IF NOT EXISTS idx_students_parent_whatsapp ON public.students(parent_whatsapp);
CREATE INDEX IF NOT EXISTS idx_conversation_analysis_lead_id ON public.conversation_analysis(lead_id);
CREATE INDEX IF NOT EXISTS idx_conversation_analysis_date ON public.conversation_analysis(analysis_date DESC);

-- ============================================================================
-- TRIGGERS for updated_at timestamps
-- ============================================================================
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_leads_updated_at BEFORE UPDATE ON public.leads 
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_appointments_updated_at BEFORE UPDATE ON public.appointments 
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_students_updated_at BEFORE UPDATE ON public.students 
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================================
-- INITIAL DATA - Insert business configuration
-- ============================================================================

-- Insert business metrics tracking
INSERT INTO public.business_metrics (metric_type, metric_value, metric_details) VALUES
('total_leads', 0, '{"description": "Total leads captured"}'),
('monthly_enrollments', 0, '{"description": "Students enrolled this month"}'),
('conversion_rate', 0.0, '{"description": "Lead to enrollment conversion rate"}')
ON CONFLICT DO NOTHING;

-- Create a sample lead for testing
INSERT INTO public.leads (
    whatsapp_number, 
    contact_name, 
    lead_status, 
    interest_level, 
    notes
) VALUES (
    '5551999999999', 
    'Test User', 
    'new', 
    'high', 
    'Sample lead for system testing'
) ON CONFLICT (whatsapp_number) DO NOTHING;

SELECT 'Kumon Business Schema created successfully!' as result; 