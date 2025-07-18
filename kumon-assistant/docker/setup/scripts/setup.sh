#!/bin/bash

# ============================================================================
# KUMON ASSISTANT - COMPLETE SYSTEM SETUP SCRIPT
# Orchestrates database, Evolution API, and Qdrant initialization
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[SETUP INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SETUP SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[SETUP WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[SETUP ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_step() {
    echo -e "${PURPLE}[SETUP STEP]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Configuration
POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-evolution_db}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"

EVOLUTION_API_URL="${EVOLUTION_API_URL:-http://evolution-api:8080}"
EVOLUTION_API_KEY="${AUTHENTICATION_API_KEY}"
QDRANT_URL="${QDRANT_URL:-http://qdrant:6333}"

# Wait for service
wait_for_service() {
    local host="$1"
    local port="$2"
    local service_name="$3"
    local max_attempts="${4:-60}"
    
    log_info "Waiting for $service_name at $host:$port..."
    
    for i in $(seq 1 $max_attempts); do
        if nc -z "$host" "$port" 2>/dev/null; then
            log_success "$service_name is ready"
            return 0
        fi
        log_info "Waiting for $service_name... (attempt $i/$max_attempts)"
        sleep 2
    done
    
    log_error "Failed to connect to $service_name after $max_attempts attempts"
    return 1
}

# Wait for HTTP service
wait_for_http_service() {
    local url="$1"
    local service_name="$2"
    local max_attempts="${3:-30}"
    
    log_info "Waiting for $service_name at $url..."
    
    for i in $(seq 1 $max_attempts); do
        if curl -s --connect-timeout 5 --max-time 10 "$url" >/dev/null 2>&1; then
            log_success "$service_name is ready"
            return 0
        fi
        log_info "Waiting for $service_name... (attempt $i/$max_attempts)"
        sleep 2
    done
    
    log_error "Failed to connect to $service_name after $max_attempts attempts"
    return 1
}

# Setup PostgreSQL database
setup_database() {
    log_step "Setting up PostgreSQL database..."
    
    # Wait for PostgreSQL
    wait_for_service "$POSTGRES_HOST" "$POSTGRES_PORT" "PostgreSQL"
    
    # Check if database exists and is accessible
    if PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" >/dev/null 2>&1; then
        log_success "Database is accessible"
    else
        log_error "Cannot access database"
        return 1
    fi
    
    log_success "Database setup completed"
}

# Setup Qdrant vector database
setup_qdrant() {
    log_step "Setting up Qdrant vector database..."
    
    # Extract host and port from QDRANT_URL
    QDRANT_HOST=$(echo "$QDRANT_URL" | sed -E 's|http://([^:]+):.*|\1|')
    QDRANT_PORT=$(echo "$QDRANT_URL" | sed -E 's|http://[^:]+:([0-9]+)|\1|')
    
    # Wait for Qdrant
    wait_for_service "$QDRANT_HOST" "$QDRANT_PORT" "Qdrant"
    wait_for_http_service "$QDRANT_URL" "Qdrant HTTP API"
    
    # Create knowledge collection if it doesn't exist
    local collection_name="${QDRANT_COLLECTION_NAME:-kumon_knowledge}"
    local response
    
    response=$(curl -s -X GET "$QDRANT_URL/collections/$collection_name" 2>/dev/null || echo "not_found")
    
    if [[ "$response" == *"not_found"* ]] || [[ "$response" == *"Not found"* ]]; then
        log_info "Creating Qdrant collection: $collection_name"
        
        curl -s -X PUT "$QDRANT_URL/collections/$collection_name" \
            -H "Content-Type: application/json" \
            -d '{
                "vectors": {
                    "size": 384,
                    "distance": "Cosine"
                },
                "optimizers_config": {
                    "default_segment_number": 2
                },
                "replication_factor": 1
            }' >/dev/null
        
        if [ $? -eq 0 ]; then
            log_success "Qdrant collection created successfully"
        else
            log_error "Failed to create Qdrant collection"
            return 1
        fi
    else
        log_success "Qdrant collection already exists"
    fi
    
    log_success "Qdrant setup completed"
}

# Setup Evolution API
setup_evolution_api() {
    log_step "Setting up Evolution API..."
    
    # Extract host and port from EVOLUTION_API_URL
    EVOLUTION_HOST=$(echo "$EVOLUTION_API_URL" | sed -E 's|http://([^:]+):.*|\1|')
    EVOLUTION_PORT=$(echo "$EVOLUTION_API_URL" | sed -E 's|http://[^:]+:([0-9]+)|\1|')
    
    # Wait for Evolution API
    wait_for_service "$EVOLUTION_HOST" "$EVOLUTION_PORT" "Evolution API"
    wait_for_http_service "$EVOLUTION_API_URL" "Evolution API HTTP"
    
    # Wait a bit more for Evolution API to fully initialize
    sleep 10
    
    log_success "Evolution API setup completed"
}

# Create Evolution API instances
create_evolution_instances() {
    log_step "Creating Evolution API instances..."
    
    if [ -z "$EVOLUTION_API_KEY" ]; then
        log_warning "No Evolution API key provided, skipping instance creation"
        return 0
    fi
    
    # Instance configurations
    local instances=(
        "kumon-main:Kumon Main Instance"
        "kumon-support:Kumon Support Instance"
    )
    
    for instance_config in "${instances[@]}"; do
        IFS=':' read -r instance_name instance_description <<< "$instance_config"
        
        log_info "Creating instance: $instance_name"
        
        local response
        response=$(curl -s -X POST "$EVOLUTION_API_URL/instance/create" \
            -H "Content-Type: application/json" \
            -H "apikey: $EVOLUTION_API_KEY" \
            -d "{
                \"instanceName\": \"$instance_name\",
                \"token\": \"$(uuidgen | tr '[:upper:]' '[:lower:]')\",
                \"integration\": \"WHATSAPP-BAILEYS\"
            }" 2>/dev/null)
        
        if echo "$response" | jq -e '.instance' >/dev/null 2>&1; then
            log_success "Instance '$instance_name' created successfully"
        else
            log_warning "Instance '$instance_name' may already exist or failed to create"
        fi
    done
    
    log_success "Evolution API instances setup completed"
}

# Verify system setup
verify_setup() {
    log_step "Verifying system setup..."
    
    local errors=0
    
    # Check PostgreSQL
    if ! PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" >/dev/null 2>&1; then
        log_error "PostgreSQL verification failed"
        ((errors++))
    else
        log_success "PostgreSQL verification passed"
    fi
    
    # Check Qdrant
    if ! curl -s "$QDRANT_URL/collections" >/dev/null; then
        log_error "Qdrant verification failed"
        ((errors++))
    else
        log_success "Qdrant verification passed"
    fi
    
    # Check Evolution API
    if ! curl -s "$EVOLUTION_API_URL" >/dev/null; then
        log_error "Evolution API verification failed"
        ((errors++))
    else
        log_success "Evolution API verification passed"
    fi
    
    if [ $errors -eq 0 ]; then
        log_success "All system verifications passed"
        return 0
    else
        log_error "System verification failed with $errors errors"
        return 1
    fi
}

# Show setup completion summary
show_summary() {
    log_info "============================================================================"
    log_info "KUMON ASSISTANT SYSTEM SETUP COMPLETED"
    log_info "============================================================================"
    log_info "PostgreSQL: $POSTGRES_HOST:$POSTGRES_PORT"
    log_info "Evolution API: $EVOLUTION_API_URL"
    log_info "Qdrant: $QDRANT_URL"
    log_info "Manager UI: $EVOLUTION_API_URL/manager"
    log_info "============================================================================"
    log_success "System is ready for use!"
}

# Main execution
main() {
    log_info "Starting Kumon Assistant system setup..."
    
    # Run setup steps
    setup_database
    setup_qdrant
    setup_evolution_api
    create_evolution_instances
    verify_setup
    
    show_summary
    
    log_success "Setup completed successfully!"
}

# Handle script termination
cleanup() {
    log_info "Setup script terminated"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

# Run main function
main "$@" 