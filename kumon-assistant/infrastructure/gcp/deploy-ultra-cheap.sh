#!/bin/bash

# ============================================================================
# KUMON AI RECEPTIONIST - ULTRA-CHEAP DEPLOYMENT
# 72% cost reduction: R$ 440/month → R$ 125/month
# ============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_ID="kumon-ai-receptionist"
REGION="us-central1"
BUILD_CONFIG="../cloudbuild-ultra-cheap.yaml"

print_header() {
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  💰 ULTRA-CHEAP DEPLOYMENT (72% OFF!)${NC}"
    echo -e "${GREEN}============================================${NC}"
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

show_savings() {
    echo -e "${GREEN}💰 ECONOMIA RADICAL:${NC}"
    echo "┌─────────────────────────────────────────┐"
    echo "│ ANTES        │ ULTRA-CHEAP  │ ECONOMIA  │"
    echo "├─────────────────────────────────────────┤"
    echo "│ Evolution    │ R$ 150 → R$ 50  │   67%   │"
    echo "│ Kumon App    │ R$ 100 → R$ 30  │   70%   │"
    echo "│ Qdrant       │ R$ 80  → R$ 20  │   75%   │"
    echo "│ PostgreSQL   │ R$ 60  → R$ 15  │   75%   │"
    echo "│ Redis        │ R$ 50  → R$ 0   │  100%   │"
    echo "├─────────────────────────────────────────┤"
    echo "│ TOTAL        │ R$ 440 → R$ 115 │   72%   │"
    echo "└─────────────────────────────────────────┘"
    echo ""
    print_warning "⚠️  Configuração extremamente econômica:"
    echo "• Cold start: 3-5 segundos"
    echo "• Capacidade: 100 conversas/dia"
    echo "• Storage: HDD (mais lento, muito mais barato)"
    echo "• Cache: Local apenas (sem Redis externo)"
    echo ""
}

check_prerequisites() {
    print_status "Verificando pré-requisitos..."
    
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI não está instalado"
        exit 1
    fi
    
    if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
        print_error "Faça login no gcloud primeiro: gcloud auth login"
        exit 1
    fi
    
    if [[ -z "$OPENAI_API_KEY" || -z "$EVOLUTION_API_KEY" || -z "$DB_ROOT_PASSWORD" || -z "$DB_USER_PASSWORD" ]]; then
        print_error "Configure as variáveis de ambiente primeiro:"
        echo "  ./setup_deploy_env.sh"
        exit 1
    fi
    
    gcloud config set project $PROJECT_ID
    print_success "Pré-requisitos OK!"
}

enable_apis() {
    print_status "Habilitando APIs necessárias..."
    
    gcloud services enable \
        cloudbuild.googleapis.com \
        run.googleapis.com \
        artifactregistry.googleapis.com \
        secretmanager.googleapis.com \
        sqladmin.googleapis.com \
        --quiet
    
    print_success "APIs habilitadas!"
}

confirm_ultra_cheap() {
    echo ""
    print_warning "⚠️  ATENÇÃO: Deploy Ultra-Econômico"
    echo "• Recursos mínimos extremos (256Mi-512Mi RAM)"
    echo "• PostgreSQL com HDD (mais lento)"
    echo "• Sem Redis externo (cache local)"
    echo "• Cold starts de 3-5 segundos"
    echo ""
    echo "✅ Vantagens:"
    echo "• 72% de economia nos custos"
    echo "• Funcionalidade completa mantida"
    echo "• Auto-scaling inteligente"
    echo ""
    read -p "Continuar com deploy ultra-econômico? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Deploy cancelado."
        exit 0
    fi
}

start_deployment() {
    print_status "Iniciando deploy ultra-econômico..."
    
    gcloud builds submit \
        --config=$BUILD_CONFIG \
        --substitutions=_OPENAI_API_KEY="$OPENAI_API_KEY",_EVOLUTION_API_KEY="$EVOLUTION_API_KEY",_DB_ROOT_PASSWORD="$DB_ROOT_PASSWORD",_DB_USER_PASSWORD="$DB_USER_PASSWORD" \
        --region=$REGION \
        --quiet
    
    print_success "Deploy ultra-econômico concluído!"
}

show_final_summary() {
    print_success "🎉 ULTRA-CHEAP DEPLOYMENT COMPLETE!"
    echo ""
    echo "💰 CUSTO FINAL ESTIMADO:"
    echo "• Cloud Run Services: ~R$ 100/mês"
    echo "• PostgreSQL HDD: ~R$ 15/mês"
    echo "• Outros serviços: ~R$ 5/mês"
    echo "• OpenAI API: ~R$ 100-200/mês"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "• TOTAL: R$ 220-320/mês"
    echo "• ECONOMIA: 72% vs configuração padrão"
    echo ""
    print_status "Próximos passos:"
    echo "1. Configurar webhook do WhatsApp"
    echo "2. Testar com mensagem"
    echo "3. Monitorar custos no console"
    echo ""
    print_warning "⚠️  Configure alertas de billing!"
}

main() {
    print_header
    show_savings
    check_prerequisites
    confirm_ultra_cheap
    enable_apis
    start_deployment
    show_final_summary
}

main "$@" 