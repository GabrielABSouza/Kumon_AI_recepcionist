# 🚨 PROCEDIMENTOS DE EMERGÊNCIA - Kumon Assistant V2

**OBJETIVO**: Procedimentos rápidos para rollback e recuperação em caso de problemas críticos no go-live.

---

## 🚨 SINAIS DE ALERTA CRÍTICOS

### ⚡ Alerta Nível 1 - AÇÃO IMEDIATA REQUERIDA

**Indicadores:**
```bash
# Qualquer ocorrência destes logs = ROLLBACK IMEDIATO
grep -E 'OUTBOX_GUARD\|level=CRITICAL\|type=handoff_violation' app.log
grep -E 'INSTANCE_GUARD\|level=CRITICAL\|type=invalid_pattern' app.log
```

**Sintomas:**
- Mensagens perdidas (planner enfileira ≥1, delivery lê 0)
- Instâncias inválidas (default, thread_*) sendo utilizadas
- Estado inconsistente entre Planner e Delivery

**Tempo de Resposta**: < 2 minutos

---

### ⚠️ Alerta Nível 2 - MONITORAR INTENSIVAMENTE

**Indicadores:**
```bash
# Taxa de falhas > 5%
grep -E 'DELIVERY_TRACE\|action=result\|status=failed' app.log | wc -l

# Verificar taxa de sucesso
python3 scripts/monitoring_commands.py delivery
```

**Sintomas:**
- Taxa de entrega < 95%
- Aumento súbito de falhas de entrega
- Timeouts ou erros de conectividade Evolution API

**Tempo de Resposta**: < 5 minutos

---

## 🔄 PROCEDIMENTOS DE ROLLBACK

### Rollback Nível 1: Kill-Switch (< 30 segundos)

```bash
# 1. ATIVAR KILL-SWITCH IMEDIATAMENTE
export DELIVERY_DISABLE=true

# 2. RESTART APLICAÇÃO
sudo systemctl restart kumon-assistant
# OU
pkill -f uvicorn && sleep 2 && python -m uvicorn main:app --host 0.0.0.0 --port 8000 &

# 3. VERIFICAR STATUS
curl -s http://localhost:8000/health | jq '.delivery_disabled'
# Deve retornar: true

# 4. CONFIRMAR NO LOG
tail -5 app.log | grep "DELIVERY_DISABLE=true"
```

**Resultado**: Mensagens ainda são processadas mas não enviadas via WhatsApp.

---

### Rollback Nível 2: Flags V1 (< 2 minutos)

```bash
# 1. DESATIVAR ENFORCEMENT V2
export OUTBOX_V2_ENFORCED=false
export TEMPLATE_VARIABLE_POLICY_V2=false
export STRICT_ENUM_STAGESTEP=false

# 2. ATIVAR MODO SOMBRA (comparação)
export ROUTER_V2_SHADOW=true

# 3. RESTART APLICAÇÃO
sudo systemctl restart kumon-assistant

# 4. VERIFICAR FALLBACK
python3 scripts/production_flags.py status
```

**Resultado**: Sistema volta ao comportamento V1 com V2 rodando em modo sombra.

---

### Rollback Nível 3: Código Anterior (< 5 minutos)

```bash
# 1. GIT ROLLBACK
git log --oneline -5  # Identificar commit anterior estável
git reset --hard COMMIT_HASH_ANTERIOR

# 2. REBUILD & RESTART
pip install -r requirements.txt
sudo systemctl restart kumon-assistant

# 3. VERIFICAR SAÚDE
curl -s http://localhost:8000/health
python3 scripts/monitoring_commands.py health
```

**Resultado**: Sistema completamente revertido para versão anterior.

---

## 📋 CHECKLIST DE EMERGÊNCIA

### ✅ Durante Crise (Execute nesta ordem)

1. **[ ] Identificar o problema** (2 min)
   ```bash
   python3 scripts/monitoring_commands.py health
   tail -20 app.log | grep -E 'CRITICAL|ERROR|FAIL'
   ```

2. **[ ] Decidir nível de rollback** (1 min)
   - Nível 1: Kill-switch (problemas de entrega)
   - Nível 2: Flags V1 (problemas de handoff/instance)  
   - Nível 3: Código anterior (problemas estruturais)

3. **[ ] Executar rollback** (conforme procedimento acima)

4. **[ ] Verificar estabilização** (3 min)
   ```bash
   # Monitorar por 3 minutos
   watch -n 10 'python3 scripts/monitoring_commands.py delivery'
   ```

5. **[ ] Comunicar status** (2 min)
   - Equipe técnica: Status atual + ETA
   - Stakeholders: Impacto + ações tomadas

6. **[ ] Análise post-incident** (após estabilização)

---

### ✅ Pós-Rollback (Verificação)

1. **[ ] Confirmar sistema estável**
   ```bash
   python3 scripts/monitoring_commands.py health
   # Deve mostrar: 🎯 SYSTEM HEALTHY
   ```

2. **[ ] Testar funcionalidade básica**
   ```bash
   # Com kill-switch ativado, apenas processar (não enviar)
   export SMOKE_TEST_PHONE="5511999999999"
   python3 scripts/smoke_test_e2e.py send
   ```

3. **[ ] Documentar incident**
   ```bash
   python3 scripts/monitoring_commands.py report
   # Gera report detalhado para análise
   ```

---

## 🔍 COMANDOS DE DIAGNÓSTICO RÁPIDO

### Verificação em 30 segundos

```bash
# Status geral do sistema
python3 scripts/monitoring_commands.py health

# Últimas mensagens críticas
tail -20 app.log | grep -E 'CRITICAL|OUTBOX_GUARD|INSTANCE_GUARD'

# Taxa de entrega atual
python3 scripts/monitoring_commands.py delivery

# Estado das flags de produção
python3 scripts/production_flags.py status
```

---

### Verificação em 60 segundos

```bash
# Handoff integrity
python3 scripts/monitoring_commands.py handoff

# Instance resolution
python3 scripts/monitoring_commands.py instances

# Recent failures
python3 scripts/monitoring_commands.py failures

# Evolution API status
curl -s http://localhost:8080/instance/kumon_assistant | jq '.instance.status'
```

---

## 📞 CONTATOS DE EMERGÊNCIA

### Escalação Técnica
1. **Desenvolvedor Principal**: [Contato]
2. **Arquiteto de Sistema**: [Contato]
3. **DevOps/Infra**: [Contato]

### Escalação de Negócio
1. **Gerente de Produto**: [Contato]
2. **Responsável Kumon**: [Contato]

---

## 🔧 RECOVERY SCRIPTS

### Script de Recovery Automático

```bash
#!/bin/bash
# emergency_recovery.sh

echo "🚨 INICIANDO RECOVERY AUTOMÁTICO..."

# Verificar problemas críticos
CRITICAL_ISSUES=$(grep -c 'OUTBOX_GUARD\|INSTANCE_GUARD.*CRITICAL' app.log)

if [ "$CRITICAL_ISSUES" -gt 0 ]; then
    echo "❌ $CRITICAL_ISSUES problemas críticos detectados"
    echo "🔧 Ativando kill-switch..."
    
    export DELIVERY_DISABLE=true
    sudo systemctl restart kumon-assistant
    
    echo "✅ Kill-switch ativado"
    echo "📞 CONTATE A EQUIPE TÉCNICA IMEDIATAMENTE"
else
    echo "✅ Nenhum problema crítico detectado"
fi

# Gerar report
python3 scripts/monitoring_commands.py report

echo "📊 Report de recovery gerado"
```

### Script de Validação Pós-Recovery

```bash
#!/bin/bash
# validate_recovery.sh

echo "🔍 VALIDANDO RECOVERY..."

# Verificar sistema
python3 scripts/monitoring_commands.py health

if [ $? -eq 0 ]; then
    echo "✅ Sistema estável após recovery"
    
    # Smoke test básico (se delivery não estiver desabilitado)
    if [ "$DELIVERY_DISABLE" != "true" ]; then
        echo "🧪 Executando smoke test..."
        python3 scripts/smoke_test_e2e.py test
        
        if [ $? -eq 0 ]; then
            echo "🎯 Recovery COMPLETO - sistema operacional"
        else
            echo "⚠️ Recovery parcial - smoke test falhou"
        fi
    else
        echo "⚠️ Kill-switch ativo - sistema em modo seguro"
    fi
else
    echo "❌ Sistema ainda instável - recovery falhou"
    exit 1
fi
```

---

## 📊 METRICAS DE RECOVERY

### SLA de Recovery
- **Kill-Switch**: < 30 segundos
- **Rollback Flags**: < 2 minutos  
- **Rollback Código**: < 5 minutos
- **Diagnóstico**: < 1 minuto
- **Comunicação**: < 2 minutos

### Critérios de Sucesso
- **0** ocorrências de logs `CRITICAL`
- **≥95%** taxa de entrega após recovery
- **<1%** perda de mensagens durante incident
- **Sistema estável** por ≥15 minutos pós-recovery

---

## 🎯 PREPARAÇÃO PARA EMERGÊNCIAS

### Antes do Go-Live

1. **[ ] Scripts de emergência testados**
   ```bash
   # Testar scripts em ambiente não-crítico
   chmod +x emergency_recovery.sh validate_recovery.sh
   ./emergency_recovery.sh --dry-run
   ```

2. **[ ] Contatos atualizados e confirmados**

3. **[ ] Equipe treinada nos procedimentos**

4. **[ ] Monitoramento automatizado configurado**
   ```bash
   # Cron para alertas automáticos
   */5 * * * * python3 scripts/monitoring_commands.py health || /path/to/alert_team.sh
   ```

### Durante Go-Live

1. **[ ] Monitor dedicado nos logs**
   ```bash
   tail -f app.log | grep -E 'CRITICAL|OUTBOX_GUARD|INSTANCE_GUARD'
   ```

2. **[ ] Scripts de emergência carregados no terminal**

3. **[ ] Canais de comunicação abertos**

4. **[ ] Backup do commit anterior identificado**
   ```bash
   git log --oneline -5  # Manter hash do commit seguro
   ```

---

**STATUS**: 🚨 **PROCEDIMENTOS DE EMERGÊNCIA PRONTOS PARA GO-LIVE**