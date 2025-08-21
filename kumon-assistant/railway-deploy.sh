#!/bin/bash
# Railway Production Deployment Script - Wave 4.3 Step 2

set -e

echo "🚀 KUMON ASSISTANT - RAILWAY PRODUCTION DEPLOYMENT"
echo "=================================================="

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "📦 Installing Railway CLI..."
    npm install -g @railway/cli
fi

# Check if logged in
echo "🔐 Checking Railway authentication..."
if ! railway whoami &> /dev/null; then
    echo "Please login to Railway first:"
    echo "railway login"
    exit 1
fi

echo "✅ Railway CLI ready"

# Deploy application
echo "🚀 Deploying to Railway..."

# Use the production Dockerfile
echo "📋 Using production Dockerfile..."
cp Dockerfile.production Dockerfile

# Set environment for deployment
export RAILWAY_ENVIRONMENT=production

# Deploy with Railway
echo "🔧 Starting Railway deployment..."
railway up --service kumon-assistant

echo "📊 Checking deployment status..."
railway status

echo "🎯 DEPLOYMENT VALIDATION"
echo "======================="

# Get the public URL
PUBLIC_URL=$(railway domain)
if [ -z "$PUBLIC_URL" ]; then
    echo "⚠️  Getting Railway public URL..."
    railway domain
    PUBLIC_URL=$(railway domain)
fi

echo "🌐 Application URL: $PUBLIC_URL"

# Test health endpoints
echo "🏥 Testing health endpoints..."
curl -f "$PUBLIC_URL/api/v1/health" || echo "❌ Health check failed"
curl -f "$PUBLIC_URL/api/v1/evolution/health" || echo "❌ Evolution health check failed"

echo ""
echo "✅ DEPLOYMENT COMPLETE!"
echo "====================="
echo "🌐 Application: $PUBLIC_URL"
echo "📖 API Docs: $PUBLIC_URL/docs"
echo "🏥 Health: $PUBLIC_URL/api/v1/health"
echo "📱 WhatsApp Webhook: $PUBLIC_URL/api/v1/evolution/webhook"
echo "📊 Performance: $PUBLIC_URL/api/v1/performance/dashboard"
echo ""
echo "🔍 Monitor logs: railway logs"
echo "📈 Check status: railway status"
echo ""
echo "🎯 PRODUCTION SYSTEM IS LIVE! 🎯"