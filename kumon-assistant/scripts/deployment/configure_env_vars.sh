#!/bin/bash

# ============================================================================
# CONFIGURAÇÃO RÁPIDA DE VARIÁVEIS - KUMON AI RECEPTIONIST
# ============================================================================

echo "🔧 CONFIGURAÇÃO RÁPIDA DE VARIÁVEIS DE AMBIENTE"
echo "=============================================="
echo ""
echo "Vou solicitar suas chaves uma por vez..."
echo ""

# Function to read input safely
read_var() {
    local var_name="$1"
    local description="$2"
    local is_secret="${3:-false}"
    
    echo "📋 $var_name"
    echo "   $description"
    
    if [ "$is_secret" = "true" ]; then
        read -s -p "   Digite o valor (entrada oculta): " value
        echo ""
    else
        read -p "   Digite o valor: " value
    fi
    
    export "$var_name"="$value"
    echo "   ✅ $var_name configurada!"
    echo ""
}

# Collect all variables
read_var "OPENAI_API_KEY" "Chave da API do OpenAI (https://platform.openai.com/api-keys)" true
read_var "EVOLUTION_API_KEY" "Chave da Evolution API (qualquer string de 32 caracteres)" true  
read_var "DB_ROOT_PASSWORD" "Senha do usuário root do PostgreSQL" true
read_var "DB_USER_PASSWORD" "Senha do usuário evolution do PostgreSQL" true

echo "🎉 TODAS AS VARIÁVEIS CONFIGURADAS!"
echo "=================================="
echo ""
echo "Próximo passo:"
echo "  ./infrastructure/gcp/deploy-ultra-cheap.sh"
echo ""
echo "💰 Deploy ultra-econômico: R$ 115/mês (72% economia)" 