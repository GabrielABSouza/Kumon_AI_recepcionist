# Evolution API - Guia de Solução de Problemas e Configuração

## 📋 Resumo dos Principais Erros e Soluções

Este documento documenta os principais problemas encontrados durante a configuração da Evolution API v1.7.1 e suas soluções definitivas.

---

## 🔴 Principais Erros Cometidos

### 1. **Loop "Recovering messages lost"**
**Problema:** Evolution API v1.7.4 entra em loop infinito tentando recuperar mensagens perdidas.

**Causa:** Bug conhecido na versão v1.7.4 relacionado ao cache Redis e recuperação de mensagens.

**Solução:** 
- Usar Evolution API v1.7.1 ao invés de v1.7.4
- Versão v1.7.1 não possui esse bug

### 2. **QR Code não gera**
**Problema:** Manager retorna erro "Não foi possível carregar o QR Code".

**Causa:** Loop de recuperação de mensagens impede geração do QR Code.

**Solução:**
- Usar versão v1.7.1 (sem o bug)
- Limpar volumes Docker antes de trocar versão

### 3. **Webhook não funciona**
**Problema:** Mensagens do WhatsApp não chegam na aplicação.

**Causa:** URL do webhook configurada incorretamente (localhost não funciona entre containers).

**Solução:**
- Usar `http://host.docker.internal:8000/api/v1/evolution/webhook`
- Configurar no Manager, não via API

### 4. **Configurações desnecessárias**
**Problema:** Adicionar Redis, PostgreSQL e configurações complexas desnecessariamente.

**Causa:** Tentar resolver problemas com configurações ao invés de identificar a raiz do problema.

**Solução:**
- Evolution API v1.7.1 funciona sem Redis
- Manter configuração minimalista

### 5. **Bug no fluxo de conversa - Coleta de dados**
**Problema:** Agente não coletava nome do responsável e estudante (dados obrigatórios).

**Causa:** Retorno incorreto de step nos handlers do estágio greeting.

**Solução:**
- Corrigir `return` em `_handle_greeting_stage` para incluir step correto
- Linha corrigida: `return {"message": response, "stage": state.stage.value, "step": ConversationStep.INITIAL_RESPONSE.value}`

### 6. **Bug no fluxo de agendamento**
**Problema:** Agente trava no estágio de agendamento, não pede email nem verifica agenda.

**Causa:** Retorno de step incorreto após atualizar estado da conversa.

**Solução:**
- Linha 1324: retornar `ConversationStep.TIME_SELECTION.value` em vez de `state.step.value`
- Linha 1366: retornar `ConversationStep.EMAIL_COLLECTION.value` em vez de `state.step.value`

### 7. **Bug do horário de funcionamento - Sábados**
**Problema:** Agente oferece sábados como dia disponível ("Sábado (8h-12h)") quando deveria funcionar apenas de segunda a sexta.

**Causa:** Modelo AI (GPT-4) gera espontaneamente informação incorreta sobre disponibilidade de sábados, baseado em conhecimento pré-treinado.

**Solução:**
- Adicionar instrução explícita nos prompts de sistema:
  - `/app/services/rag_engine.py` linhas 156 e 239
  - `/app/services/langchain_rag.py` linha 64
  - `/app/services/intent_classifier.py` linha 98
- Instrução adicionada: "IMPORTANTE: A unidade Kumon Vila A funciona APENAS de segunda a sexta-feira, das 8h às 18h. NÃO funcionamos aos sábados nem domingos. Nunca mencione disponibilidade aos fins de semana."

---

## ✅ Passo a Passo - Evolution API Funcionando

### **Pré-requisitos**
- Docker e Docker Compose instalados
- Chave da OpenAI válida

### **1. Configuração do Docker Compose**

```yaml
version: '3.8'

services:
  # Evolution API v1.7.1 - Versão estável
  evolution-api:
    container_name: evolution_api
    image: atendai/evolution-api:v1.7.1
    restart: always
    ports:
      - "8080:8080"
    environment:
      # Authentication
      - AUTHENTICATION_TYPE=apikey
      - AUTHENTICATION_API_KEY=${EVOLUTION_API_KEY:-development-key-change-in-production}
      
      # Server Configuration
      - SERVER_PORT=8080
      - SERVER_URL=http://localhost:8080
      
      # Instance Management - Minimal config
      - DEL_INSTANCE=true
      - DATABASE_ENABLED=false
      
      # QR Code Configuration
      - QRCODE_LIMIT=30
      - QRCODE_COLOR=#198754
      
      # Disable problematic features
      - STORE_MESSAGES=false
      - STORE_MESSAGE_UP=false
      - STORE_CONTACTS=false
      
      # Redis Configuration - Disable completely
      - REDIS_ENABLED=false
      - CACHE_REDIS_ENABLED=false
      
      # Logging
      - LOG_LEVEL=INFO
      - LOG_COLOR=true
    volumes:
      - evolution_instances:/evolution/instances
      - evolution_store:/evolution/store
    networks:
      - kumon-net

  # Qdrant Vector Database - Essential for AI
  qdrant:
    container_name: qdrant_db
    image: qdrant/qdrant:latest
    restart: always
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
      - QDRANT__SERVICE__GRPC_PORT=6334
    networks:
      - kumon-net

  # Kumon Assistant Application
  kumon-assistant:
    container_name: kumon_assistant
    build: .
    restart: always
    ports:
      - "8000:8000"
    environment:
      - EVOLUTION_API_URL=http://evolution-api:8080
      - EVOLUTION_API_KEY=${EVOLUTION_API_KEY:-development-key-change-in-production}
      - QDRANT_URL=http://qdrant:6333
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./cache:/app/cache
    depends_on:
      - evolution-api
      - qdrant
    networks:
      - kumon-net

volumes:
  evolution_instances:
  evolution_store:
  qdrant_data:

networks:
  kumon-net:
    driver: bridge
```

### **2. Configuração do Ambiente (.env)**

```env
# Evolution API Configuration
EVOLUTION_API_KEY=B6D711FCDE4D4FD5936544120E713976
EVOLUTION_API_URL=http://localhost:8080

# OpenAI Configuration
OPENAI_API_KEY=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

# Qdrant Configuration
QDRANT_URL=http://localhost:6333

# Application Configuration
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
```

### **3. Inicialização do Sistema**

```bash
# 1. Limpar volumes existentes (se necessário)
docker-compose down
docker volume prune -f

# 2. Iniciar containers
docker-compose up -d

# 3. Verificar se todos estão rodando
docker-compose ps

# 4. Aguardar inicialização (30 segundos)
sleep 30

# 5. Verificar logs da Evolution API
docker logs evolution_api --tail 10
```

### **4. Configuração da Instância WhatsApp**

**4.1. Acessar o Manager**
- URL: `http://localhost:8080/manager`
- API Key: `B6D711FCDE4D4FD5936544120E713976`

**4.2. Criar Nova Instância**
- Nome: `kumon-assistant`
- Integration: `WHATSAPP-BAILEYS`

**4.3. Configurar Webhook**
- URL: `http://host.docker.internal:8000/api/v1/evolution/webhook`
- Eventos: Marcar `MESSAGES_UPSERT` e `CONNECTION_UPDATE`
- Salvar configurações

**4.4. Gerar QR Code**
- Clicar em "Generate QR Code"
- Escanear com WhatsApp
- Aguardar conexão

### **5. Teste de Funcionamento**

```bash
# 1. Verificar status da instância
curl -X GET "http://localhost:8080/instance/connectionState/kumon-assistant" \
  -H "apikey: B6D711FCDE4D4FD5936544120E713976"

# 2. Verificar saúde do Kumon Assistant
curl http://localhost:8000/api/v1/health

# 3. Enviar mensagem de teste via WhatsApp
# Envie qualquer mensagem para o número conectado

# 4. Verificar logs de processamento
docker logs kumon_assistant --tail 20
```

---

## 🚨 Troubleshooting Rápido

### **QR Code não aparece**
1. Verificar versão: deve ser v1.7.1
2. Limpar volumes e reiniciar
3. Aguardar inicialização completa

### **Webhook não funciona**
1. URL deve ser: `http://host.docker.internal:8000/api/v1/evolution/webhook`
2. Configurar no Manager, não via API
3. Marcar evento `MESSAGES_UPSERT`

### **Instância desconecta**
1. Verificar se WhatsApp Web está aberto em outro lugar
2. Recriar instância se necessário
3. Escanear QR Code novamente

### **AI não responde**
1. Verificar logs: `docker logs kumon_assistant --tail 20`
2. Verificar chave OpenAI no .env
3. Verificar conectividade entre containers

---

## 📚 URLs Importantes

- **Evolution API**: `http://localhost:8080`
- **Manager**: `http://localhost:8080/manager`
- **Kumon Assistant**: `http://localhost:8000`
- **Health Check**: `http://localhost:8000/api/v1/health`
- **Webhook URL**: `http://host.docker.internal:8000/api/v1/evolution/webhook`

---

## 🔧 Comandos Úteis

```bash
# Reiniciar apenas Evolution API
docker-compose restart evolution-api

# Ver logs em tempo real
docker logs evolution_api --follow

# Limpar tudo e recomeçar
docker-compose down && docker volume prune -f && docker-compose up -d

# Verificar conectividade
curl http://localhost:8080/
curl http://localhost:8000/api/v1/health
```

---

## ⚠️ Não Fazer

1. **Não usar Evolution API v1.7.4** (tem bug de loop)
2. **Não usar Redis** (desnecessário e pode causar problemas)
3. **Não usar PostgreSQL** (desnecessário para funcionamento básico)
4. **Não usar localhost no webhook** (não funciona entre containers)
5. **Não configurar webhook via API** (mais complexo que pelo Manager)

---

## ✅ Conclusão

Com esta configuração minimalista usando Evolution API v1.7.1, o sistema funciona de forma estável e confiável. O segredo é manter a simplicidade e usar apenas o que é necessário.

**Configuração final que funciona:**
- Evolution API v1.7.1 (sem Redis, sem PostgreSQL)
- Webhook via Manager com URL `host.docker.internal`
- Configuração minimalista no docker-compose
- Chaves corretas no .env

Este guia deve ser seguido exatamente para evitar os problemas documentados.