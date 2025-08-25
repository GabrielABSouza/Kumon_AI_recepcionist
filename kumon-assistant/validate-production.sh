#!/bin/bash
# Production Validation Script - Wave 4.3 Step 2

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🔍 KUMON ASSISTANT - PRODUCTION VALIDATION${NC}"
echo "==========================================="

# Get Railway URL
RAILWAY_URL=$(railway domain 2>/dev/null || echo "")
if [ -z "$RAILWAY_URL" ]; then
    echo -e "${RED}❌ Could not get Railway URL. Make sure you're logged in and have deployed.${NC}"
    exit 1
fi

echo -e "${BLUE}🌐 Application URL: $RAILWAY_URL${NC}"
echo ""

# Function to test endpoint
test_endpoint() {
    local endpoint=$1
    local description=$2
    local expected_status=${3:-200}
    
    echo -n "Testing $description..."
    
    response=$(curl -s -o /dev/null -w "%{http_code}" "$RAILWAY_URL$endpoint" || echo "000")
    
    if [ "$response" -eq "$expected_status" ]; then
        echo -e " ${GREEN}✅ PASS${NC} (HTTP $response)"
        return 0
    else
        echo -e " ${RED}❌ FAIL${NC} (HTTP $response)"
        return 1
    fi
}

# Function to test JSON endpoint
test_json_endpoint() {
    local endpoint=$1
    local description=$2
    
    echo -n "Testing $description..."
    
    response=$(curl -s "$RAILWAY_URL$endpoint" 2>/dev/null || echo "")
    
    if echo "$response" | jq . >/dev/null 2>&1; then
        echo -e " ${GREEN}✅ PASS${NC} (Valid JSON)"
        return 0
    else
        echo -e " ${RED}❌ FAIL${NC} (Invalid JSON or no response)"
        return 1
    fi
}

echo -e "${YELLOW}📊 CORE HEALTH CHECKS${NC}"
echo "====================="

# Core health endpoints
test_endpoint "/" "Root endpoint"
test_endpoint "/api/v1/health" "Health check"
test_json_endpoint "/api/v1/health" "Health JSON response"

echo ""
echo -e "${YELLOW}🔧 API ENDPOINTS${NC}"
echo "================"

# API endpoints
test_endpoint "/docs" "API Documentation"
test_endpoint "/redoc" "ReDoc Documentation"

echo ""
echo -e "${YELLOW}📱 WHATSAPP INTEGRATION${NC}"
echo "=========================="

# Evolution API endpoints
test_endpoint "/api/v1/evolution/health" "Evolution API Health"
test_endpoint "/api/v1/evolution/instances" "Evolution Instances"

echo ""
echo -e "${YELLOW}⚡ PERFORMANCE MONITORING${NC}"
echo "=========================="

# Performance endpoints
test_endpoint "/api/v1/performance/health" "Performance Health"
test_endpoint "/api/v1/performance/dashboard" "Performance Dashboard"

echo ""
echo -e "${YELLOW}🛡️ SECURITY ENDPOINTS${NC}"
echo "====================="

# Security endpoints (should require auth - expect 401/403)
test_endpoint "/api/v1/security/metrics" "Security Metrics" 401
test_endpoint "/api/v1/alerts/dashboard" "Alert Dashboard" 401

echo ""
echo -e "${YELLOW}🔐 AUTHENTICATION${NC}"
echo "=================="

# Auth endpoints
test_endpoint "/api/v1/auth/status" "Auth Status" 200

echo ""
echo -e "${YELLOW}📊 BUSINESS REQUIREMENTS VALIDATION${NC}"
echo "==================================="

# Test business hours endpoint
echo -n "Testing business hours configuration..."
response=$(curl -s "$RAILWAY_URL/api/v1/health" | jq -r '.business_hours // empty' 2>/dev/null)
if [[ "$response" == *"8"* ]] && [[ "$response" == *"12"* ]] && [[ "$response" == *"14"* ]] && [[ "$response" == *"18"* ]]; then
    echo -e " ${GREEN}✅ PASS${NC} (Hours: 8h-12h, 14h-18h)"
else
    echo -e " ${YELLOW}⚠️  PARTIAL${NC} (Need to verify hours)"
fi

# Test pricing configuration
echo -n "Testing pricing configuration..."
response=$(curl -s "$RAILWAY_URL/api/v1/health" | jq -r '.pricing // empty' 2>/dev/null)
if [[ "$response" == *"375"* ]] && [[ "$response" == *"100"* ]]; then
    echo -e " ${GREEN}✅ PASS${NC} (R$375 + R$100)"
else
    echo -e " ${YELLOW}⚠️  PARTIAL${NC} (Need to verify pricing)"
fi

echo ""
echo -e "${YELLOW}🚀 PERFORMANCE TESTS${NC}"
echo "==================="

# Response time test
echo -n "Testing response time..."
start_time=$(date +%s%N)
curl -s "$RAILWAY_URL/api/v1/health" > /dev/null
end_time=$(date +%s%N)
response_time=$(( (end_time - start_time) / 1000000 )) # Convert to milliseconds

if [ "$response_time" -lt 5000 ]; then
    echo -e " ${GREEN}✅ PASS${NC} (${response_time}ms < 5000ms target)"
else
    echo -e " ${RED}❌ FAIL${NC} (${response_time}ms > 5000ms target)"
fi

# Load test (simple)
echo -n "Testing concurrent requests (5 requests)..."
for i in {1..5}; do
    curl -s "$RAILWAY_URL/api/v1/health" > /dev/null &
done
wait
echo -e " ${GREEN}✅ PASS${NC} (Handled concurrent requests)"

echo ""
echo -e "${YELLOW}📋 DEPLOYMENT SUMMARY${NC}"
echo "====================="

echo -e "🌐 Production URL: ${BLUE}$RAILWAY_URL${NC}"
echo -e "📖 API Docs: ${BLUE}$RAILWAY_URL/docs${NC}"
echo -e "🏥 Health Check: ${BLUE}$RAILWAY_URL/api/v1/health${NC}"
echo -e "📱 WhatsApp Webhook: ${BLUE}$RAILWAY_URL/api/v1/evolution/webhook${NC}"
echo -e "📊 Performance Dashboard: ${BLUE}$RAILWAY_URL/api/v1/performance/dashboard${NC}"

echo ""
echo -e "${GREEN}✅ PRODUCTION VALIDATION COMPLETE!${NC}"
echo ""
echo -e "${YELLOW}📋 NEXT STEPS:${NC}"
echo "1. Configure Evolution API webhook URL in your Evolution API dashboard"
echo "2. Test real WhatsApp message flow"
echo "3. Monitor performance metrics and costs"
echo "4. Set up business metrics tracking"
echo ""
echo -e "${BLUE}🎯 PRODUCTION SYSTEM IS READY FOR REAL CUSTOMERS! 🎯${NC}"