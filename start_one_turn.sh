#!/bin/bash

echo "=================================================="
echo "   KUMON ASSISTANT - ARQUITETURA ONE_TURN"
echo "=================================================="
echo ""
echo "🔍 Verificando configuração..."

# Verificar se as variáveis estão definidas
if [ -z "$OPENAI_API_KEY" ] && [ -z "$(grep OPENAI_API_KEY .env)" ]; then
    echo "❌ OPENAI_API_KEY não encontrada no .env"
    exit 1
fi

if [ -z "$GEMINI_API_KEY" ] && [ -z "$(grep GEMINI_API_KEY .env)" ]; then
    echo "❌ GEMINI_API_KEY não encontrada no .env"
    exit 1
fi

if [ -z "$EVOLUTION_API_KEY" ] && [ -z "$(grep EVOLUTION_API_KEY .env)" ]; then
    echo "❌ EVOLUTION_API_KEY não encontrada no .env"
    exit 1
fi

echo "✅ Configurações OK"
echo ""
echo "📡 Iniciando servidor FastAPI..."
echo "   Webhook: http://localhost:8000/api/v1/evolution/webhook"
echo "   Health: http://localhost:8000/health"
echo ""
echo "🚀 Servidor iniciando..."
echo "--------------------------------------------------"

python3 main.py