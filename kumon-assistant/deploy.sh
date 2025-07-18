#!/bin/bash

# ============================================================================
# KUMON AI RECEPTIONIST - DEPLOYMENT SCRIPT
# Deploys all services to Google Cloud Run with cost optimization
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="kumon-ai-receptionist"
REGION="us-central1"
BUILD_CONFIG="cloudbuild.yaml"

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

print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  KUMON AI RECEPTIONIST - DEPLOYMENT${NC}"
    echo -e "${BLUE}============================================${NC}"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if logged in
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        print_error "Please login to gcloud first: gcloud auth login"
        exit 1
    fi
    
    # Check if project exists
    if ! gcloud projects describe $PROJECT_ID &> /dev/null; then
        print_error "Project $PROJECT_ID does not exist or you don't have access."
        exit 1
    fi
    
    # Set project
    gcloud config set project $PROJECT_ID
    
    print_success "Prerequisites check passed!"
}

# Function to enable required APIs
enable_apis() {
    print_status "Enabling required Google Cloud APIs..."
    
    gcloud services enable \
        cloudbuild.googleapis.com \
        run.googleapis.com \
        artifactregistry.googleapis.com \
        secretmanager.googleapis.com \
        --quiet
    
    print_success "APIs enabled successfully!"
}

# Function to start deployment
start_deployment() {
    print_status "Starting deployment with Cloud Build..."
    
    # Submit build
    gcloud builds submit \
        --config=$BUILD_CONFIG \
        --substitutions=_OPENAI_API_KEY="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",_EVOLUTION_API_KEY="B6D711FCDE4D4FD5936544120E713976",_EMBEDDING_CACHE_SIZE_MB="50",_EMBEDDING_CACHE_FILES="500",_MAX_ACTIVE_CONVERSATIONS="500",_CONVERSATION_TIMEOUT_HOURS="12",_CACHE_CLEANUP_INTERVAL="1800" \
        --region=$REGION \
        --quiet
    
    print_success "Deployment submitted successfully!"
}

# Function to get service URLs
get_service_urls() {
    print_status "Getting service URLs..."
    
    echo ""
    echo "🎉 DEPLOYMENT COMPLETE! 🎉"
    echo "=========================="
    
    # Get URLs
    QDRANT_URL=$(gcloud run services describe kumon-qdrant --region=$REGION --format="value(status.url)" 2>/dev/null || echo "Not deployed")
    EVOLUTION_URL=$(gcloud run services describe kumon-evolution-api --region=$REGION --format="value(status.url)" 2>/dev/null || echo "Not deployed")
    KUMON_URL=$(gcloud run services describe kumon-assistant --region=$REGION --format="value(status.url)" 2>/dev/null || echo "Not deployed")
    
    echo "📊 Qdrant Database: $QDRANT_URL"
    echo "📱 Evolution API: $EVOLUTION_URL"
    echo "🤖 Kumon Assistant: $KUMON_URL"
    echo ""
    echo "🔗 NEXT STEPS:"
    echo "1. Configure your WhatsApp webhook to: $KUMON_URL/api/v1/evolution/webhook"
    echo "2. Test the system by sending a WhatsApp message"
    echo "3. Monitor logs: gcloud logs read --service kumon-assistant"
    echo ""
    echo "💰 COST OPTIMIZATION:"
    echo "• All services are configured with minimum instances"
    echo "• Auto-scaling based on demand"
    echo "• Optimized resource allocation"
    echo ""
}

# Function to show deployment status
show_status() {
    print_status "Checking deployment status..."
    
    echo ""
    echo "📋 SERVICE STATUS:"
    echo "=================="
    
    # Check each service
    for service in kumon-qdrant kumon-evolution-api kumon-assistant; do
        if gcloud run services describe $service --region=$REGION --format="value(status.url)" &> /dev/null; then
            print_success "$service: ✅ Deployed"
        else
            print_warning "$service: ❌ Not deployed"
        fi
    done
    
    echo ""
}

# Function to clean up (if needed)
cleanup() {
    print_warning "Cleaning up resources..."
    
    read -p "Are you sure you want to delete all services? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        gcloud run services delete kumon-assistant --region=$REGION --quiet 2>/dev/null || true
        gcloud run services delete kumon-evolution-api --region=$REGION --quiet 2>/dev/null || true
        gcloud run services delete kumon-qdrant --region=$REGION --quiet 2>/dev/null || true
        print_success "Services deleted successfully!"
    else
        print_status "Cleanup cancelled."
    fi
}

# Main execution
main() {
    print_header
    
    case "${1:-deploy}" in
        "deploy")
            check_prerequisites
            enable_apis
            start_deployment
            sleep 10  # Wait for deployment to complete
            get_service_urls
            ;;
        "status")
            show_status
            get_service_urls
            ;;
        "cleanup")
            cleanup
            ;;
        "help")
            echo "Usage: $0 [deploy|status|cleanup|help]"
            echo ""
            echo "Commands:"
            echo "  deploy   - Deploy all services (default)"
            echo "  status   - Check deployment status"
            echo "  cleanup  - Delete all services"
            echo "  help     - Show this help message"
            ;;
        *)
            print_error "Unknown command: $1"
            echo "Use '$0 help' for available commands."
            exit 1
            ;;
    esac
}

# Run main function
main "$@" 