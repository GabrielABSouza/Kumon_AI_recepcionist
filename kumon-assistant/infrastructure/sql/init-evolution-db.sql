-- ============================================================================
-- EVOLUTION API - DATABASE INITIALIZATION SCRIPT
-- Creates required tables for Evolution API functionality
-- ============================================================================

-- Create Instance table
CREATE TABLE IF NOT EXISTS public."Instance" (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    qrcode BOOLEAN DEFAULT true,
    status TEXT DEFAULT 'disconnected',
    server_url TEXT,
    api_key TEXT,
    integration TEXT DEFAULT 'WHATSAPP-BAILEYS',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Message table
CREATE TABLE IF NOT EXISTS public."Message" (
    id TEXT PRIMARY KEY,
    key_remote_jid TEXT,
    key_from_me BOOLEAN DEFAULT false,
    key_id TEXT,
    pushname TEXT,
    message_type TEXT,
    message TEXT,
    instance_id TEXT REFERENCES public."Instance"(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Contact table
CREATE TABLE IF NOT EXISTS public."Contact" (
    id TEXT PRIMARY KEY,
    pushname TEXT,
    profile_pic_url TEXT,
    instance_id TEXT REFERENCES public."Instance"(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Chat table
CREATE TABLE IF NOT EXISTS public."Chat" (
    id TEXT PRIMARY KEY,
    remote_jid TEXT,
    name TEXT,
    instance_id TEXT REFERENCES public."Instance"(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_message_instance_id ON public."Message" (instance_id);
CREATE INDEX IF NOT EXISTS idx_contact_instance_id ON public."Contact" (instance_id);
CREATE INDEX IF NOT EXISTS idx_chat_instance_id ON public."Chat" (instance_id);
CREATE INDEX IF NOT EXISTS idx_message_key_remote_jid ON public."Message" (key_remote_jid);

-- Grant permissions to evolution_user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO evolution_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO evolution_user;

-- Insert a test record to verify functionality
INSERT INTO public."Instance" (id, name, qrcode, status, integration) 
VALUES ('test-init', 'initialization-test', true, 'disconnected', 'WHATSAPP-BAILEYS') 
ON CONFLICT (name) DO NOTHING;

SELECT 'Evolution API database initialized successfully!' as result; 