#!/bin/bash

# Demo Script - Testes E2E WhatsApp
# Este script demonstra como executar os testes E2E do pipeline WhatsApp

echo "🧪 === DEMO: Testes E2E WhatsApp ==="
echo ""

echo "📋 Cenários disponíveis:"
echo "  1. Cenário 'Olá' - Happy Path"
echo "  2. Cenário Segurança - Template Perigoso"  
echo "  3. Cenário Outbox Vazio - Emergência"
echo "  4. Cenário Deduplicação/Idempotência"
echo "  5. Cenário Enum & Estado"
echo ""

echo "🚀 Exemplos de execução:"
echo ""

echo "1. Executar todos os cenários em staging:"
echo "   python3 tests/e2e/run_e2e_tests.py staging"
echo ""

echo "2. Executar com logs detalhados:"
echo "   python3 tests/e2e/run_e2e_tests.py staging --detailed-logs"
echo ""

echo "3. Executar cenário específico:"
echo "   python3 tests/e2e/run_e2e_tests.py staging --scenario 1"
echo ""

echo "4. Executar com relatório personalizado:"
echo "   python3 tests/e2e/run_e2e_tests.py staging --output my_report.json"
echo ""

echo "📊 O que os testes validam:"
echo "✅ Pipeline completo: Safety → Outbox → Delivery"
echo "✅ Prevenção de loops infinitos" 
echo "✅ Templates seguros (sem {{...}} vazando)"
echo "✅ Stop conditions funcionando"
echo "✅ Emergency fallbacks (1x por sessão)"
echo "✅ Deduplicação e idempotência"
echo "✅ Manipulação correta de enums"
echo ""

echo "⚠️  IMPORTANTE:"
echo "   - Configure as variáveis de ambiente antes de executar"
echo "   - Certifique-se que Evolution API está funcionando"
echo "   - Use números de teste válidos"
echo ""

echo "📖 Documentação completa em: tests/e2e/README.md"
echo ""

# Verificar se o usuário quer executar um teste de demonstração
read -p "🔥 Executar teste de demonstração agora? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🧪 Executando teste de demonstração..."
    echo ""
    
    # Verificar se podemos executar
    if command -v python3 &> /dev/null; then
        echo "ℹ️  Executando: python3 tests/e2e/run_e2e_tests.py staging --verbose"
        echo "   (Ctrl+C para cancelar se necessário)"
        echo ""
        
        # Dar um tempo para o usuário cancelar se quiser
        sleep 3
        
        # Executar o teste (pode falhar se ambiente não configurado)
        python3 tests/e2e/run_e2e_tests.py staging --verbose || {
            echo ""
            echo "❌ Teste falhou - provavelmente falta configuração do ambiente"
            echo "📋 Configure as variáveis de ambiente e tente novamente"
            echo "📖 Veja tests/e2e/README.md para detalhes"
        }
    else
        echo "❌ python3 não encontrado - instale Python 3 primeiro"
    fi
else
    echo ""
    echo "👍 OK - execute manualmente quando estiver pronto!"
fi

echo ""
echo "🎯 Pipeline pronto para validação E2E completa!"