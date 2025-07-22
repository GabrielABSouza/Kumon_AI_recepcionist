#!/bin/bash

# 🚀 Evolution API Quick Setup Script for Kumon Assistant
# This script automates the setup of Evolution API for cost-free WhatsApp integration

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}"
    echo "=================================="
    echo "$1"
    echo "=================================="
    echo -e "${NC}"
}

# Main setup function
main() {
    print_header "🚀 Kumon Assistant - Evolution API Setup"
    
    print_info "Setting up cost-free WhatsApp integration with Evolution API"
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Setup environment
    setup_environment
    
    # Start services
    start_services
    
    # Initialize system
    initialize_system
    
    # Setup WhatsApp instance
    setup_whatsapp_instance
    
    # Final instructions
    show_final_instructions
}

check_prerequisites() {
    print_header "📋 Checking Prerequisites"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_success "Docker is installed"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    print_success "Docker Compose is installed"
    
    # Check if docker-compose.yml exists
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml not found. Please run this script from the project root."
        exit 1
    fi
    print_success "docker-compose.yml found"
    
    echo ""
}

setup_environment() {
    print_header "⚙️  Setting up Environment"
    
    # Check if .env already exists
    if [ -f ".env" ]; then
        print_warning ".env file already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Keeping existing .env file"
            return
        fi
    fi
    
    # Copy example environment file
    if [ -f "evolution_config.env.example" ]; then
        cp evolution_config.env.example .env
        print_success "Environment file created from example"
    else
        print_error "evolution_config.env.example not found"
        exit 1
    fi
    
    # Generate secure API keys
    print_info "Generating secure API keys..."
    GLOBAL_API_KEY=$(openssl rand -hex 32)
    
    # Update .env file with generated keys (keep AUTHENTICATION_API_KEY as 1234)
    sed -i.bak "s/your_global_api_key/$GLOBAL_API_KEY/g" .env
    rm .env.bak 2>/dev/null || true
    
    print_success "Secure API keys configured"
    print_info "Using AUTHENTICATION_API_KEY=1234 (as configured)"
    
    # Prompt for OpenAI API key
    echo ""
    print_info "OpenAI API key is required for AI responses"
    read -p "Enter your OpenAI API key: " OPENAI_KEY
    
    if [ -n "$OPENAI_KEY" ]; then
        sed -i.bak "s/your_openai_api_key_here/$OPENAI_KEY/g" .env
        rm .env.bak 2>/dev/null || true
        print_success "OpenAI API key configured"
    else
        print_warning "No OpenAI API key provided - you can add it later in .env file"
    fi
    
    echo ""
}

start_services() {
    print_header "🚀 Starting Services"
    
    print_info "Starting Evolution API, Qdrant, and Kumon Assistant..."
    
    # Start services in detached mode
    docker-compose up -d
    
    print_success "Services started successfully"
    
    # Wait for services to be ready
    print_info "Waiting for services to be ready..."
    sleep 15
    
    # Check if services are running
    if docker-compose ps | grep -q "Up"; then
        print_success "All services are running"
    else
        print_error "Some services failed to start. Check logs with: docker-compose logs"
        exit 1
    fi
    
    echo ""
}

initialize_system() {
    print_header "🔧 Initializing System"
    
    print_info "Waiting for Kumon Assistant to be ready..."
    
    # Wait for the application to be ready
    max_attempts=30
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/api/v1/health >/dev/null 2>&1; then
            print_success "Kumon Assistant is ready"
            break
        fi
        
        print_info "Attempt $attempt/$max_attempts - waiting for service..."
        sleep 2
        ((attempt++))
    done
    
    if [ $attempt -gt $max_attempts ]; then
        print_error "Kumon Assistant failed to start. Check logs: docker-compose logs kumon-assistant"
        exit 1
    fi
    
    # Initialize embedding system
    print_info "Initializing embedding system..."
    if docker-compose exec -T kumon-assistant python scripts/setup_embeddings.py >/dev/null 2>&1; then
        print_success "Embedding system initialized"
    else
        print_warning "Embedding system initialization failed - you can run it manually later"
    fi
    
    echo ""
}

setup_whatsapp_instance() {
    print_header "📱 Setting up WhatsApp Instance"
    
    # Get instance name from user
    read -p "Enter a name for your WhatsApp instance (default: kumon_main): " INSTANCE_NAME
    INSTANCE_NAME=${INSTANCE_NAME:-kumon_main}
    
    print_info "Creating WhatsApp instance: $INSTANCE_NAME"
    
    # Create instance via API
    RESPONSE=$(curl -s -X POST "http://localhost:8000/api/v1/evolution/instances" \
        -H "Content-Type: application/json" \
        -d "{\"instance_name\": \"$INSTANCE_NAME\"}")
    
    if echo "$RESPONSE" | grep -q "success.*true"; then
        print_success "WhatsApp instance created successfully"
    else
        print_error "Failed to create WhatsApp instance"
        print_info "Response: $RESPONSE"
        exit 1
    fi
    
    # Get QR code
    print_info "Generating QR code for WhatsApp connection..."
    sleep 3
    
    QR_RESPONSE=$(curl -s "http://localhost:8000/api/v1/evolution/instances/$INSTANCE_NAME/qr")
    
    if echo "$QR_RESPONSE" | grep -q "qr_code"; then
        print_success "QR code generated"
        print_info "QR code endpoint: http://localhost:8000/api/v1/evolution/instances/$INSTANCE_NAME/qr"
    else
        print_warning "QR code generation failed - you can get it manually later"
    fi
    
    echo ""
}

show_final_instructions() {
    print_header "🎉 Setup Complete!"
    
    print_success "Evolution API integration is ready!"
    echo ""
    
    print_info "Next steps:"
    echo "1. 📱 Connect WhatsApp:"
    echo "   - Visit: http://localhost:8000/api/v1/evolution/instances/kumon_main/qr"
    echo "   - Copy the QR code (base64) and decode it"
    echo "   - Open WhatsApp > Settings > Linked Devices > Link a Device"
    echo "   - Scan the QR code"
    echo ""
    
    echo "2. 🧪 Test the integration:"
    echo "   - Send a message to your connected WhatsApp number"
    echo "   - The AI should respond automatically"
    echo ""
    
    echo "3. 📊 Monitor the system:"
    echo "   - API Documentation: http://localhost:8000/docs"
    echo "   - Health Check: http://localhost:8000/api/v1/evolution/health"
    echo "   - View Logs: docker-compose logs -f"
    echo ""
    
    echo "4. 🔧 Additional configuration:"
    echo "   - Edit .env file for custom settings"
    echo "   - Add business information (phone, address, etc.)"
    echo "   - Customize AI responses in app/data/few_shot_examples.json"
    echo ""
    
    print_info "Useful commands:"
    echo "  - Check status: curl http://localhost:8000/api/v1/evolution/instances"
    echo "  - Stop services: docker-compose down"
    echo "  - View logs: docker-compose logs [service-name]"
    echo ""
    
    print_success "Your cost-free WhatsApp AI receptionist is ready! 🤖💬"
    print_info "For detailed documentation, see: EVOLUTION_API_SETUP.md"
}

# Error handling
trap 'print_error "Setup failed! Check the logs above for details."' ERR

# Run main function
main "$@" 