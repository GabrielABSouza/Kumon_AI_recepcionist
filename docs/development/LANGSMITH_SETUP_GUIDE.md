# LangSmith Setup Guide

## 📋 Configuração da Conta LangSmith

### Passo 1: Criar Conta
1. Acesse https://smith.langchain.com/
2. Clique em "Go to App" ou "Sign Up"
3. Crie uma conta usando email ou GitHub

### Passo 2: Obter API Key
1. Após login, vá para Settings → API Keys
2. Clique em "Create API Key"
3. Nomeie a chave como "kumon-assistant-dev"
4. Copie a API key gerada

### Passo 3: Criar Projeto
1. No dashboard, clique em "New Project"
2. Nome do projeto: "kumon-assistant"
3. Descrição: "Kumon AI Receptionist Workflow"

### Passo 4: Configurar Variáveis
Adicione ao arquivo `.env`:
```bash
LANGSMITH_API_KEY=sua-api-key-aqui
LANGSMITH_PROJECT=kumon-assistant
LANGCHAIN_TRACING_V2=true
```

### Verificação
Execute este comando para testar a conexão:
```bash
python -c "from langsmith import Client; client = Client(); print('LangSmith conectado com sucesso!')"
```

## 🔗 Links Úteis
- Dashboard: https://smith.langchain.com/
- Documentação: https://docs.smith.langchain.com/
- API Reference: https://api.smith.langchain.com/docs/