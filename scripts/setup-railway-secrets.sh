#!/bin/bash
# Kumon Assistant - Railway Secrets Setup
# Usage: ./scripts/setup-railway-secrets.sh
# Description: Automated setup of Railway secrets for production deployment

set -e

echo "🔐 Setting up Railway secrets for Kumon Assistant..."
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${YELLOW}⚠️ Railway CLI not found. Installing...${NC}"
    if command -v npm &> /dev/null; then
        npm install -g @railway/cli
    elif command -v curl &> /dev/null; then
        curl -fsSL https://railway.app/install.sh | sh
    else
        echo -e "${RED}❌ Cannot install Railway CLI. Please install npm or curl first.${NC}"
        exit 1
    fi
fi

# Login to Railway
echo -e "${BLUE}🔑 Please login to Railway...${NC}"
railway login

# Select project
echo -e "${BLUE}📋 Selecting Railway project...${NC}"
railway environment

# Generate secure JWT secrets
echo -e "${BLUE}🎲 Generating JWT secrets...${NC}"
JWT_SECRET=$(openssl rand -hex 32)
SECRET_KEY=$(openssl rand -hex 32)

# Set core application secrets
echo -e "${BLUE}⚙️ Setting core application secrets...${NC}"
railway variables set JWT_SECRET_KEY="$JWT_SECRET"
railway variables set SECRET_KEY="$SECRET_KEY"
railway variables set ENVIRONMENT="production"
railway variables set DEBUG="false"
railway variables set VALIDATE_API_KEYS="true"
railway variables set REQUIRE_HTTPS="true"
railway variables set ENABLE_HEALTH_CHECKS="true"

# Interactive setup for API keys
echo -e "${YELLOW}🔧 Setting up API keys...${NC}"
echo "Please enter your OpenAI API key (starts with sk-):"
read -s OPENAI_KEY
if [[ ! $OPENAI_KEY =~ ^sk- ]]; then
    echo -e "${RED}❌ Invalid OpenAI API key format${NC}"
    exit 1
fi
railway variables set OPENAI_API_KEY="$OPENAI_KEY"

echo "Enter your Evolution API key:"
read -s EVOLUTION_KEY
railway variables set EVOLUTION_API_KEY="$EVOLUTION_KEY"

echo "Enter your Evolution API URL (e.g., https://your-evolution-api.com):"
read EVOLUTION_URL
railway variables set EVOLUTION_API_URL="${EVOLUTION_URL:-https://your-evolution-api.com}"

# Optional secrets with validation
echo -e "${YELLOW}📋 Setting up optional secrets...${NC}"
echo "Enter your LangSmith API key (optional, press Enter to skip):"
read -s LANGSMITH_KEY
if [ ! -z "$LANGSMITH_KEY" ]; then
    railway variables set LANGSMITH_API_KEY="$LANGSMITH_KEY"
    railway variables set LANGSMITH_PROJECT="kumon-assistant"
    railway variables set LANGCHAIN_TRACING_V2="true"
fi

echo "Enter your Anthropic API key (optional fallback, press Enter to skip):"
read -s ANTHROPIC_KEY
if [ ! -z "$ANTHROPIC_KEY" ]; then
    railway variables set ANTHROPIC_API_KEY="$ANTHROPIC_KEY"
fi

# Database URLs (Railway provides these automatically)
echo -e "${BLUE}🗄️ Database URLs will be set automatically by Railway services${NC}"

# Business configuration
echo -e "${BLUE}📋 Setting business configuration...${NC}"
railway variables set BUSINESS_PHONE="51996921999"
railway variables set BUSINESS_EMAIL="kumonvilaa@gmail.com"
railway variables set BUSINESS_NAME="Kumon Vila A"

# Performance and reliability settings
echo -e "${BLUE}⚡ Setting performance configuration...${NC}"
railway variables set LLM_DAILY_BUDGET_BRL="5.00"
railway variables set LLM_COST_ALERT_THRESHOLD_BRL="4.00"
railway variables set LLM_REQUEST_TIMEOUT_SECONDS="30"
railway variables set WEB_CONCURRENCY="2"

# Security settings
echo -e "${BLUE}🛡️ Setting security configuration...${NC}"
railway variables set USE_SECURE_PROCESSING="true"
railway variables set SECURITY_LOGGING_ENABLED="true"
railway variables set ENABLE_PROMPT_INJECTION_DEFENSE="true"
railway variables set ENABLE_DDOS_PROTECTION="true"

# Memory and cache settings
echo -e "${BLUE}💾 Setting memory and cache configuration...${NC}"
railway variables set MAX_ACTIVE_CONVERSATIONS="500"
railway variables set CONVERSATION_TIMEOUT_HOURS="12"
railway variables set EMBEDDING_CACHE_SIZE_MB="50"

echo -e "${GREEN}✅ Railway secrets setup complete!${NC}"
echo ""
echo -e "${BLUE}📝 Next steps:${NC}"
echo "1. Deploy your application: railway up"
echo "2. Check deployment: railway logs"
echo "3. Test health: curl https://your-app.railway.app/api/v1/health"
echo ""
echo -e "${YELLOW}📊 Configuration Summary:${NC}"
echo "• Core secrets: JWT, OpenAI, Evolution API configured"
echo "• Environment: Production with security enabled"
echo "• Business: Kumon Vila A contact details set"
echo "• Performance: 2 workers, R$5/day OpenAI budget"
echo "• Security: All protection mechanisms enabled"
echo ""
echo -e "${GREEN}🚀 Ready for production deployment!${NC}"