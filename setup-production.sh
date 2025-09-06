#!/bin/bash
# Production Environment Setup Script - Wave 4.3 Step 2

set -e

echo "🔧 KUMON ASSISTANT - PRODUCTION ENVIRONMENT SETUP"
echo "================================================"

# Check Railway CLI
if ! command -v railway &> /dev/null; then
    echo "📦 Installing Railway CLI..."
    npm install -g @railway/cli
fi

echo "🔐 Login to Railway..."
railway login

echo "📋 Creating new Railway project..."
railway new kumon-assistant-production

echo "🗄️ Adding PostgreSQL service..."
railway add postgresql

echo "🗂️ Adding Redis service..."  
railway add redis

echo "🔧 Setting up environment variables..."

# Core application settings
railway variables set ENVIRONMENT=production
railway variables set DEBUG=false
railway variables set LOG_LEVEL=warning
railway variables set RAILWAY_ENVIRONMENT=production

# Performance and concurrency
railway variables set WEB_CONCURRENCY=2
railway variables set WORKER_CONNECTIONS=1000
railway variables set PORT=8000

# Business Configuration - EXACT COMPLIANCE
railway variables set BUSINESS_NAME="Kumon Vila A"
railway variables set BUSINESS_PHONE="51996921999"
railway variables set BUSINESS_EMAIL="kumonvilaa@gmail.com"
railway variables set BUSINESS_ADDRESS="Rua Amoreira, 571. Salas 6 e 7. Jardim das Laranjeiras"

# Business Hours (8h-12h, 14h-18h)
railway variables set BUSINESS_HOURS_START=8
railway variables set BUSINESS_HOURS_END_MORNING=12
railway variables set BUSINESS_HOURS_START_AFTERNOON=14
railway variables set BUSINESS_HOURS_END=18
railway variables set BUSINESS_TIMEZONE="America/Sao_Paulo"

# Pricing - EXACT VALUES
railway variables set PRICE_PER_SUBJECT=375.00
railway variables set ENROLLMENT_FEE=100.00
railway variables set CURRENCY=BRL

# Rate Limiting - EXACT COMPLIANCE (50 req/min)
railway variables set RATE_LIMIT_PER_MINUTE=50
railway variables set RATE_LIMIT_PER_HOUR=1000

# Performance Targets
railway variables set RESPONSE_TIME_TARGET=5.0
railway variables set RESPONSE_TIME_WARNING=4.0

# OpenAI Configuration - COST MONITORING
railway variables set OPENAI_MODEL="gpt-3.5-turbo"
railway variables set OPENAI_MAX_TOKENS=150
railway variables set OPENAI_TEMPERATURE=0.7
railway variables set LLM_DAILY_BUDGET_BRL=5.00
railway variables set OPENAI_COST_LIMIT_DAILY=4.0

# Performance and Cost Monitoring
railway variables set ENABLE_MONITORING=true
railway variables set ENABLE_COST_ALERTS=true
railway variables set ENABLE_PERFORMANCE_ALERTS=true
railway variables set COST_ALERT_THRESHOLD=4.0
railway variables set ERROR_RATE_THRESHOLD=0.01
railway variables set RESPONSE_TIME_THRESHOLD=5.0

# Security Configuration
railway variables set USE_SECURE_PROCESSING=true
railway variables set SECURITY_MONITORING_ENABLED=true
railway variables set ENABLE_DDOS_PROTECTION=true
railway variables set ENABLE_PROMPT_INJECTION_DEFENSE=true
railway variables set ENABLE_SCOPE_VALIDATION=true
railway variables set ENABLE_INFORMATION_PROTECTION=true
railway variables set ENABLE_ADVANCED_THREAT_DETECTION=true

# Feature Flags
railway variables set USE_ENHANCED_CACHE=true
railway variables set USE_LANGGRAPH_WORKFLOW=true
railway variables set STREAMING_FALLBACK_ENABLED=true
railway variables set VALIDATE_API_KEYS=true
railway variables set ENABLE_HEALTH_CHECKS=true
railway variables set REQUIRE_HTTPS=true
railway variables set ENABLE_LGPD_COMPLIANCE=true

# Logging Configuration
railway variables set LOG_FORMAT=json
railway variables set LOG_LEVEL=warning

echo "⚠️  MANUAL CONFIGURATION REQUIRED:"
echo "=================================="
echo "1. Set OPENAI_API_KEY in Railway dashboard"
echo "2. Set EVOLUTION_API_KEY in Railway dashboard"  
echo "3. Set SECRET_KEY (generate with: openssl rand -hex 32)"
echo "4. Set JWT_SECRET_KEY (generate with: openssl rand -hex 32)"
echo "5. Configure Evolution API webhook URL after deployment"
echo ""
echo "🔗 Railway Dashboard: https://railway.app/dashboard"
echo ""
echo "✅ Production environment configured!"
echo "📋 Next step: Run ./railway-deploy.sh to deploy"