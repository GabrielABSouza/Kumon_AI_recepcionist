# 🚀 PLANO GO-LIVE - Sistema Kumon Assistant V2

**OBJETIVO**: Deploy seguro do sistema com handoff Planner→Outbox→Delivery, resolução determinística WhatsApp e observabilidade estruturada.

---

## 📋 PASSO 1: FLAGS DE PRODUÇÃO

### Flags Obrigatórias
```bash
# Enforcement crítico
export OUTBOX_V2_ENFORCED=true
export TEMPLATE_VARIABLE_POLICY_V2=true
export STRICT_ENUM_STAGESTEP=true

# Kill-switch de segurança
export DELIVERY_DISABLE=false  # true para rollback rápido

# Opcional - desligar sombra quando confiante
export ROUTER_V2_SHADOW=false  # iniciar com true para comparação
```

### Verificação das Flags
```bash
# Confirmar que as variáveis estão definidas
echo "OUTBOX_V2_ENFORCED=$OUTBOX_V2_ENFORCED"
echo "TEMPLATE_VARIABLE_POLICY_V2=$TEMPLATE_VARIABLE_POLICY_V2" 
echo "STRICT_ENUM_STAGESTEP=$STRICT_ENUM_STAGESTEP"
echo "DELIVERY_DISABLE=$DELIVERY_DISABLE"
```

---

## 📱 PASSO 2: INSTÂNCIA WHATSAPP

### 2.1 Verificar Instância no Evolution API
```bash
# Verificar se kumon_assistant existe
curl -X GET "http://localhost:8080/instance/kumon_assistant" \
  -H "apikey: YOUR_API_KEY"

# Resposta esperada: {"instance": {"instanceName": "kumon_assistant", "status": "open"}}
```

### 2.2 Criar Instância (se necessário)
```bash
# Criar instância kumon_assistant
curl -X POST "http://localhost:8080/instance/create" \
  -H "Content-Type: application/json" \
  -H "apikey: YOUR_API_KEY" \
  -d '{
    "instanceName": "kumon_assistant",
    "qrcode": true,
    "integration": "WHATSAPP-BAILEYS"
  }'
```

### 2.3 Teste de Conectividade
```bash
# Ping básico para validar
curl -X GET "http://localhost:8080/instance/kumon_assistant/connectionState" \
  -H "apikey: YOUR_API_KEY"

# Status esperado: "open"
```

### 2.4 Validação do Mapeamento
- ✅ Webhook → `envelope.meta.instance = "kumon_assistant"`
- ✅ State → `state.channel.instance = "kumon_assistant"`
- ❌ **NUNCA** usar `default` ou `thread_*`

---

## 🗄️ PASSO 3: CHECKPOINTER POSTGRES

### 3.1 Configuração Database
```bash
# Confirmar DATABASE_URL
echo "DATABASE_URL=$DATABASE_URL"

# Deve apontar para Railway Postgres:
# postgresql://postgres:XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR@yamabiko.proxy.rlwy.net:20931/railway

# Flag checkpointer
export CHECKPOINTER=postgres
```

### 3.2 Verificação no Boot
```bash
# Iniciar aplicação e verificar logs
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# NÃO deve aparecer nos logs:
# ❌ "Using memory checkpointer"
# ✅ Deve aparecer: "Using PostgreSQL checkpointer"
```

### 3.3 Teste de Persistência
```bash
# Verificar tabelas de checkpoint
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "\dt *checkpoint*"
```

---

## 📝 PASSO 4: TEMPLATES

### 4.1 Linter Template (Bloquear Variáveis)
```bash
# Executar pre-commit hooks
pre-commit run --all-files

# Verificar que não existem:
# ❌ {{variavel}}
# ❌ {ALL_CAPS}
# ❌ templates com kind: configuration no gate
```

### 4.2 Validação Template Safety
```bash
# Verificar templates neutros ativos
python -c "
from app.prompts.template_loader import template_loader
fallback = template_loader.load_template('kumon:greeting:response:general:neutral')
print('Fallback neutro:', fallback[0][:50])
"
```

### 4.3 Teste Front-matter
```bash
# Confirmar que templates configuration são bloqueados
python -c "
from app.core.safety.template_safety_v2 import check_and_sanitize
result = check_and_sanitize('Test config template', 'kumon:system:base:identity')
print('Template bloqueado:', result['fallback_used'])
"
```

---

## 🧪 PASSO 5: SMOKE TEST E2E

### 5.1 Preparação
```bash
# Limpar logs anteriores
> app.log

# Iniciar aplicação
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 5.2 Envio de Teste
**Enviar "oi" do seu WhatsApp para o número da instância kumon_assistant**

### 5.3 Verificação dos Logs (Sequência Esperada)

#### ✅ Logs Obrigatórios (nesta ordem):
```bash
# 1. Planner enfileira mensagem
grep -E 'OUTBOX_TRACE\|phase=planner' app.log
# Esperado: count=1

# 2. Delivery lê mensagem (mesmo conv|idem, mesmo state_id/outbox_id)
grep -E 'OUTBOX_TRACE\|phase=delivery' app.log  
# Esperado: count=1, mesmo conv+idem do planner

# 3. Instância resolvida corretamente
grep -E 'INSTANCE_TRACE\|source=meta\|instance=kumon_assistant' app.log
# Esperado: source=meta, instance=kumon_assistant

# 4. Envio WhatsApp
grep -E 'DELIVERY_TRACE\|action=send\|instance=kumon_assistant' app.log
# Esperado: action=send, instance=kumon_assistant

# 5. Resultado sucesso
grep -E 'DELIVERY_TRACE\|action=result\|status=success\|http=200' app.log
# Esperado: status=success, http=200
```

#### ❌ Logs Proibidos (devem estar VAZIOS):
```bash
# Violações críticas
grep -E 'OUTBOX_GUARD\|level=CRITICAL\|type=handoff_violation' app.log
# Deve ser VAZIO

grep -E 'INSTANCE_GUARD\|level=CRITICAL\|type=invalid_pattern' app.log  
# Deve ser VAZIO

# Instâncias inválidas
grep -E 'instance=default|instance=thread_' app.log
# Deve ser VAZIO
```

---

## 📊 PASSO 6: ROLLOUT GRADUAL

### 6.1 Estratégia de Deploy
```
0% → 10% → 50% → 100%
```

### 6.2 Monitoramento por Fase

#### Fase 1: 10% (Primeiros usuários)
```bash
# Monitorar por 30 minutos
watch -n 30 'grep -E "DELIVERY_TRACE\|action=result" app.log | tail -20'

# Verificar taxa de sucesso
grep -E 'DELIVERY_TRACE\|action=result' app.log | awk -F'|' '
  /status=success/ {success++}
  /status=failed/ {failed++}
  END {total=success+failed; if(total>0) print "Success rate:", (success/total)*100"%"}
'
```

#### Fase 2: 50% (Escala média)
```bash
# Guard-rails críticos
grep -E 'delivery_failure_rate.*exceeds.*critical' app.log
# Se aparecer algo: ROLLBACK IMEDIATO
```

#### Fase 3: 100% (Full rollout)
```bash
# Monitoramento contínuo
tail -f app.log | grep -E 'OUTBOX_GUARD\|INSTANCE_GUARD\|delivery_failure_rate'
```

---

## 🚨 PROCEDIMENTOS DE EMERGÊNCIA

### Rollback Imediato
```bash
# Kill-switch de entrega
export DELIVERY_DISABLE=true

# Restart aplicação
sudo systemctl restart kumon-assistant
# ou
pkill -f uvicorn && python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### Sinais de Alerta
- `OUTBOX_GUARD|level=CRITICAL|type=handoff_violation` (qualquer ocorrência)
- `INSTANCE_GUARD|level=CRITICAL|type=invalid_pattern` (qualquer ocorrência)  
- Taxa de falhas > 5% em `DELIVERY_TRACE|action=result|status=failed`
- Mensagens perdidas (planner count≥1, delivery count=0)

---

## 📈 COMANDOS DE VERIFICAÇÃO CONTÍNUA

### Handoff Íntegro
```bash
# Detectar mismatches (planner enfileira≥1, delivery lê 0)
grep -E 'OUTBOX_TRACE\|' app.log | awk -F'[=| ]' '
  /phase=planner/ { k=$6"|" $8; p[k]=$12 }
  /phase=delivery/ { k=$6"|" $8; d=$12; if (k in p && p[k] > 0 && d == 0) print "❌ MISMATCH conv=" $6 " idem=" $8 " planner=" p[k] " delivery=" d }
'
```

### State ID Consistente
```bash
# Verificar se state_id/outbox_id são os mesmos
grep -E 'OUTBOX_TRACE\|' app.log | awk -F'[=| ]' '
  /phase=planner/ { k=$6"|" $8; ps[k]=$10; po[k]=$12 }
  /phase=delivery/ { k=$6"|" $8; if (ps[k]!="" && (ps[k]!=$10 || po[k]!=$12)) {
      print "❌ ID-DIFF conv=" $6 " idem=" $8 " state_id(planner)=" ps[k] " state_id(delivery)=" $10 " outbox_id(planner)=" po[k] " outbox_id(delivery)=" $12
  } }
'
```

### Instâncias Inválidas
```bash
# Deve retornar VAZIO
grep -E 'INSTANCE_GUARD\|level=CRITICAL\|type=invalid_pattern' app.log
```

### Taxa de Falhas
```bash
# Monitorar falhas de entrega
grep -E 'DELIVERY_TRACE\|action=result\|status=failed' app.log | wc -l
```

---

## ✅ CRITÉRIOS DE ACEITE EM PRODUÇÃO

1. **0 ocorrências** de `OUTBOX_GUARD|...handoff_violation`
2. **0 ocorrências** de `INSTANCE_GUARD|...invalid_pattern`  
3. **≥95% success rate** em `DELIVERY_TRACE|action=result|status=success`
4. **Nenhum template** de configuração vazando
5. **Nenhuma variável** `{{...}}` ou `{ALL_CAPS}` no texto final
6. **State ID consistente** entre Planner e Delivery para mesmo conv|idem

---

## 🎯 CHECKLIST FINAL

### Pré-Deploy
- [ ] Flags de produção configuradas
- [ ] Instância WhatsApp `kumon_assistant` ativa
- [ ] Checkpointer Postgres funcionando
- [ ] Templates validados sem variáveis
- [ ] Smoke test E2E passou

### Durante Deploy
- [ ] Logs estruturados funcionando
- [ ] Comandos grep/jq operacionais
- [ ] Taxa de sucesso ≥95%
- [ ] Zero violações críticas
- [ ] Kill-switch testado

### Pós-Deploy
- [ ] Monitoramento contínuo ativo
- [ ] Alertas configurados
- [ ] Equipe treinada nos comandos
- [ ] Procedimentos de rollback documentados
- [ ] Métricas de baseline estabelecidas

**STATUS**: 🚀 **PRONTO PARA GO-LIVE**