#!/bin/bash

# ============================================================================
# EVOLUTION API - CUSTOM ENTRYPOINT SCRIPT
# Handles initialization, health checks, and startup sequence
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[EVOLUTION-API INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[EVOLUTION-API SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[EVOLUTION-API WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[EVOLUTION-API ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Function to wait for database
wait_for_database() {
    log_info "Waiting for database connection..."
    
    if [ -n "$DATABASE_CONNECTION_URI" ]; then
        # Check if this is a Cloud SQL connection
        if echo "$DATABASE_CONNECTION_URI" | grep -q "/cloudsql/"; then
            log_info "Detected Cloud SQL connection, skipping connection check"
            log_info "Cloud SQL connection will be handled by the application"
            return 0
        else
            # Extract database details from standard URI
        DB_HOST=$(echo $DATABASE_CONNECTION_URI | sed -E 's|postgresql://[^@]*@([^:]+):.*|\1|')
        DB_PORT=$(echo $DATABASE_CONNECTION_URI | sed -E 's|postgresql://[^@]*@[^:]+:([0-9]+)/.*|\1|')
        
        log_info "Checking database connection to $DB_HOST:$DB_PORT"
        
        # Wait up to 60 seconds for database
        for i in {1..60}; do
            if nc -z "$DB_HOST" "$DB_PORT"; then
                log_success "Database connection established"
                return 0
            fi
            log_info "Waiting for database... (attempt $i/60)"
            sleep 1
        done
        
        log_error "Failed to connect to database after 60 seconds"
        exit 1
        fi
    else
        log_warning "No DATABASE_CONNECTION_URI found, skipping database check"
    fi
}

# Function to wait for Redis
wait_for_redis() {
    if [ "$CACHE_REDIS_ENABLED" = "true" ] && [ -n "$CACHE_REDIS_URI" ]; then
        # Extract Redis details from URI (handle database number in URI)
        REDIS_HOST=$(echo $CACHE_REDIS_URI | sed -E 's|redis://([^:]+):.*|\1|')
        REDIS_PORT=$(echo $CACHE_REDIS_URI | sed -E 's|redis://[^:]+:([0-9]+).*|\1|')
        
        log_info "Checking Redis connection to $REDIS_HOST:$REDIS_PORT"
        
        # Wait up to 30 seconds for Redis
        for i in {1..30}; do
            if nc -z "$REDIS_HOST" "$REDIS_PORT"; then
                log_success "Redis connection established"
                return 0
            fi
            log_info "Waiting for Redis... (attempt $i/30)"
            sleep 1
        done
        
        log_error "Failed to connect to Redis after 30 seconds"
        exit 1
    else
        log_info "Redis not enabled or no URI provided, skipping Redis check"
    fi
}

# Function to validate required environment variables
validate_environment() {
    log_info "Validating environment variables..."
    
    REQUIRED_VARS=(
        "AUTHENTICATION_API_KEY"
        "DATABASE_CONNECTION_URI"
    )
    
    for var in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!var}" ]; then
            log_error "Required environment variable $var is not set"
            exit 1
        fi
    done
    
    log_success "Environment validation passed"
}

# Function to initialize Evolution API
initialize_evolution() {
    log_info "Initializing Evolution API..."
    
    # Create necessary directories
    mkdir -p /evolution/instances
    mkdir -p /evolution/store
    
    log_success "Evolution API initialization completed"
}

# Function to show startup info
show_startup_info() {
    log_info "============================================================================"
    log_info "EVOLUTION API STARTING"
    log_info "============================================================================"
    log_info "Server URL: ${SERVER_URL:-http://localhost:8080}"
    log_info "Database: ${DATABASE_PROVIDER:-postgresql}"
    log_info "Redis Enabled: ${CACHE_REDIS_ENABLED:-false}"
    log_info "Authentication: ${AUTHENTICATION_TYPE:-jwt}"
    log_info "============================================================================"
}

# Main execution
main() {
    show_startup_info
    validate_environment
    wait_for_database
    wait_for_redis
    initialize_evolution
    
    log_success "Starting Evolution API..."
    
    # Execute the original command
    exec "$@"
}

# Run main function with all arguments
main "$@" 