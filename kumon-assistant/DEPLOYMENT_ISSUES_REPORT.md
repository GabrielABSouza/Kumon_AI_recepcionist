### **1. Problema Principal: Falha na Validação de Variáveis de Ambiente Críticas**

O log mostra uma `pydantic_core._pydantic_core.ValidationError` com 3 erros de validação para as configurações da aplicação. Isso significa que a aplicação não consegue iniciar porque variáveis de ambiente essenciais estão ausentes ou com valores inválidos.

**Detalhes da Falha:**

*   **`EVOLUTION_API_KEY`**: "Value error, Evolution API key is required in production"
    *   **Status Atual:** Valor vazio (`input_value=''`).
*   **`OPENAI_API_KEY`**: "Value error, OpenAI API key is required in production and must start with 'sk-'"
    *   **Status Atual:** Valor vazio (`input_value=''`).
*   **`DATABASE_URL`**: "Value error, Valid PostgreSQL database URL is required in production"
    *   **Status Atual:** Valor vazio (`input_value=''`).

**Causa Raiz:**

As variáveis de ambiente `DATABASE_URL`, `REDIS_URL`, `EVOLUTION_API_KEY` e `OPENAI_API_KEY` não estão sendo fornecidas ou estão com valores incorretos no ambiente de produção do Railway. 

*   O módulo `app.core.railway_environment_fix` tenta detectar e preencher `DATABASE_URL` e `REDIS_URL` automaticamente, mas falha (`No valid Railway database URL found`, `No valid Railway Redis URL found`).
*   As chaves de API (`EVOLUTION_API_KEY`, `OPENAI_API_KEY`) estão vazias, indicando que não foram configuradas no ambiente.

**Impacto:**

A aplicação não consegue iniciar, pois suas configurações básicas (conexão com banco de dados, Redis, e chaves de API para serviços externos) são inválidas. Isso resulta em um crash imediato do serviço.

---

### **2. Plano de Ação Detalhado**

O foco principal é garantir que todas as variáveis de ambiente críticas sejam corretamente definidas no ambiente de produção do Railway.

**Passo 1: Configuração de Variáveis de Ambiente no Railway**

*   **Ação:** Você deve acessar o painel do Railway para o serviço `kumon-assistant` e ir na aba **"Variables"**.
*   **Variáveis a Definir (e seus valores esperados):**
    *   `DATABASE_URL`:
        *   **Valor:** A URL de conexão completa com o seu serviço de PostgreSQL no Railway.
        *   **Como Obter:** Geralmente, o Railway fornece essa URL na página do serviço de PostgreSQL. Certifique-se de que o serviço de PostgreSQL esteja linkado ao seu serviço `kumon-assistant`. Se estiver linkado, o Railway deveria autopopular essa variável. Se não, copie-a manualmente.
    *   `REDIS_URL`:
        *   **Valor:** A URL de conexão completa com o seu serviço de Redis no Railway.
        *   **Como Obter:** Similar ao `DATABASE_URL`, o Railway fornece essa URL na página do serviço de Redis. Verifique o link e, se necessário, copie-a manualmente.
    *   `EVOLUTION_API_KEY`:
        *   **Valor:** A chave da API do seu serviço Evolution.
        *   **Como Obter:** Esta chave é gerada pelo seu serviço Evolution (que você deve ter configurado separadamente).
    *   `OPENAI_API_KEY`:
        *   **Valor:** A chave da API da OpenAI.
        *   **Como Obter:** Gerada na sua conta OpenAI. **Importante:** Deve começar com `sk-`.

**Passo 2: Revisão do `app.core.railway_environment_fix` (Opcional/Avançado)**

*   **Ação:** Se, após definir as variáveis no Railway, o `DATABASE_URL` e `REDIS_URL` ainda não forem detectados corretamente pelo `railway_environment_fix`, pode ser necessário inspecionar o código em `app/core/railway_environment_fix.py`.
*   **Possível Causa:** Os nomes das variáveis de ambiente que o Railway fornece para os serviços de banco de dados e Redis podem ter mudado, ou a lógica de detecção no seu código precisa ser atualizada para os nomes atuais.
*   **Alternativa:** Se a detecção automática continuar falhando, você pode definir essas URLs manualmente nas variáveis do Railway, copiando-as diretamente dos serviços de banco de dados e Redis no Railway.

**Passo 3: Novo Deploy**

*   **Ação:** Após configurar todas as variáveis de ambiente necessárias, acione um novo deploy no Railway.
