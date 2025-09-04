# 🧪 Testes E2E WhatsApp - Documentação

## Visão Geral

Sistema completo de testes End-to-End para validação do pipeline WhatsApp em ambientes staging e produção controlada.

**Pipeline Validado**: Safety → Outbox → Delivery sem loops infinitos

## Cenários de Teste

### 1. Cenário "Olá" - Happy Path
- **Ação**: Enviar "olá" via WhatsApp
- **Validações**:
  - ✅ StageResolver: stage=greeting, step=WELCOME
  - ✅ IntentClassifier: greeting detectado
  - ✅ ResponsePlanner: Outbox contains ≥1 mensagem
  - ✅ DeliveryIO: Mensagem entregue com sucesso
  - ✅ Sistema para com should_end=True
  - ✅ Nenhuma variável {{...}} vaza
  - ✅ Conteúdo neutro sem assumir gênero

### 2. Cenário Segurança - Template Perigoso
- **Ação**: Forçar template com diretivas de configuração
- **Validações**:
  - ✅ Safety detecta e bloqueia template perigoso
  - ✅ Outbox mantém conteúdo (não vazio)
  - ✅ Delivery acontece normalmente
  - ✅ Nenhuma diretiva {{SYSTEM_IDENTITY}} vaza
  - ✅ Sistema para sem loop

### 3. Cenário Outbox Vazio - Emergência
- **Ação**: Simular planner que retorna outbox vazio
- **Validações**:
  - ✅ Delivery detecta EMPTY OUTBOX
  - ✅ Emergency fallback adicionado UMA VEZ por sessão
  - ✅ Mensagem de emergência entregue
  - ✅ Sistema para para prevenir loop
  - ✅ Limit de 1x emergency por sessão respeitado

### 4. Cenário Deduplicação/Idempotência
- **Ação**: Enviar mesma mensagem 2x em sequência
- **Validações**:
  - ✅ Pelo menos uma mensagem processada
  - ✅ Sistema de deduplicação ativo (se implementado)
  - ✅ Nenhum erro de processamento
  - ✅ Métricas de idempotency coletadas

### 5. Cenário Enum & Estado
- **Ação**: Validar manipulação de enums vs strings
- **Validações**:
  - ✅ Nenhum erro 'str' object has no attribute 'value'
  - ✅ Stage tratado como enum corretamente
  - ✅ Nenhum erro de enum normalization
  - ✅ Telemetria de violações enum = 0

## Execução dos Testes

### Comandos Básicos

**Executar todos os cenários em staging:**
```bash
python tests/e2e/run_e2e_tests.py staging
```

**Executar todos os cenários em produção controlada:**
```bash
python tests/e2e/run_e2e_tests.py production
```

**Com logs detalhados:**
```bash
python tests/e2e/run_e2e_tests.py staging --detailed-logs
```

**Com relatório personalizado:**
```bash
python tests/e2e/run_e2e_tests.py staging --output my_report.json
```

**Modo verbose:**
```bash
python tests/e2e/run_e2e_tests.py staging --verbose
```

### Execução de Cenário Específico

**Executar apenas um cenário:**
```bash
python tests/e2e/run_e2e_tests.py staging --scenario 1  # Cenário "olá"
python tests/e2e/run_e2e_tests.py staging --scenario 2  # Segurança
python tests/e2e/run_e2e_tests.py staging --scenario 3  # Outbox vazio
python tests/e2e/run_e2e_tests.py staging --scenario 4  # Deduplicação
python tests/e2e/run_e2e_tests.py staging --scenario 5  # Enum validation
```

## Sistema de Observabilidade

### Dashboard de Métricas

O sistema coleta e exibe métricas críticas:

**📈 Resumo Executivo:**
- Cenários executados/passaram/falharam
- Taxa de sucesso geral
- Tempo total e médio de execução

**🔄 Saúde do Pipeline:**
- Mensagens planejadas vs entregues
- Taxa de entrega do sistema
- Eficiência do outbox

**🛡️ Sistema de Segurança:**
- Bloqueios safety detectados
- Efetividade do sistema de proteção
- Templates perigosos interceptados

**🚨 Confiabilidade:**
- Emergency fallbacks acionados
- Taxa de fallbacks de emergência
- Prevenção de loops infinitos

**✅ Validações Críticas:**
- Outbox sempre populado após planning
- Sistema safety ativo e funcionando
- Sistema delivery operacional
- Sem warnings async críticos
- Emergency fallbacks controlados

### Relatórios Detalhados

**Formato JSON:**
```json
{
  "timestamp": "2024-12-19T15:30:00",
  "summary": {
    "total_scenarios": 5,
    "passed": 5,
    "failed": 0,
    "success_rate": "100.0%"
  },
  "scenarios": [...],
  "observability_metrics": {...},
  "critical_validations": {...},
  "recommendations": [...]
}
```

## Configuração do Ambiente

### Variáveis de Ambiente

**Staging:**
```env
ENVIRONMENT=staging
EVOLUTION_API_URL=https://staging-api.example.com
TEST_PHONE_NUMBER=5551999999999
INSTANCE_NAME=staging_instance
```

**Produção Controlada:**
```env
ENVIRONMENT=production
EVOLUTION_API_URL=https://api.example.com
TEST_PHONE_NUMBER=5551888888888
INSTANCE_NAME=production_test_instance
```

### Pré-requisitos

1. **Evolution API configurada** nos ambientes
2. **Números de teste** registrados
3. **Permissões** para webhook testing
4. **Logs estruturados** habilitados no sistema

## Interpretação dos Resultados

### Status dos Testes

- ✅ **PASS**: Cenário executado com sucesso
- ❌ **FAIL**: Cenário falhou - investigar logs
- ⚠️ **WARNING**: Cenário passou mas com alertas

### Métricas Críticas

**Outbox Health:**
- `outbox_after_planning > 0` (exceto cenário 3)
- `messages_delivered ≥ outbox_after_planning`

**Safety System:**
- `safety_blocks > 0` quando template perigoso testado
- `safety_effectiveness = "Active"`

**Loop Prevention:**
- `emergency_fallbacks ≤ número_cenários`
- `should_end = True` em todos os cenários

### Troubleshooting

**Falhas Comuns:**

1. **Timeout de Conexão**
   - Verificar Evolution API
   - Validar configuração de webhook

2. **Logs Não Encontrados**
   - Confirmar level de logging
   - Verificar captura de logs ativa

3. **Templates Vazando**
   - Validar sistema safety ativo
   - Confirmar lint de templates

4. **Loop Infinito Detectado**
   - Verificar stop conditions
   - Analisar emergency fallback count

## Estrutura de Arquivos

```
tests/e2e/
├── whatsapp_e2e_framework.py    # Framework base
├── test_scenarios.py            # 5 cenários implementados  
├── run_e2e_tests.py            # Script principal + dashboard
└── README.md                   # Esta documentação
```

## Métricas de Qualidade

**Cobertura de Cenários:** 5/5 (100%)
**Validações por Cenário:** 6-8 assertions
**Observabilidade:** Dashboard completo + JSON detalhado
**Ambientes Suportados:** Staging + Produção controlada
**Tempo Execução:** ~30-60 segundos (todos os cenários)

---

## 🚀 Execução Rápida

Para validação completa do pipeline:

```bash
# Execute todos os cenários com observabilidade completa
python tests/e2e/run_e2e_tests.py staging --detailed-logs --verbose

# Verifique o relatório JSON gerado
cat e2e_report_staging_*.json | jq '.critical_validations'
```

**Resultado Esperado:** ✅ Todos os cenários passam, validações críticas OK, sistema sem loops.