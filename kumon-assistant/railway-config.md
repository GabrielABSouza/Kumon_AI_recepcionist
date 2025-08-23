# Railway Configuration Guide

## PROBLEMA IDENTIFICADO:

O `railway.json` original estava configurado incorretamente, causando problemas de conectividade entre serviços.

## PROBLEMAS ENCONTRADOS:

1. **Serviços PostgreSQL e Redis definidos no railway.json** mas não conectados automaticamente
2. **Variáveis de ambiente usando placeholders vazios** como `${{DATABASE_URL}}`
3. **Falta de detecção forçada do Railway** para ativar os fixes de ambiente

## CONFIGURAÇÃO CORRETA DO RAILWAY:

### 1. Serviços Devem Ser Criados Manualmente no Dashboard

**PostgreSQL:**
```bash
# No Railway Dashboard:
1. Add New Service → Database → PostgreSQL
2. Nome sugerido: kumon-postgres
3. A variável DATABASE_URL será criada automaticamente
```

**Redis:**  
```bash
# No Railway Dashboard:
1. Add New Service → Database → Redis
2. Nome sugerido: kumon-redis  
3. A variável REDIS_URL será criada automaticamente
```

### 2. Variáveis de Ambiente no Railway Dashboard

Configure estas variáveis **diretamente no Railway Dashboard**:

#### Obrigatórias:
```
RAILWAY_ENVIRONMENT=1
FORCE_RAILWAY_DETECTION=1
ENVIRONMENT=production
DEBUG=false
```

#### APIs:
```
OPENAI_API_KEY=sk-...
EVOLUTION_API_KEY=...
```

#### Database (Auto-geradas pelos serviços):
```
DATABASE_URL=postgresql://...  (criada pelo PostgreSQL service)
REDIS_URL=redis://...          (criada pelo Redis service)
```

### 3. Network Connectivity

No Railway v2, todos os serviços do mesmo projeto estão **automaticamente na mesma rede privada**.

**Verificação:**
- PostgreSQL: `postgres://user:pass@postgres.railway.internal:5432/db`
- Redis: `redis://redis.railway.internal:6379`

### 4. Health Checks

Configurados para verificar conectividade dos serviços:

```yaml
healthChecks:
  railway:
    path: "/api/v1/health/railway"
    timeout: 45
    interval: 120
```

## COMANDOS DE TROUBLESHOOTING:

### No Railway Deploy:

```bash
# 1. Debug environment variables
python3 railway_debug.py

# 2. Test service connectivity  
curl http://localhost:$PORT/api/v1/health/railway

# 3. Check logs for connection errors
railway logs
```

### Local Development:

```bash
# Test with Railway detection forced
export RAILWAY_ENVIRONMENT=1
export FORCE_RAILWAY_DETECTION=1
python3 railway_debug.py
```

## RESOLUÇÃO DOS PROBLEMAS:

### ✅ Correções Aplicadas:

1. **railway.json simplificado** - Remove serviços que devem ser criados manualmente
2. **Variáveis de detecção forçada** - `RAILWAY_ENVIRONMENT=1` e `FORCE_RAILWAY_DETECTION=1`
3. **Health checks otimizados** - Timeouts apropriados para Railway
4. **Debug script** - `railway_debug.py` para troubleshooting em produção

### 📋 TODO Manual no Railway Dashboard:

1. **Criar serviços PostgreSQL e Redis** manualmente
2. **Configurar variáveis de ambiente** listadas acima  
3. **Verificar conectividade** usando health checks
4. **Executar debug script** para validar setup

## ARQUITETURA FINAL:

```
Railway Project:
├── kumon-assistant (main app)
├── kumon-postgres (PostgreSQL service)  
├── kumon-redis (Redis service)
└── Private Network (conecta tudo automaticamente)
```

**Network:** Todos os serviços na mesma rede privada do Railway
**Variables:** Auto-geradas para DATABASE_URL e REDIS_URL
**Detection:** Forçada via RAILWAY_ENVIRONMENT=1