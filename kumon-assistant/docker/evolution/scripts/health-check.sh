#!/bin/bash

# ============================================================================
# EVOLUTION API - HEALTH CHECK SCRIPT
# Comprehensive health monitoring for Evolution API
# ============================================================================

set -e

# Configuration
API_URL="${SERVER_URL:-http://localhost:8080}"
API_KEY="${AUTHENTICATION_API_KEY}"
TIMEOUT=10

# Function to check HTTP endpoint
check_http_endpoint() {
    local endpoint="$1"
    local expected_status="$2"
    
    local response_code
    response_code=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time $TIMEOUT \
        --connect-timeout 5 \
        -H "apikey: $API_KEY" \
        "$API_URL$endpoint" 2>/dev/null || echo "000")
    
    if [ "$response_code" = "$expected_status" ]; then
        return 0
    else
        echo "Health check failed: $endpoint returned $response_code, expected $expected_status"
        return 1
    fi
}

# Function to check database connectivity
check_database() {
    if [ -n "$DATABASE_CONNECTION_URI" ]; then
        # Extract database details
        DB_HOST=$(echo $DATABASE_CONNECTION_URI | sed -E 's|postgresql://[^@]*@([^:]+):.*|\1|')
        DB_PORT=$(echo $DATABASE_CONNECTION_URI | sed -E 's|postgresql://[^@]*@[^:]+:([0-9]+)/.*|\1|')
        
        if ! nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; then
            echo "Health check failed: Cannot connect to database $DB_HOST:$DB_PORT"
            return 1
        fi
    fi
    return 0
}

# Function to check Redis connectivity
check_redis() {
    if [ "$CACHE_REDIS_ENABLED" = "true" ] && [ -n "$CACHE_REDIS_URI" ]; then
        # Extract Redis details
        REDIS_HOST=$(echo $CACHE_REDIS_URI | sed -E 's|redis://([^:]+):.*|\1|')
        REDIS_PORT=$(echo $CACHE_REDIS_URI | sed -E 's|redis://[^:]+:([0-9]+)|\1|')
        
        if ! nc -z "$REDIS_HOST" "$REDIS_PORT" 2>/dev/null; then
            echo "Health check failed: Cannot connect to Redis $REDIS_HOST:$REDIS_PORT"
            return 1
        fi
    fi
    return 0
}

# Function to check Evolution API specific endpoints
check_evolution_api() {
    # Check if API is responding
    if ! check_http_endpoint "/" "200"; then
        return 1
    fi
    
    # Check manager endpoint (if available)
    if ! check_http_endpoint "/manager" "200"; then
        # Manager might return different status codes, so we'll be more lenient
        local response_code
        response_code=$(curl -s -o /dev/null -w "%{http_code}" \
            --max-time $TIMEOUT \
            --connect-timeout 5 \
            "$API_URL/manager" 2>/dev/null || echo "000")
        
        # Accept 200, 401, or 403 as valid responses (API is running)
        if [[ ! "$response_code" =~ ^(200|401|403)$ ]]; then
            echo "Health check failed: Manager endpoint not accessible"
            return 1
        fi
    fi
    
    return 0
}

# Main health check function
main() {
    local exit_code=0
    
    # Check database connectivity
    if ! check_database; then
        exit_code=1
    fi
    
    # Check Redis connectivity
    if ! check_redis; then
        exit_code=1
    fi
    
    # Check Evolution API endpoints
    if ! check_evolution_api; then
        exit_code=1
    fi
    
    if [ $exit_code -eq 0 ]; then
        echo "Health check passed: All services are healthy"
    else
        echo "Health check failed: One or more services are unhealthy"
    fi
    
    exit $exit_code
}

# Run main function
main "$@" 