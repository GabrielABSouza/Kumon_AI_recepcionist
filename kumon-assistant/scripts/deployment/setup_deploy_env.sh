#!/bin/bash

# ============================================================================
# SETUP DEPLOY ENVIRONMENT - KUMON AI RECEPTIONIST
# Script para configurar as variáveis de ambiente necessárias para o deploy
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
    echo -e "${BLUE}  KUMON AI RECEPTIONIST - DEPLOY SETUP${NC}"
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

# Function to check if a variable is set
check_var() {
    local var_name="$1"
    local var_value="${!var_name}"
    
    if [ -z "$var_value" ]; then
        print_error "$var_name não está definida"
        return 1
    else
        print_success "$var_name está definida"
        return 0
    fi
}

# Function to prompt for a variable
prompt_for_var() {
    local var_name="$1"
    local description="$2"
    local is_secret="${3:-false}"
    
    echo ""
    print_status "Configure: $var_name"
    echo "Descrição: $description"
    
    if [ "$is_secret" = "true" ]; then
        read -s -p "Digite o valor (entrada oculta): " value
        echo ""
    else
        read -p "Digite o valor: " value
    fi
    
    if [ -n "$value" ]; then
        export "$var_name"="$value"
        echo "export $var_name=\"$value\"" >> ~/.bash_profile 2>/dev/null || true
        echo "export $var_name=\"$value\"" >> ~/.zshrc 2>/dev/null || true
        print_success "$var_name configurada"
    else
        print_error "Valor vazio fornecido para $var_name"
        return 1
    fi
}

# Main function
main() {
    print_header
    
    print_status "Verificando variáveis de ambiente necessárias..."
    
    # Required variables
    REQUIRED_VARS=(
        "OPENAI_API_KEY:Chave da API do OpenAI (https://platform.openai.com/api-keys):true"
        "EVOLUTION_API_KEY:Chave da API Evolution (gerada automaticamente):true"
        "DB_ROOT_PASSWORD:Senha do usuário root do PostgreSQL:true"
        "DB_USER_PASSWORD:Senha do usuário evolution do PostgreSQL:true"
    )
    
    local missing_vars=0
    
    # Check existing variables
    for var_info in "${REQUIRED_VARS[@]}"; do
        IFS=':' read -r var_name description is_secret <<< "$var_info"
        
        if ! check_var "$var_name"; then
            missing_vars=$((missing_vars + 1))
        fi
    done
    
    # If variables are missing, prompt for them
    if [ $missing_vars -gt 0 ]; then
        print_warning "Algumas variáveis estão faltando. Vamos configurá-las:"
        
        for var_info in "${REQUIRED_VARS[@]}"; do
            IFS=':' read -r var_name description is_secret <<< "$var_info"
            
            if [ -z "${!var_name}" ]; then
                if ! prompt_for_var "$var_name" "$description" "$is_secret"; then
                    print_error "Falha ao configurar $var_name"
                    exit 1
                fi
            fi
        done
    fi
    
    print_success "Todas as variáveis de ambiente estão configuradas!"
    
    echo ""
    print_status "Próximos passos:"
    echo "1. Execute: source ~/.zshrc (ou ~/.bash_profile)"
    echo "2. Execute: ./infrastructure/gcp/deploy.sh"
    echo ""
    print_warning "IMPORTANTE: Nunca commit suas chaves reais no Git!"
}

# Run main function
main "$@" 