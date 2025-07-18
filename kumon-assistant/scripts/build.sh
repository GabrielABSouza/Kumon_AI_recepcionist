#!/bin/bash

# ============================================================================
# KUMON ASSISTANT - BUILD & DEPLOYMENT SCRIPT
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

# Function to clean up old containers and images
cleanup() {
    print_status "Cleaning up old containers and images..."
    
    # Stop and remove containers
    docker-compose down --remove-orphans 2>/dev/null || true
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true
    docker-compose -f docker-compose.containers.yml down --remove-orphans 2>/dev/null || true
    
    # Remove old images
    docker image prune -f
    
    print_success "Cleanup completed"
}

# Function to build development version
build_dev() {
    print_status "Building Kumon Assistant for DEVELOPMENT..."
    
    # Build development version
    docker-compose build --no-cache kumon-assistant
    
    print_success "Development build completed"
}

# Function to build production version
build_prod() {
    print_status "Building Kumon Assistant for PRODUCTION..."
    
    # Enable BuildKit for better caching
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    
    # Build production version
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml build --no-cache kumon-assistant
    
    print_success "Production build completed"
}

# Function to build containerized version
build_containers() {
    print_status "Building ALL CUSTOM CONTAINERS..."
    
    # Enable BuildKit for better caching
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    
    # Build all custom containers
    docker-compose -f docker-compose.containers.yml build --no-cache
    
    print_success "Containerized build completed"
}

# Function to start development environment
start_dev() {
    print_status "Starting DEVELOPMENT environment..."
    
    docker-compose up -d
    
    print_success "Development environment started"
    print_status "Services available at:"
    echo "  - Kumon Assistant: http://localhost:8000"
    echo "  - Evolution API: http://localhost:8080"
    echo "  - Evolution Manager: http://localhost:8080/manager"
}

# Function to start production environment
start_prod() {
    print_status "Starting PRODUCTION environment..."
    
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
    
    print_success "Production environment started"
    print_status "Services available at:"
    echo "  - Kumon Assistant: http://localhost:8000"
    echo "  - Evolution API: http://localhost:8080"
    echo "  - Evolution Manager: http://localhost:8080/manager"
}

# Function to start containerized environment
start_containers() {
    print_status "Starting CONTAINERIZED environment..."
    
    # Start all services except setup first
    docker-compose -f docker-compose.containers.yml up -d postgres redis qdrant evolution-api kumon-assistant
    
    # Wait a moment for services to start
    sleep 10
    
    # Run setup container
    print_status "Running system setup..."
    docker-compose -f docker-compose.containers.yml run --rm setup
    
    print_success "Containerized environment started"
    print_status "Services available at:"
    echo "  - Kumon Assistant: http://localhost:8000"
    echo "  - Evolution API: http://localhost:8080"
    echo "  - Evolution Manager: http://localhost:8080/manager"
    echo "  - Qdrant: http://localhost:6333"
}

# Function to show logs
show_logs() {
    local service=${1:-kumon-assistant}
    local mode=${2:-dev}
    
    print_status "Showing logs for $service ($mode mode)..."
    
    case "$mode" in
        "prod")
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml logs -f $service
            ;;
        "containers")
            docker-compose -f docker-compose.containers.yml logs -f $service
            ;;
        *)
            docker-compose logs -f $service
            ;;
    esac
}

# Function to show status
show_status() {
    local mode=${1:-dev}
    
    print_status "Service status ($mode mode):"
    
    case "$mode" in
        "prod")
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
            ;;
        "containers")
            docker-compose -f docker-compose.containers.yml ps
            ;;
        *)
            docker-compose ps
            ;;
    esac
}

# Function to stop services
stop_services() {
    local mode=${1:-dev}
    
    print_status "Stopping services ($mode mode)..."
    
    case "$mode" in
        "prod")
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
            ;;
        "containers")
            docker-compose -f docker-compose.containers.yml down
            ;;
        *)
            docker-compose down
            ;;
    esac
    
    print_success "Services stopped"
}

# Function to run setup only
run_setup() {
    print_status "Running system setup..."
    
    docker-compose -f docker-compose.containers.yml run --rm setup
    
    print_success "Setup completed"
}

# Main script logic
case "$1" in
    "cleanup")
        check_docker
        cleanup
        ;;
    "build-dev")
        check_docker
        build_dev
        ;;
    "build-prod")
        check_docker
        build_prod
        ;;
    "build-containers")
        check_docker
        build_containers
        ;;
    "start-dev")
        check_docker
        start_dev
        ;;
    "start-prod")
        check_docker
        start_prod
        ;;
    "start-containers")
        check_docker
        start_containers
        ;;
    "logs")
        show_logs "$2" "$3"
        ;;
    "status")
        show_status "$2"
        ;;
    "stop")
        stop_services "$2"
        ;;
    "setup")
        check_docker
        run_setup
        ;;
    "full-dev")
        check_docker
        cleanup
        build_dev
        start_dev
        ;;
    "full-prod")
        check_docker
        cleanup
        build_prod
        start_prod
        ;;
    "full-containers")
        check_docker
        cleanup
        build_containers
        start_containers
        ;;
    *)
        echo "============================================================================"
        echo "KUMON ASSISTANT - BUILD & DEPLOYMENT SCRIPT"
        echo "============================================================================"
        echo ""
        echo "Usage: $0 [COMMAND]"
        echo ""
        echo "Commands:"
        echo "  cleanup              - Clean up old containers and images"
        echo "  build-dev            - Build development version"
        echo "  build-prod           - Build production version"
        echo "  build-containers     - Build all custom containers"
        echo "  start-dev            - Start development environment"
        echo "  start-prod           - Start production environment"
        echo "  start-containers     - Start containerized environment"
        echo "  stop [dev|prod|containers] - Stop services"
        echo "  status [dev|prod|containers] - Show service status"
        echo "  logs [service] [dev|prod|containers] - Show logs"
        echo "  setup                - Run system setup only"
        echo "  full-dev             - Cleanup, build, and start development"
        echo "  full-prod            - Cleanup, build, and start production"
        echo "  full-containers      - Cleanup, build, and start containerized"
        echo ""
        echo "Examples:"
        echo "  $0 full-containers   - Complete containerized setup"
        echo "  $0 build-containers  - Build all custom containers"
        echo "  $0 logs evolution-api containers - Show Evolution API logs"
        echo "  $0 stop containers   - Stop containerized environment"
        echo ""
        exit 1
        ;;
esac 