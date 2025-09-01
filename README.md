# 🤖 Kumon AI Receptionist - Enterprise Edition

> **Sistema Completo de Recepcionista Virtual Inteligente com Analytics Avançado e Tracking ML**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Evolution API](https://img.shields.io/badge/Evolution_API-2.2.3-25D366.svg)](https://evolution-api.com)
[![Google Cloud](https://img.shields.io/badge/Google_Cloud-Production-orange.svg)](https://cloud.google.com)
[![Database](https://img.shields.io/badge/PostgreSQL-15+-336791.svg)](https://postgresql.org)
[![ML Ready](https://img.shields.io/badge/ML_Ready-Analytics-purple.svg)](https://scikit-learn.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 **Visão Geral**

Sistema **enterprise-grade** de recepcionista virtual inteligente que automatiza o atendimento ao cliente via WhatsApp para unidades Kumon. Combina **IA conversacional**, **análise semântica avançada**, **tracking completo de usuários** e **pipeline de dados preparado para Machine Learning**.

### 🌟 **Diferencial Competitivo**

- **💰 Zero custo WhatsApp**: Evolution API elimina custos de $0.005-$0.009/mensagem
- **🧠 IA Híbrida**: Embeddings locais + Vertex AI + TF-IDF como fallback
- **📊 Analytics ML-Ready**: Captura completa da jornada do usuário para modelos preditivos
- **🏗️ Arquitetura Enterprise**: Estrutura profissional, escalável e manutenível
- **☁️ Cloud Otimizado**: Deploy híbrido com 70% redução de custos

---

## ✨ **Principais Funcionalidades**

### 🤖 **IA Conversacional Avançada**

- **GPT-4o-mini**: Respostas naturais otimizadas para custo
- **Semantic Search**: Busca semântica multilíngue com Sentence Transformers
- **Context Management**: Gerenciamento inteligente de contexto de conversação
- **Hybrid Embeddings**: Local + Cloud com fallback automático

### 📱 **WhatsApp Business Completo**

- **Evolution API 2.2.3**: Integração WhatsApp gratuita e completa
- **Multi-instância**: Suporte a múltiplas unidades Kumon
- **Media Support**: Texto, imagens, áudio e documentos
- **Real-time Processing**: Processamento em tempo real via webhooks

### 📊 **Analytics & Machine Learning**

- **🎯 User Journey Tracking**: Captura completa da jornada do usuário
- **📈 Conversion Funnel**: Análise detalhada de funil de conversão
- **🔮 ML-Ready Data**: Estrutura otimizada para modelos preditivos
- **📊 Business Intelligence**: Métricas de negócio e KPIs automáticos

### 🏢 **Gestão de Negócio**

- **📅 Google Calendar**: Agendamento automático com detecção de conflitos
- **👥 Lead Management**: Sistema completo de gestão de leads
- **🎓 Student Tracking**: Acompanhamento de alunos e progressão
- **💳 Payment Integration**: Controle de pagamentos e mensalidades

---

## 🏗️ **Arquitetura Enterprise**

### 📁 **Estrutura do Projeto (Reorganizada)**

```
📦 kumon-assistant/
├── 📁 app/                          # 🔥 APLICAÇÃO PRINCIPAL
│   ├── api/                         # Endpoints FastAPI
│   ├── clients/                     # Clientes externos (Google, Evolution)
│   ├── core/                        # Configurações centrais
│   ├── models/                      # Modelos de dados
│   ├── services/                    # Lógica de negócio
│   └── utils/                       # Utilitários
│
├── 📁 infrastructure/               # 🚀 INFRAESTRUTURA & DEPLOY
│   ├── docker/                      # Dockerfiles organizados
│   │   ├── app/Dockerfile           # Kumon Assistant
│   │   ├── evolution-api/           # Evolution API customizada
│   │   └── qdrant/                  # Vector Database
│   ├── gcp/                         # Configurações Google Cloud
│   │   ├── cloudbuild.yaml          # Build principal
│   │   └── deploy.sh                # Script de deploy
│   ├── sql/                         # 🗄️ SCHEMAS DE BANCO
│   │   ├── evolution_schema.sql     # Evolution API (31 tabelas)
│   │   ├── kumon_business_schema.sql # Business Logic (6 tabelas)
│   │   └── user_journey_ml_schema.sql # ML Analytics (4 tabelas)
│   └── config/                      # Configurações
│
├── 📁 docs/                         # 📚 DOCUMENTAÇÃO ORGANIZADA
│   ├── deployment/                  # Guias de deploy
│   │   ├── DEPLOY_GUIDE.md          # Guia principal de deploy
│   │   └── EVOLUTION_API_SETUP.md   # Setup Evolution API
│   ├── development/                 # Documentação técnica
│   │   ├── EMBEDDING_SYSTEM_README.md # Sistema de embeddings
│   │   └── PROJECT_REORGANIZATION_COMPLETED.md # Reorganização
│   ├── analysis/                    # 📊 ESTUDOS TÉCNICOS
│   │   ├── GCP_NATIVE_MIGRATION_STUDY.md # Migração GCP
│   │   ├── KUMON_ASSISTANT_REQUIREMENTS_STUDY.md # Requisitos
│   │   └── EXECUTIVE_SUMMARY.md     # Resumo executivo
│   └── security/                    # Documentação de segurança
│
├── 📁 scripts/                      # 🔧 SCRIPTS ORGANIZADOS
│   ├── deployment/                  # Scripts de deploy
│   │   ├── configure_env_vars.sh    # Configuração de ambiente
│   │   └── prepare_and_deploy.sh    # Deploy automatizado
│   └── maintenance/                 # Scripts de manutenção
│       ├── ingest_docs.py           # Ingestão de documentos
│       └── setup_embeddings.py     # Setup de embeddings
│
└── 📁 tests/                        # 🧪 TESTES
    ├── unit/                        # Testes unitários
    ├── integration/                 # Testes de integração
    └── e2e/                         # Testes end-to-end
```

### 🗄️ **Arquitetura de Dados Completa**

#### **Evolution API Schema (31 Tabelas)**

```sql
-- Core WhatsApp Integration
Instance, Message, Contact, Chat, Session

-- Advanced Features
Webhook, Websocket, Media, Label, Template

-- AI Integration
OpenaiBot, OpenaiSetting, OpenaiCreds

-- Business Integrations
Chatwoot, Typebot, Flowise, Dify

-- And 17 more specialized tables...
```

#### **Kumon Business Schema (6 Tabelas)**

```sql
-- 👥 Customer Management
leads              -- Potential customers from WhatsApp
students           -- Enrolled students
appointments       -- Scheduled meetings

-- 🤖 AI Operations
conversation_analysis    -- AI insights from conversations
automated_responses     -- AI responses tracking
business_metrics       -- KPIs and performance metrics
```

#### **ML Analytics Schema (4 Tabelas)**

```sql
-- 📊 User Journey & ML Analytics
user_sessions             -- Complete conversation sessions
user_behavior_events      -- Granular event tracking
conversion_funnel_tracking -- Sales funnel analysis
ab_test_assignments      -- A/B testing framework
```

### 🎯 **Features para Machine Learning**

#### **Dados Comportamentais**

- **Session Tracking**: Duração, frequência, padrões de uso
- **Engagement Metrics**: Score de engajamento, frequência de perguntas
- **Response Patterns**: Tempo de resposta, tipos de mensagem

#### **Dados Demográficos**

- **Informações do Aluno**: Idade, série, matérias de interesse
- **Contexto Familiar**: Indicadores socioeconômicos inferidos
- **Localização**: Região e proximidade da unidade

#### **Dados Temporais**

- **Sazonalidade**: Padrões por hora, dia, mês
- **Timing**: Melhor momento para conversão
- **Frequência**: Padrões de reengajamento

#### **Dados de Sentimento**

- **Análise de Sentimento**: Progressão emocional na conversa
- **Indicadores de Urgência**: Palavras-chave de pressa/interesse
- **Satisfação**: Níveis de satisfação implícitos

---

## 🚀 **Quick Start**

### **1. Pré-requisitos**

```bash
# Ferramentas necessárias
- Python 3.11+
- Docker & Docker Compose
- Google Cloud SDK
- Node.js (para Evolution API local)

# Credenciais necessárias
- OpenAI API Key
- Google Service Account
- Evolution API Key (gerada automaticamente)
```

### **2. Configuração Local**

```bash
# Clone o repositório
git clone <repository-url>
cd kumon-assistant

# Configure ambiente
cp .env.example .env
# Edite .env com suas credenciais

# Instale dependências
pip install -r infrastructure/config/requirements-hybrid.txt

# Start development environment
docker-compose up -d

# Inicialize embeddings
python scripts/maintenance/setup_embeddings.py
```

### **3. Deploy Production**

```bash
# Configurar Google Cloud
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Deploy automatizado
./infrastructure/gcp/deploy.sh

# Ou deploy manual
gcloud builds submit --config=infrastructure/gcp/cloudbuild.yaml
```

---

## 📊 **Custos Otimizados**

### **Configuração Híbrida (Recomendada)**

| Componente          | Recursos         | Custo Mensal | Economia       |
| ------------------- | ---------------- | ------------ | -------------- |
| **Kumon Assistant** | 1 vCPU / 1Gi RAM | $26/mês      | 76% ↓          |
| **Evolution API**   | 1 vCPU / 1Gi RAM | $26/mês      | -              |
| **Qdrant**          | 1 vCPU / 1Gi RAM | $26/mês      | -              |
| **PostgreSQL**      | db-f1-micro      | $7/mês       | -              |
| **Vertex AI**       | Pay-per-use      | $4/mês       | -              |
| **Total**           | -                | **~$89/mês** | **$708/ano** ↓ |

### **Estratégia de Embeddings**

1. **🥇 Primary**: `sentence-transformers` local (GRATUITO)
2. **🥈 Fallback**: Vertex AI Embeddings ($0.025/1k chars)
3. **🥉 Last Resort**: TF-IDF scikit-learn (GRATUITO)

---

## 🔧 **Configuração Avançada**

### **Environment Variables**

```bash
# Core Application
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini

# Evolution API
EVOLUTION_API_URL=https://your-evolution-api-url
EVOLUTION_API_KEY=your_evolution_key

# Database
DATABASE_URL=postgresql://user:pass@host/db
QDRANT_URL=http://localhost:6333

# ML Configuration
USE_GCP_EMBEDDINGS=false
EMBEDDING_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_CACHE_SIZE_MB=50

# Business Configuration
BUSINESS_NAME=Kumon Vila A
BUSINESS_PHONE=+55 11 99999-9999
BUSINESS_EMAIL=kumonvilaa@gmail.com
```

### **Hybrid ML Configuration**

```python
# app/core/config.py
class Settings(BaseSettings):
    # Hybrid ML Strategy
    USE_GCP_EMBEDDINGS: bool = False  # Start with local
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # Cache Management
    EMBEDDING_CACHE_SIZE_MB: int = 50
    MAX_ACTIVE_CONVERSATIONS: int = 500

    # Analytics Configuration
    ENABLE_USER_TRACKING: bool = True
    ML_FEATURES_ENABLED: bool = True
```

---

## 📈 **Analytics & Insights**

### **Dashboard KPIs**

```sql
-- Conversion Rate por Período
SELECT
    DATE_TRUNC('day', session_start) as date,
    COUNT(*) as total_sessions,
    COUNT(*) FILTER (WHERE conversion_achieved = true) as conversions,
    ROUND(COUNT(*) FILTER (WHERE conversion_achieved = true)::numeric / COUNT(*) * 100, 2) as conversion_rate
FROM user_sessions
GROUP BY date ORDER BY date DESC;

-- Abandonment Analysis
SELECT
    abandonment_stage,
    COUNT(*) as count,
    ROUND(AVG(session_duration_minutes), 2) as avg_duration
FROM user_sessions
WHERE session_outcome = 'abandoned'
GROUP BY abandonment_stage;

-- Peak Hours Performance
SELECT
    start_hour,
    COUNT(*) as sessions,
    AVG(conversion_achieved::int) as conversion_rate
FROM user_sessions
GROUP BY start_hour
ORDER BY conversion_rate DESC;
```

### **ML Features Pre-calculadas**

```sql
-- View para Features de ML
CREATE VIEW ml_features_view AS
SELECT
    session_id,
    -- Behavioral Features
    session_duration_minutes,
    total_messages_sent,
    avg_response_time_seconds,
    engagement_score,

    -- Temporal Features
    start_hour, start_day_of_week, is_weekend,

    -- Demographic Features
    mentioned_student_age,
    subjects_mentioned_count,

    -- Target Variable
    conversion_achieved
FROM user_sessions;
```

---

## 🛡️ **Segurança Enterprise**

### **Implementações de Segurança**

- **🔐 Multi-layer Authentication**: Google IAM + API Keys + JWT
- **🛡️ Data Encryption**: Secrets Manager + SSL/TLS end-to-end
- **👤 Non-root Containers**: Todos containers run como non-root users
- **🔍 Security Scanning**: Vulnerability scanning em builds
- **📊 Audit Logging**: Log completo de todas as operações
- **🚧 CORS Policy**: Configuração restritiva para produção

### **Compliance**

- **LGPD Ready**: Estrutura preparada para conformidade LGPD
- **Data Retention**: Políticas automáticas de retenção de dados
- **Access Control**: Controle granular de acesso por função
- **Backup Strategy**: Backup automático com criptografia

---

## 📚 **Documentação Completa**

### **Guias Disponíveis**

- 📖 **[Deploy Guide](docs/deployment/DEPLOY_GUIDE.md)** - Deploy completo passo-a-passo
- 🔧 **[Evolution API Setup](docs/deployment/EVOLUTION_API_SETUP.md)** - Configuração WhatsApp
- 🧠 **[Embedding System](docs/development/EMBEDDING_SYSTEM_README.md)** - Sistema de embeddings
- 📊 **[Migration Study](docs/analysis/GCP_NATIVE_MIGRATION_STUDY.md)** - Análise de migração
- 🎯 **[Requirements Study](docs/analysis/KUMON_ASSISTANT_REQUIREMENTS_STUDY.md)** - Estudo de requisitos

### **API Documentation**

- **Swagger UI**: `https://your-app-url/docs`
- **ReDoc**: `https://your-app-url/redoc`
- **OpenAPI JSON**: `https://your-app-url/openapi.json`

---

## 🧪 **Testing & Quality**

### **Test Coverage**

```bash
# Run all tests
pytest tests/ -v --cov=app

# Run specific test suites
pytest tests/unit/ -v        # Unit tests
pytest tests/integration/ -v # Integration tests
pytest tests/e2e/ -v         # End-to-end tests
```

### **Code Quality**

```bash
# Code formatting
black app/ tests/
isort app/ tests/

# Linting
flake8 app/ tests/
mypy app/

# Security scanning
bandit -r app/
```

---

## 🤝 **Contributing**

### **Development Workflow**

1. **Fork** o repositório
2. **Create** feature branch: `git checkout -b feature/amazing-feature`
3. **Commit** changes: `git commit -m 'Add amazing feature'`
4. **Push** to branch: `git push origin feature/amazing-feature`
5. **Open** Pull Request

### **Code Standards**

- **Type Hints**: Obrigatório em todo código Python
- **Docstrings**: Documentação completa de funções e classes
- **Tests**: Coverage mínimo de 80%
- **Security**: Security scanning obrigatório

---

## 📊 **Roadmap**

### **🚀 Phase 1: Core (✅ Completed)**

- [x] WhatsApp Integration via Evolution API
- [x] Basic AI Conversation Flow
- [x] Google Calendar Integration
- [x] Cloud Deployment

### **🚀 Phase 2: Analytics (✅ Completed)**

- [x] Complete Database Schema (41 tables)
- [x] User Journey Tracking
- [x] ML-Ready Data Structure
- [x] Project Reorganization

### **🚀 Phase 3: Intelligence (🚧 In Progress)**

- [ ] ML Model Training Pipeline
- [ ] Predictive Lead Scoring
- [ ] Automated A/B Testing
- [ ] Advanced Analytics Dashboard

### **🚀 Phase 4: Scale (📋 Planned)**

- [ ] Multi-tenant Architecture
- [ ] Advanced Reporting Suite
- [ ] Mobile Management App
- [ ] Voice Message Support

---

## 📞 **Support & Contact**

- **📧 Email**: kumonvilaa@gmail.com
- **📱 WhatsApp**: +55 51 99692-1999
- **🏢 Address**: Rua Amoreira, 571. Salas 6 e 7. Jardim das Laranjeiras
- **🕒 Hours**: Segunda a Sexta: 08:00 às 18:00

---

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**🌟 Desenvolvido com amor para automatizar e humanizar o atendimento Kumon 🌟**

_Transformando conversas em oportunidades, dados em insights, e visitantes em alunos._

</div>
