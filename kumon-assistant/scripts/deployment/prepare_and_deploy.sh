#!/bin/bash

# ============================================================================
# KUMON AI RECEPTIONIST - PREPARAÇÃO E DEPLOY COMPLETO
# Script que realiza todas as verificações e deploy para Google Cloud
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  KUMON AI RECEPTIONIST - DEPLOY COMPLETO${NC}"
    echo -e "${BLUE}============================================${NC}"
}

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

# Function to check prerequisites
check_prerequisites() {
    print_status "Verificando pré-requisitos..."
    
    # Check if gcloud is installed
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI não está instalado. Instale primeiro:"
        echo "  brew install google-cloud-sdk"
        exit 1
    fi
    
    # Check if logged in
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        print_error "Faça login no gcloud primeiro:"
        echo "  gcloud auth login"
        exit 1
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker não está instalado ou não está rodando"
        exit 1
    fi
    
    print_success "Pré-requisitos OK!"
}

# Function to validate environment variables
validate_env_vars() {
    print_status "Validando variáveis de ambiente..."
    
    local missing_vars=0
    
    # Required variables
    local required_vars=("OPENAI_API_KEY" "EVOLUTION_API_KEY" "DB_ROOT_PASSWORD" "DB_USER_PASSWORD")
    
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            print_error "$var não está definida"
            missing_vars=$((missing_vars + 1))
        else
            print_success "$var está definida"
        fi
    done
    
    if [ $missing_vars -gt 0 ]; then
        print_error "Execute o script de configuração primeiro:"
        echo "  ./setup_deploy_env.sh"
        exit 1
    fi
    
    print_success "Variáveis de ambiente OK!"
}

# Function to check Google Cloud project
check_gcp_project() {
    print_status "Verificando projeto Google Cloud..."
    
    local project_id="kumon-ai-receptionist"
    
    if ! gcloud projects describe $project_id &> /dev/null; then
        print_error "Projeto $project_id não existe ou você não tem acesso."
        print_status "Projetos disponíveis:"
        gcloud projects list --format="table(projectId,name)"
        echo ""
        read -p "Digite o PROJECT_ID correto: " project_id
        
        # Update deploy.sh with correct project ID
        sed -i.bak "s/PROJECT_ID=\".*\"/PROJECT_ID=\"$project_id\"/" infrastructure/gcp/deploy.sh
        print_success "PROJECT_ID atualizado para: $project_id"
    fi
    
    gcloud config set project $project_id
    print_success "Projeto configurado: $project_id"
}

# Function to validate file structure
validate_structure() {
    print_status "Validando estrutura de arquivos..."
    
    local required_files=(
        "app/main.py"
        "infrastructure/docker/app/Dockerfile"
        "infrastructure/docker/evolution-api/Dockerfile"
        "infrastructure/docker/qdrant/Dockerfile"
        "infrastructure/gcp/cloudbuild.yaml"
        "infrastructure/gcp/deploy.sh"
        "infrastructure/config/requirements-hybrid.txt"
    )
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            print_error "Arquivo não encontrado: $file"
            exit 1
        fi
    done
    
    print_success "Estrutura de arquivos OK!"
}

# Function to show deployment summary
show_summary() {
    print_status "============================================"
    print_status "RESUMO DO DEPLOY"
    print_status "============================================"
    echo "📱 Serviços que serão implantados:"
    echo "  • Kumon Assistant (Main App) - Cloud Run"
    echo "  • Evolution API (WhatsApp) - Cloud Run"
    echo "  • Qdrant (Vector DB) - Cloud Run"
    echo "  • PostgreSQL - Cloud SQL"
    echo "  • Redis - Memorystore"
    echo ""
    echo "💰 Custo estimado: ~R$ 400-600/mês"
    echo "🌐 Região: us-central1"
    echo "⚡ Auto-scaling habilitado"
    echo ""
    print_warning "Este processo pode levar 30-60 minutos"
}

# Function to confirm deployment
confirm_deployment() {
    echo ""
    read -p "Deseja continuar com o deploy? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Deploy cancelado pelo usuário."
        exit 0
    fi
}

# Function to execute deployment
execute_deployment() {
    print_status "Iniciando deploy..."
    
    # Change to the correct directory for cloudbuild.yaml
    cd infrastructure/gcp
    
    # Execute deployment
    ./deploy.sh
    
    print_success "Deploy concluído!"
}

# Function to show post-deployment info
show_post_deployment() {
    print_success "============================================"
    print_success "DEPLOY CONCLUÍDO COM SUCESSO!"
    print_success "============================================"
    
    echo ""
    print_status "Próximos passos:"
    echo "1. 🔍 Verificar logs dos serviços no Google Cloud Console"
    echo "2. 📱 Configurar o webhook do WhatsApp"
    echo "3. 🧪 Testar a aplicação enviando uma mensagem"
    echo ""
    print_status "Links úteis:"
    echo "• Google Cloud Console: https://console.cloud.google.com"
    echo "• Cloud Run Services: https://console.cloud.google.com/run"
    echo "• Logs: https://console.cloud.google.com/logs"
    echo ""
    print_warning "Lembre-se de monitorar os custos!"
}

# Main function
main() {
    print_header
    
    check_prerequisites
    validate_env_vars
    check_gcp_project
    validate_structure
    show_summary
    confirm_deployment
    execute_deployment
    show_post_deployment
}

# Run main function
main "$@" 