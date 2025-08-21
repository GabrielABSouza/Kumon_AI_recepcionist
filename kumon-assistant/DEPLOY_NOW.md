# 🚀 Deploy Kumon Assistant para Railway - GUIA RÁPIDO

## Pré-requisitos Concluídos ✅
- Railway CLI instalado
- Código commitado e pushado para GitHub
- Dockerfile e railway.json configurados

## Passos para Deploy

### 1. Login no Railway
```bash
railway login
```
(Abrirá o navegador para autenticação)

### 2. Criar novo projeto ou conectar ao existente

**Opção A - Novo Projeto:**
```bash
railway new kumon-assistant-production
```

**Opção B - Projeto Existente:**
```bash
railway link
```
(Selecione o projeto Kumon Assistant)

### 3. Configurar as variáveis de ambiente

```bash
# Configurar todas as secrets necessárias
railway variables set OPENAI_API_KEY="sua-chave-aqui"
railway variables set EVOLUTION_API_KEY="B6D711FCDE4D4FD5936544120E713976"
railway variables set POSTGRES_PASSWORD="senha-segura"
railway variables set REDIS_PASSWORD="senha-segura"
railway variables set LANGSMITH_API_KEY="sua-chave-langsmith"
railway variables set LANGSMITH_PROJECT="kumon-assistant"
railway variables set LANGCHAIN_TRACING_V2="true"
railway variables set USE_SECURE_PROCESSING="true"
railway variables set SECURE_ROLLOUT_PERCENTAGE="100.0"
railway variables set MEMORY_ENABLE_SYSTEM="true"
```

### 4. Deploy da aplicação

```bash
# Copiar Dockerfile de produção
cp Dockerfile.production Dockerfile

# Deploy
railway up --service kumon-assistant
```

### 5. Configurar domínio público

```bash
# Gerar domínio público Railway
railway domain

# Ou configurar domínio customizado
railway domain set kumon.seudominio.com
```

### 6. Verificar deployment

```bash
# Ver logs
railway logs

# Ver status
railway status
```

### 7. Testar endpoints

Após o deploy, teste:
- Health: https://seu-app.railway.app/api/v1/health
- Docs: https://seu-app.railway.app/docs
- Evolution: https://seu-app.railway.app/api/v1/evolution/health

### 8. Configurar Evolution API

Na Evolution API, configure o webhook para:
```
https://seu-app.railway.app/api/v1/evolution/webhook
```

## Serviços Necessários no Railway

1. **PostgreSQL** - Para persistência de conversações
2. **Redis** - Para cache e sessões
3. **Kumon Assistant** - Aplicação principal

## Monitoramento

- Logs: `railway logs --tail`
- Métricas: Dashboard do Railway
- Health: Endpoint /api/v1/health

## Troubleshooting

Se houver erros:
1. Verifique logs: `railway logs`
2. Verifique variáveis: `railway variables`
3. Verifique status: `railway status`

## 🎯 Próximos Passos

Após deploy bem-sucedido:
1. Configure Evolution API com novo webhook URL
2. Teste integração WhatsApp
3. Configure monitoramento
4. Ative alertas de saúde

---

**IMPORTANTE**: Guarde a URL do Railway para configurar no Evolution API!