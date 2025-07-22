# 🤖 Kumon AI Receptionist

> **Recepcionista Virtual Inteligente para Kumon com WhatsApp Integration**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)
[![Google Cloud](https://img.shields.io/badge/Google_Cloud-Deployed-orange.svg)](https://cloud.google.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🎯 Visão Geral

Sistema de recepcionista virtual inteligente que automatiza o atendimento ao cliente via WhatsApp para unidades Kumon. Utiliza IA avançada para responder perguntas, agendar consultas e coletar leads de forma natural e eficiente.

## ✨ Principais Funcionalidades

- 🤖 **IA Conversacional**: Respostas naturais usando OpenAI GPT
- 📱 **WhatsApp Integration**: Suporte completo via Evolution API
- 📅 **Agendamento Inteligente**: Integração com Google Calendar
- 🔍 **Busca Semântica**: Sistema RAG com Qdrant Vector Database
- 🏢 **Multi-unidades**: Gerenciamento de múltiplas unidades Kumon
- 📊 **Analytics**: Métricas de conversação e performance
- ☁️ **Cloud Native**: Deploy automatizado no Google Cloud Platform

## 📁 Estrutura do Projeto

```
kumon-assistant/
├── 📁 src/app/                    # 🔥 Código da Aplicação
│   ├── api/                      # Endpoints FastAPI
│   ├── clients/                  # Clientes externos (Google, Evolution)
│   ├── core/                     # Configurações centrais
│   ├── models/                   # Modelos de dados
│   ├── services/                 # Lógica de negócio
│   └── utils/                    # Utilitários
│
├── 📁 infrastructure/             # 🚀 Infraestrutura & Deploy
│   ├── docker/                   # Dockerfiles organizados
│   ├── gcp/                      # Configurações Google Cloud
│   └── config/                   # Configurações de infraestrutura
│
├── 📁 docs/                      # 📚 Documentação
│   ├── deployment/               # Guias de deploy
│   ├── development/              # Documentação técnica
│   ├── security/                 # Segurança
│   └── business/                 # Documentação de negócio
│
├── 📁 scripts/                   # 🔧 Scripts Utilitários
│   ├── deployment/               # Scripts de deploy
│   ├── maintenance/              # Scripts de manutenção
│   └── development/              # Scripts de desenvolvimento
│
└── 📁 tests/                     # 🧪 Testes
    ├── unit/                     # Testes unitários
    ├── integration/              # Testes de integração
    └── e2e/                      # Testes end-to-end
```

## 🏗️ Arquitetura do Sistema

### 📊 Arquitetura do Sistema

```mermaid
graph LR
    %% Frontend Layer
    subgraph "📱 Frontend"
        WA[WhatsApp<br/>Business<br/><small>Port 443</small>]
    end

    %% Backend Layer
    subgraph "🚀 Backend"
        API[Kumon AI<br/>Assistant<br/><small>Port 8000</small>]
    end

    %% Data Layer
    subgraph "🗄️ Data"
        QDRANT[Qdrant<br/>Vector DB<br/><small>Port 6333</small>]
        POSTGRES[PostgreSQL<br/>Cloud SQL<br/><small>Port 5432</small>]
    end

    %% Connections
    WA <--> API
    API <--> QDRANT
    API <--> POSTGRES

    %% External Services
    API -.-> OPENAI[🤖 OpenAI<br/>GPT-4]
    API -.-> GCAL[📅 Google<br/>Calendar]
    API -.-> VERTEX[🧠 Vertex AI<br/>Embeddings]

    %% Styling
    classDef frontend fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef backend fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    classDef data fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef external fill:#fff3e0,stroke:#f57c00,stroke-width:2px

    class WA frontend
    class API backend
    class QDRANT,POSTGRES data
    class OPENAI,GCAL,VERTEX external
```

### 🔧 Componentes Internos

```mermaid
graph TB
    subgraph "🤖 Kumon AI Assistant"
        subgraph "📥 Input Layer"
            WEBHOOK[Webhook<br/>Handler]
            MSG[Message<br/>Processor]
        end

        subgraph "🧠 Intelligence Layer"
            INTENT[Intent<br/>Classifier]
            CONV[Conversation<br/>Flow]
            RAG[RAG<br/>Engine]
        end

        subgraph "🔍 Knowledge Layer"
            EMBED[Hybrid<br/>Embeddings]
            VECTOR[Vector<br/>Store]
            CACHE[Cache<br/>Manager]
        end

        subgraph "📋 Business Layer"
            BOOKING[Booking<br/>Service]
            LEAD[Lead<br/>Collector]
            UNIT[Unit<br/>Manager]
        end

        subgraph "📤 Output Layer"
            RESPONSE[Response<br/>Generator]
            FORMAT[Message<br/>Formatter]
        end
    end

    %% Internal Flow
    WEBHOOK --> MSG
    MSG --> INTENT
    INTENT --> CONV
    CONV --> RAG
    RAG --> EMBED
    EMBED --> VECTOR
    VECTOR --> CACHE

    CONV --> BOOKING
    CONV --> LEAD
    CONV --> UNIT

    CONV --> RESPONSE
    RESPONSE --> FORMAT

    %% Styling
    classDef input fill:#e8eaf6,stroke:#3f51b5,stroke-width:2px
    classDef intelligence fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px
    classDef knowledge fill:#e0f2f1,stroke:#4caf50,stroke-width:2px
    classDef business fill:#fff3e0,stroke:#ff9800,stroke-width:2px
    classDef output fill:#fce4ec,stroke:#e91e63,stroke-width:2px

    class WEBHOOK,MSG input
    class INTENT,CONV,RAG intelligence
    class EMBED,VECTOR,CACHE knowledge
    class BOOKING,LEAD,UNIT business
    class RESPONSE,FORMAT output
```

### 🔄 Fluxo de Processamento de Mensagens

```mermaid
sequenceDiagram
    participant U as 👤 Cliente
    participant W as 📱 WhatsApp
    participant E as 🔗 Evolution API
    participant A as 🤖 Kumon Assistant
    participant AI as 🧠 OpenAI GPT-4
    participant V as 🗄️ Vector DB
    participant G as 📅 Google Calendar

    U->>W: Envia mensagem
    W->>E: Webhook message
    E->>A: POST /webhook

    A->>A: 🔍 Classifica intenção
    A->>V: 🔎 Busca semântica
    V-->>A: Contexto relevante

    A->>AI: 💬 Gera resposta
    AI-->>A: Resposta personalizada

    alt Agendamento
        A->>G: 📅 Cria evento
        G-->>A: Confirmação
    end

    A->>E: Resposta formatada
    E->>W: Envia resposta
    W->>U: Recebe resposta
```

### 🧬 Arquitetura de Embeddings Híbrida

```mermaid
graph LR
    TEXT[📝 Texto Input] --> HYBRID[🔄 Hybrid Service]

    HYBRID --> PRIMARY[🥇 PRIMARY]
    HYBRID --> FALLBACK[🥈 FALLBACK]
    HYBRID --> LASTRESORT[🥉 LAST RESORT]

    PRIMARY --> ST[🆓 Sentence Transformers<br/>• Melhor qualidade<br/>• Gratuito<br/>• Local]

    FALLBACK --> GCP[💰 GCP Vertex AI<br/>• Boa qualidade<br/>• $0.025/1k chars<br/>• Cloud]

    LASTRESORT --> TFIDF[⚡ TF-IDF<br/>• Qualidade básica<br/>• Gratuito<br/>• Sempre disponível]

    ST --> EMBED[🧬 Embedding 384D]
    GCP --> EMBED
    TFIDF --> EMBED

    EMBED --> CACHE[💾 Cache Local]
    EMBED --> QDRANT[🗄️ Vector Search]
```

### ☁️ Infraestrutura Cloud

```mermaid
graph LR
    subgraph "🌐 Client"
        USER[WhatsApp<br/>Users]
    end

    subgraph "🚀 Cloud Run Services"
        KUMON[Kumon AI<br/>Assistant<br/><small>1 CPU, 1GB</small>]
        QDRANT[Qdrant<br/>Vector DB<br/><small>1 CPU, 2GB</small>]
        EVO[Evolution<br/>API<br/><small>2 CPU, 2GB</small>]
    end

    subgraph "🗄️ Managed Services"
        SQL[Cloud SQL<br/>PostgreSQL<br/><small>Shared Core</small>]
        SECRET[Secret<br/>Manager<br/><small>API Keys</small>]
    end

    subgraph "🤖 AI Services"
        OPENAI[OpenAI<br/>GPT-4<br/><small>External</small>]
        VERTEX[Vertex AI<br/>Embeddings<br/><small>Fallback</small>]
    end

    %% Connections
    USER <--> EVO
    EVO <--> KUMON
    KUMON <--> QDRANT
    KUMON <--> SQL
    KUMON <--> SECRET
    KUMON -.-> OPENAI
    KUMON -.-> VERTEX

    %% Styling
    classDef client fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef cloudrun fill:#4285f4,color:white,stroke:#1a73e8,stroke-width:2px
    classDef managed fill:#34a853,color:white,stroke:#137333,stroke-width:2px
    classDef ai fill:#ff9800,color:white,stroke:#f57c00,stroke-width:2px

    class USER client
    class KUMON,QDRANT,EVO cloudrun
    class SQL,SECRET managed
    class OPENAI,VERTEX ai
```

## 🚀 Quick Start

### Pré-requisitos

- Python 3.11+
- Docker & Docker Compose
- Google Cloud SDK
- Conta Google Cloud com APIs habilitadas

### 1. Clone e Configure

```bash
git clone <repository-url>
cd kumon-assistant

# Copie as configurações
cp .env.example .env
# Edite .env com suas credenciais
```

### 2. Deploy Local (Desenvolvimento)

```bash
# Usando Docker Compose
docker-compose -f infrastructure/docker/compose/docker-compose.yml up

# Ou usando Python
cd src/
python -m uvicorn app.main:app --reload
```

### 3. Deploy em Produção (Google Cloud)

```bash
# Configure suas credenciais
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Execute o deploy
./infrastructure/gcp/deploy.sh
```

## 🏗️ Arquitetura

```mermaid
graph TB
    A[WhatsApp User] --> B[Evolution API]
    B --> C[Kumon Assistant API]
    C --> D[OpenAI GPT]
    C --> E[Qdrant Vector DB]
    C --> F[Google Calendar]
    C --> G[PostgreSQL]

    subgraph "Google Cloud Platform"
        C
        E
        G
    end
```

## 📖 Documentação

### 📋 Guias Principais

- [🚀 Guia de Deploy](docs/deployment/deployment-guide.md)
- [🐳 Containerização](docs/deployment/CONTAINERIZATION_SUMMARY.md)
- [📱 Evolution API Setup](docs/deployment/EVOLUTION_API_SETUP.md)

### 🔧 Documentação Técnica

- [🧠 Sistema de Embeddings](docs/development/EMBEDDING_SYSTEM_README.md)
- [⚡ Cache Fixes](docs/development/CACHE_FIXES_SUMMARY.md)

### 🔒 Segurança

- [🛡️ Melhorias de Segurança](docs/security/SECURITY_IMPROVEMENTS.md)

### 💰 Negócio

- [💵 Estimativa de Custos](docs/business/COST_ESTIMATION.md)

## 🛠️ Desenvolvimento

### Estrutura do Código

```python
# Exemplo de uso da API
from src.app.services.conversation_flow import ConversationFlow
from src.app.clients.evolution_api import EvolutionAPIClient

# Processar mensagem
flow = ConversationFlow()
response = await flow.process_message(message)
```

### Scripts Utilitários

```bash
# Configurar embeddings
python scripts/maintenance/setup_embeddings.py

# Ingerir documentos
python scripts/maintenance/ingest_docs.py

# Testar fluxo de conversação
python scripts/development/test_flow.py
```

## 🧪 Testes

```bash
# Testes unitários
pytest tests/unit/

# Testes de integração
pytest tests/integration/

# Testes end-to-end
pytest tests/e2e/
```

## 📊 Monitoramento

- **Logs**: Google Cloud Logging
- **Métricas**: Google Cloud Monitoring
- **Health Checks**: `/api/v1/health`
- **Docs API**: `/docs` (Swagger UI)

## 🤝 Contribuição

1. Fork o projeto
2. Crie uma branch (`git checkout -b feature/nova-funcionalidade`)
3. Commit suas mudanças (`git commit -am 'Adiciona nova funcionalidade'`)
4. Push para a branch (`git push origin feature/nova-funcionalidade`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

## 🆘 Suporte

- **Documentação**: Consulte a pasta `docs/`
- **Issues**: Abra uma issue no GitHub
- **Contato**: [Seu contato aqui]

---

**Desenvolvido com ❤️ para automatizar o atendimento Kumon**

## 🎉 **DEPLOY COMPLETO E SERVIÇOS ATIVOS!**

### ✅ **SERVIÇOS DEPLOYADOS COM SUCESSO:**

| Serviço                 | URL                                                   | Status   |
| ----------------------- | ----------------------------------------------------- | -------- |
| 🤖 **Kumon Assistant**  | `https://kumon-assistant-bfaxfjccta-uc.a.run.app`     | ✅ Ready |
| 📱 **Evolution API**    | `https://kumon-evolution-api-bfaxfjccta-uc.a.run.app` | ✅ Ready |
| 🗄️ **Qdrant Vector DB** | `https://kumon-qdrant-bfaxfjccta-uc.a.run.app`        | ✅ Ready |

### 🏗️ **ARQUITETURA IMPLEMENTADA:**

```
📱 WhatsApp → 🚀 Evolution API → 🤖 Kumon Assistant → 🗄️ Qdrant + PostgreSQL
                                        ↓
                               🧬 Hybrid Embeddings
                            (Sentence Transformers + Gemini)
```

### 🎯 **PRÓXIMOS PASSOS:**

1. **✅ Testar o webhook** do WhatsApp
2. **✅ Verificar logs** dos serviços
3. **✅ Configurar Evolution API** para WhatsApp
4. **✅ Testar conversas** end-to-end

**🎉 PARABÉNS! O sistema está totalmente deployado com a arquitetura híbrida implementada - melhor qualidade gratuita com backup pago confiável!**
