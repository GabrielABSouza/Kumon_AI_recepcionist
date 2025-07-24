# 🚀 Guia de Deploy - Kumon AI Receptionist

## ⚡ Configuração Híbrida Otimizada

Este deploy utiliza uma **configuração híbrida otimizada** baseada em análise técnica detalhada:

### 📊 **Recursos por Serviço**
- **Kumon Assistant**: 1.5 vCPU / 1.5Gi RAM (sweet spot ML workloads)
- **Qdrant**: 1 vCPU / 1Gi RAM (vector database)
- **Evolution API**: 1 vCPU / 1Gi RAM (WhatsApp integration)
- **PostgreSQL**: db-f1-micro (minimal database needs)

### 💰 **Estimativa de Custos**
- **Total mensal**: ~$116/mês (configuração otimizada)
- **Economia**: $708/ano vs configuração anterior
- **Startup time**: 7-10 minutos (aceitável para ML apps)
- **Success rate**: ~85% (production ready)

### 🎯 **Estratégia ML**
- **Embeddings**: Locais (sentence-transformers) - GRATUITO
- **Chat**: OpenAI GPT-4o-mini - Custo-efetivo
- **Cache**: Redis inteligente para otimização
- **Fallback**: TF-IDF como último recurso

---

## 📋 Pré-requisitos

### 1. Ferramentas Necessárias

- **Google Cloud SDK** (gcloud CLI)
- **Docker** (para builds locais)
- **Git** (para versionamento)

### 2. Contas e Permissões

- **Conta Google Cloud** com projeto ativo
- **APIs habilitadas**:
  - Cloud Run API
  - Cloud Build API
  - Cloud SQL Admin API
  - Secret Manager API
  - Artifact Registry API

## 🔐 Configuração de Segurança

### 1. Configurar Variáveis de Ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite com suas credenciais reais
nano .env

# Exporte as variáveis
source .env
export OPENAI_API_KEY
export EVOLUTION_API_KEY
export DB_ROOT_PASSWORD
export DB_USER_PASSWORD
```

### 2. Configurar Credenciais do Google Cloud

```bash
# Faça login no Google Cloud
gcloud auth login

# Configure o projeto
gcloud config set project YOUR_PROJECT_ID

# Configure as credenciais da aplicação
gcloud auth application-default login
```

### 3. Colocar Credenciais no Local Correto

```bash
# Coloque o arquivo google-service-account.json em:
cp /path/to/your/google-service-account.json temp/credentials/
```

## 🏗️ Estrutura de Deploy

### Arquivos de Deploy (Organizados)

```
infrastructure/
├── docker/
│   ├── app/Dockerfile              # Kumon Assistant
│   ├── evolution-api/Dockerfile    # Evolution API
│   └── qdrant/Dockerfile          # Vector Database
├── gcp/
│   ├── cloudbuild.yaml            # Build configuration
│   └── deploy.sh                  # Deploy script
└── config/
    ├── .dockerignore              # Docker ignore rules
    └── .gcloudignore             # Cloud Build ignore rules
```

## 🚀 Deploy em Produção

### 1. Deploy Automático (Recomendado)

```bash
# Execute o script de deploy
./infrastructure/gcp/deploy.sh
```

### 2. Deploy Manual (Passo a Passo)

```bash
# 1. Habilitar APIs
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    sqladmin.googleapis.com

# 2. Executar build
gcloud builds submit \
    --config=infrastructure/gcp/cloudbuild.yaml \
    --substitutions=_OPENAI_API_KEY="$OPENAI_API_KEY",_EVOLUTION_API_KEY="$EVOLUTION_API_KEY",_DB_ROOT_PASSWORD="$DB_ROOT_PASSWORD",_DB_USER_PASSWORD="$DB_USER_PASSWORD" \
    --region=us-central1
```

## 🔍 Verificação do Deploy

### 1. Verificar Serviços

```bash
# Listar serviços do Cloud Run
gcloud run services list --region=us-central1

# Verificar status específico
gcloud run services describe kumon-assistant --region=us-central1
```

### 2. Testar Endpoints

```bash
# Obter URL do serviço
KUMON_URL=$(gcloud run services describe kumon-assistant --region=us-central1 --format="value(status.url)")

# Testar health check
curl $KUMON_URL/api/v1/health

# Testar documentação
echo "Docs: $KUMON_URL/docs"
```

### 3. Verificar Logs

```bash
# Ver logs em tempo real
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=kumon-assistant"

# Ver logs específicos
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=kumon-assistant" --limit=50
```

## 🛠️ Desenvolvimento Local

### 1. Usando Docker Compose

```bash
# Subir ambiente local
docker-compose -f infrastructure/docker/compose/docker-compose.yml up -d

# Ver logs
docker-compose -f infrastructure/docker/compose/docker-compose.yml logs -f
```

### 2. Desenvolvimento Python

```bash
# Instalar dependências
pip install -r infrastructure/config/requirements.txt

# Executar aplicação
cd src/
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 🔧 Troubleshooting

### Problemas Comuns

#### 1. Erro de Credenciais

```bash
# Verificar autenticação
gcloud auth list

# Reautenticar se necessário
gcloud auth login
gcloud auth application-default login
```

#### 2. Erro de Permissões

```bash
# Verificar IAM
gcloud projects get-iam-policy YOUR_PROJECT_ID

# Adicionar permissões necessárias
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:your-email@domain.com" \
    --role="roles/run.admin"
```

#### 3. Erro de Build

```bash
# Verificar logs do build
gcloud builds list --limit=5

# Ver detalhes do build específico
gcloud builds log BUILD_ID --region=us-central1
```

#### 4. Erro de Quota

```bash
# Verificar quotas
gcloud compute project-info describe --project=YOUR_PROJECT_ID

# Solicitar aumento de quota via Console
```

## 📊 Monitoramento

### 1. Métricas

```bash
# Acessar métricas via Console
echo "https://console.cloud.google.com/monitoring/dashboards"

# Métricas específicas do Cloud Run
echo "https://console.cloud.google.com/run"
```

### 2. Alertas

```bash
# Criar alerta de erro
gcloud alpha monitoring alert-policies create \
    --display-name="Kumon Assistant High Error Rate" \
    --condition-display-name="High Error Rate" \
    --condition-filter="resource.type=\"cloud_run_revision\""
```

## 🔄 Atualizações

### 1. Deploy de Nova Versão

```bash
# Fazer commit das mudanças
git add .
git commit -m "feat: nova funcionalidade"

# Deploy automático
./infrastructure/gcp/deploy.sh
```

### 2. Rollback

```bash
# Listar revisões
gcloud run revisions list --service=kumon-assistant --region=us-central1

# Fazer rollback para revisão específica
gcloud run services update-traffic kumon-assistant \
    --to-revisions=REVISION_NAME=100 \
    --region=us-central1
```

## 🆘 Suporte

### Logs Importantes

- **Cloud Build**: `gcloud builds log BUILD_ID`
- **Cloud Run**: `gcloud logging read "resource.type=cloud_run_revision"`
- **Cloud SQL**: `gcloud sql operations list --instance=evolution-postgres`

### Comandos de Debug

```bash
# Status geral
gcloud run services list --region=us-central1

# Configuração do serviço
gcloud run services describe kumon-assistant --region=us-central1

# Variáveis de ambiente
gcloud run services describe kumon-assistant --region=us-central1 --format="export"
```

---

**🎉 Deploy concluído com sucesso!**

Acesse a documentação da API em: `https://your-service-url/docs`
