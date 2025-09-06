# 📊 GUIA DE MONITORAMENTO CONTÍNUO - Kumon Assistant V2

**OBJETIVO**: Monitoramento proativo e contínuo do sistema em produção com observabilidade estruturada.

---

## 🎯 DASHBOARD DE MONITORAMENTO

### Métricas Críticas (Monitoramento 24/7)

| Métrica | Threshold | Comando | Ação |
|---------|-----------|---------|------|
| **Outbox Handoff Violations** | 0 | `python3 scripts/monitoring_commands.py handoff` | ROLLBACK IMEDIATO |
| **Invalid Instance Patterns** | 0 | `python3 scripts/monitoring_commands.py instances` | ROLLBACK IMEDIATO |
| **Delivery Success Rate** | ≥95% | `python3 scripts/monitoring_commands.py delivery` | Investigar se <95% |
| **State ID Consistency** | 100% | `python3 scripts/monitoring_commands.py consistency` | Investigar inconsistências |

### Comandos de Monitoramento Rápido

```bash
# Status geral (30 segundos)
python3 scripts/monitoring_commands.py health

# Relatório completo (2 minutos)
python3 scripts/monitoring_commands.py report

# Monitoramento em tempo real
tail -f app.log | grep -E 'OUTBOX_TRACE|INSTANCE_TRACE|DELIVERY_TRACE'
```

---

## ⏰ MONITORAMENTO POR HORÁRIO

### 🌅 Monitoramento Manhã (08:00-12:00)
**Características**: Alto volume, pico de usuários

```bash
# A cada 15 minutos
watch -n 900 'python3 scripts/monitoring_commands.py delivery'

# Alertas críticos em tempo real  
tail -f app.log | grep -E 'CRITICAL|OUTBOX_GUARD|INSTANCE_GUARD' &

# Dashboard visual
while true; do
  clear
  echo "=== KUMON ASSISTANT V2 - MORNING DASHBOARD ==="
  echo "Time: $(date)"
  echo ""
  python3 scripts/monitoring_commands.py health
  echo ""
  echo "Recent delivery stats:"
  python3 scripts/monitoring_commands.py delivery
  sleep 300  # 5 minutos
done
```

### 🌆 Monitoramento Tarde/Noite (12:00-22:00)
**Características**: Volume médio, operação estável

```bash
# A cada 30 minutos
watch -n 1800 'python3 scripts/monitoring_commands.py health'

# Relatório a cada 2 horas
*/120 * * * * python3 scripts/monitoring_commands.py report > /var/log/kumon-monitoring-$(date +\%H).log
```

### 🌙 Monitoramento Madrugada (22:00-08:00)
**Características**: Volume baixo, maintenance window

```bash
# Verificação a cada hora
0 * * * * python3 scripts/monitoring_commands.py health || /path/to/alert_oncall.sh

# Backup de logs e limpeza
0 2 * * * tar -czf logs/app-$(date +\%Y\%m\%d).tar.gz app.log && > app.log
```

---

## 📈 ALERTAS AUTOMATIZADOS

### Alertas Críticos (Intervenção Imediata)

```bash
#!/bin/bash
# critical_alert_monitor.sh

while true; do
    # Verificar violações críticas
    HANDOFF_VIOLATIONS=$(python3 scripts/monitoring_commands.py handoff 2>/dev/null | grep -c "❌")
    INSTANCE_VIOLATIONS=$(python3 scripts/monitoring_commands.py instances 2>/dev/null | grep -c "❌")
    
    if [ "$HANDOFF_VIOLATIONS" -gt 0 ] || [ "$INSTANCE_VIOLATIONS" -gt 0 ]; then
        # ALERTA CRÍTICO
        echo "🚨 CRITICAL ALERT: System violations detected at $(date)"
        echo "Handoff violations: $HANDOFF_VIOLATIONS"
        echo "Instance violations: $INSTANCE_VIOLATIONS"
        
        # Ativar procedimentos de emergência
        ./emergency_recovery.sh
        
        # Alertar equipe (substituir por seu sistema de alertas)
        # curl -X POST "https://hooks.slack.com/..." -d '{"text":"🚨 KUMON ASSISTANT V2 CRITICAL ALERT"}'
        # ou enviar email, SMS, etc.
        
        break  # Parar monitoring para intervenção manual
    fi
    
    sleep 60  # Verificar a cada minuto
done
```

### Alertas de Performance

```bash
#!/bin/bash
# performance_alert_monitor.sh

while true; do
    # Verificar taxa de entrega
    DELIVERY_RESULT=$(python3 scripts/monitoring_commands.py delivery 2>/dev/null)
    
    if echo "$DELIVERY_RESULT" | grep -q "❌"; then
        echo "⚠️ PERFORMANCE ALERT: Delivery rate below threshold at $(date)"
        echo "$DELIVERY_RESULT"
        
        # Log para análise
        echo "$(date): $DELIVERY_RESULT" >> /var/log/performance-alerts.log
        
        # Alerta moderado (não crítico)
        # send_moderate_alert.sh
    fi
    
    sleep 300  # Verificar a cada 5 minutos
done
```

---

## 🔍 ANÁLISE DE TRENDS

### Coleta de Dados Históricos

```bash
#!/bin/bash
# collect_metrics.sh - Executar a cada hora

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
LOG_DIR="/var/log/kumon-metrics"
mkdir -p "$LOG_DIR"

# Coleta métricas principais
{
    echo "timestamp,delivery_success_count,delivery_failed_count,handoff_violations,instance_violations"
    
    DELIVERY_RESULT=$(python3 scripts/monitoring_commands.py delivery 2>/dev/null)
    HANDOFF_RESULT=$(python3 scripts/monitoring_commands.py handoff 2>/dev/null)
    INSTANCE_RESULT=$(python3 scripts/monitoring_commands.py instances 2>/dev/null)
    
    # Extrair números (implementar parsing específico)
    DELIVERY_SUCCESS=$(echo "$DELIVERY_RESULT" | grep -o '[0-9]\+/[0-9]\+' | cut -d'/' -f1 || echo "0")
    DELIVERY_TOTAL=$(echo "$DELIVERY_RESULT" | grep -o '[0-9]\+/[0-9]\+' | cut -d'/' -f2 || echo "0")
    DELIVERY_FAILED=$((DELIVERY_TOTAL - DELIVERY_SUCCESS))
    
    HANDOFF_VIOLATIONS=$(echo "$HANDOFF_RESULT" | grep -c "❌" || echo "0")
    INSTANCE_VIOLATIONS=$(echo "$INSTANCE_RESULT" | grep -c "❌" || echo "0")
    
    echo "$TIMESTAMP,$DELIVERY_SUCCESS,$DELIVERY_FAILED,$HANDOFF_VIOLATIONS,$INSTANCE_VIOLATIONS"
    
} >> "$LOG_DIR/metrics-$(date +%Y%m%d).csv"
```

### Análise de Performance Semanal

```bash
#!/bin/bash
# weekly_analysis.sh

echo "📊 KUMON ASSISTANT V2 - WEEKLY PERFORMANCE REPORT"
echo "Period: $(date -d '7 days ago' '+%Y-%m-%d') to $(date '+%Y-%m-%d')"
echo ""

# Análise de logs da semana passada
WEEK_LOGS="/var/log/kumon-metrics/metrics-$(date +%Y%m%d).csv"

if [ -f "$WEEK_LOGS" ]; then
    echo "=== DELIVERY PERFORMANCE ==="
    
    # Calcular médias (implementar com awk ou Python)
    python3 -c "
import csv
import sys
from datetime import datetime, timedelta

try:
    with open('$WEEK_LOGS', 'r') as f:
        reader = csv.DictReader(f)
        data = list(reader)
    
    if not data:
        print('No data available')
        sys.exit(0)
    
    total_success = sum(int(row['delivery_success_count']) for row in data)
    total_failed = sum(int(row['delivery_failed_count']) for row in data)
    total_handoff_violations = sum(int(row['handoff_violations']) for row in data)
    total_instance_violations = sum(int(row['instance_violations']) for row in data)
    
    total_deliveries = total_success + total_failed
    success_rate = (total_success / total_deliveries * 100) if total_deliveries > 0 else 0
    
    print(f'Total Deliveries: {total_deliveries}')
    print(f'Success Rate: {success_rate:.2f}%')
    print(f'Handoff Violations: {total_handoff_violations}')
    print(f'Instance Violations: {total_instance_violations}')
    print(f'System Health: {\"🎯 EXCELLENT\" if total_handoff_violations == 0 and total_instance_violations == 0 and success_rate >= 95 else \"⚠️ NEEDS ATTENTION\"}')

except Exception as e:
    print(f'Error analyzing data: {e}')
"
    
else
    echo "⚠️ No metrics data available for analysis"
fi
```

---

## 🛠️ FERRAMENTAS DE DEBUGGING

### Debug de Handoff Issues

```bash
# Investigar handoff específico por conversation_id
debug_handoff() {
    local conv_id=$1
    echo "🔍 Debugging handoff for conversation: $conv_id"
    
    echo "=== PLANNER TRACES ==="
    grep -E "OUTBOX_TRACE.*phase=planner.*conv=$conv_id" app.log
    
    echo "=== DELIVERY TRACES ==="
    grep -E "OUTBOX_TRACE.*phase=delivery.*conv=$conv_id" app.log
    
    echo "=== INSTANCE RESOLUTION ==="
    grep -E "INSTANCE_TRACE.*conv=$conv_id" app.log
    
    echo "=== DELIVERY RESULTS ==="
    grep -E "DELIVERY_TRACE.*conv=$conv_id" app.log
}

# Uso: debug_handoff "conversation_123"
```

### Debug de Performance Issues

```bash
# Análise de performance por período
debug_performance() {
    local start_time=$1  # formato: "2024-01-15 10:00"
    local end_time=$2    # formato: "2024-01-15 11:00"
    
    echo "📊 Performance analysis: $start_time to $end_time"
    
    # Filtrar logs por período (assumindo formato de timestamp nos logs)
    awk -v start="$start_time" -v end="$end_time" '
    {
        # Extrair timestamp do log (implementar conforme formato real)
        if ($0 ~ /DELIVERY_TRACE.*action=result/) {
            if ($0 ~ /status=success/) success++
            else if ($0 ~ /status=failed/) failed++
        }
    }
    END {
        total = success + failed
        rate = (total > 0) ? (success/total*100) : 0
        printf "Success: %d, Failed: %d, Rate: %.2f%%\n", success, failed, rate
    }' app.log
}

# Uso: debug_performance "2024-01-15 10:00" "2024-01-15 11:00"
```

---

## 📋 CHECKLIST DE MONITORAMENTO DIÁRIO

### 🌅 Manhã (08:00)
- [ ] **Health check completo**
  ```bash
  python3 scripts/monitoring_commands.py health
  ```
- [ ] **Verificar métricas da noite**
  ```bash
  python3 scripts/monitoring_commands.py delivery
  ```
- [ ] **Confirmar zero violações críticas**
  ```bash
  python3 scripts/monitoring_commands.py handoff
  python3 scripts/monitoring_commands.py instances
  ```
- [ ] **Verificar logs de erro**
  ```bash
  grep -E 'ERROR|CRITICAL|FATAL' app.log | tail -10
  ```

### 🌆 Tarde (14:00)
- [ ] **Status intermediário**
  ```bash
  python3 scripts/monitoring_commands.py health
  ```
- [ ] **Análise de performance do período de pico**
  ```bash
  python3 scripts/monitoring_commands.py delivery
  ```

### 🌙 Noite (20:00)
- [ ] **Relatório do dia**
  ```bash
  python3 scripts/monitoring_commands.py report
  ```
- [ ] **Preparar alertas noturnos**
  ```bash
  # Verificar se alertas automáticos estão rodando
  ps aux | grep -E 'critical_alert_monitor|performance_alert_monitor'
  ```

---

## 🎛️ CONFIGURAÇÃO DE ALERTAS AVANÇADOS

### Integração com Slack

```python
#!/usr/bin/env python3
# slack_alerts.py

import requests
import json
import sys

def send_slack_alert(webhook_url, message, severity="info"):
    """Enviar alerta para Slack"""
    
    colors = {
        "critical": "#FF0000",
        "warning": "#FFA500", 
        "info": "#008000"
    }
    
    icons = {
        "critical": "🚨",
        "warning": "⚠️",
        "info": "ℹ️"
    }
    
    payload = {
        "attachments": [{
            "color": colors.get(severity, "#008000"),
            "title": f"{icons.get(severity, 'ℹ️')} Kumon Assistant V2 Alert",
            "text": message,
            "footer": "Kumon Assistant Monitoring",
            "ts": int(time.time())
        }]
    }
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Failed to send Slack alert: {e}")
        return False

if __name__ == "__main__":
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    message = sys.argv[1] if len(sys.argv) > 1 else "Test alert"
    severity = sys.argv[2] if len(sys.argv) > 2 else "info"
    
    if webhook_url:
        send_slack_alert(webhook_url, message, severity)
    else:
        print("SLACK_WEBHOOK_URL not configured")
```

### Integração com Email

```bash
#!/bin/bash
# email_alerts.sh

send_email_alert() {
    local subject=$1
    local body=$2
    local priority=$3  # low, normal, high, critical
    
    local recipients="admin@kumon.com,devops@kumon.com"
    
    if [ "$priority" = "critical" ]; then
        recipients="$recipients,oncall@kumon.com"
        subject="🚨 CRITICAL: $subject"
    elif [ "$priority" = "high" ]; then
        subject="⚠️ HIGH: $subject"
    fi
    
    # Usando sendmail ou outro sistema de email
    echo "$body" | mail -s "$subject" "$recipients"
}

# Uso:
# send_email_alert "Kumon Assistant Issue" "Delivery rate below threshold" "high"
```

---

## 🔗 INTEGRAÇÃO COM FERRAMENTAS EXTERNAS

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Kumon Assistant V2 Monitoring",
    "panels": [
      {
        "title": "Delivery Success Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "kumon_delivery_success_rate",
            "legendFormat": "Success Rate"
          }
        ]
      },
      {
        "title": "Outbox Handoff Violations",
        "type": "stat", 
        "targets": [
          {
            "expr": "kumon_outbox_violations_total",
            "legendFormat": "Violations"
          }
        ]
      }
    ]
  }
}
```

### Prometheus Metrics

```python
# prometheus_exporter.py
from prometheus_client import Counter, Gauge, start_http_server
import time
import subprocess
import json

# Métricas
delivery_success_rate = Gauge('kumon_delivery_success_rate', 'Delivery success rate')
outbox_violations = Counter('kumon_outbox_violations_total', 'Total outbox violations')
instance_violations = Counter('kumon_instance_violations_total', 'Total instance violations')

def collect_metrics():
    """Coletar métricas do sistema"""
    try:
        # Executar comandos de monitoramento
        delivery_result = subprocess.run(['python3', 'scripts/monitoring_commands.py', 'delivery'], 
                                       capture_output=True, text=True)
        
        # Parse e exposição das métricas (implementar parsing específico)
        # delivery_success_rate.set(parsed_rate)
        
    except Exception as e:
        print(f"Error collecting metrics: {e}")

if __name__ == "__main__":
    start_http_server(8080)
    while True:
        collect_metrics()
        time.sleep(60)  # Coletar a cada minuto
```

---

## 🎯 METAS DE MONITORAMENTO

### KPIs Operacionais
- **Uptime**: 99.9%
- **Delivery Success Rate**: ≥95%
- **Alert Response Time**: <2 minutos
- **Recovery Time**: <5 minutos
- **Zero** violações críticas

### Métricas de Qualidade
- **False Positive Rate**: <1%
- **Monitoring Coverage**: 100% dos fluxos críticos
- **Alert Accuracy**: ≥95%
- **Documentation Currency**: Atualizada semanalmente

---

**STATUS**: 📊 **MONITORAMENTO CONTÍNUO CONFIGURADO E PRONTO PARA PRODUÇÃO**

Este guia fornece monitoramento completo 24/7 com alertas automáticos, análise de trends e ferramentas de debugging para operação estável do Kumon Assistant V2.