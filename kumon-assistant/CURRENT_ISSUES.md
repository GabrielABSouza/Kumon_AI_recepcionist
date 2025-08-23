# Diagnóstico de Problemas Atuais

Este documento detalha os problemas identificados na análise de logs de 23/08/2025. O objetivo é servir como um backlog para as correções.

---

### 1. Ineficiência Crítica: Inicialização de Serviços por Requisição

-   **Problema:** Serviços pesados (LLM Providers, Cost Monitor) são inicializados a cada nova mensagem recebida.
-   **Impacto:** Causa alta latência em todas as requisições, aumenta o consumo de recursos (CPU/Memória) e prejudica a escalabilidade do sistema.
-   **Plano de Ação:** Refatorar o código para mover a inicialização destes serviços para o evento de startup do FastAPI, garantindo que sejam instanciados apenas uma vez e reutilizados.
-   **Status:** `Concluído`

---

### 2. Falta de Resiliência: Fallbacks de LLM Inativos

-   **Problema:** Os provedores de fallback (Anthropic e Twilio) não estão funcionais devido a dependências ausentes e falta de configuração.
-   **Impacto:** O sistema não possui resiliência. Uma falha na API da OpenAI resultará em falha total do serviço.
-   **Plano de Ação:**
    1.  Adicionar o pacote `anthropic` às dependências do projeto (`requirements.txt`).
    2.  Configurar as credenciais do Twilio como variáveis de ambiente no Railway.
-   **Status:** `Concluído`

---

### 3. Ruído nos Logs: Mensagens Duplicadas

-   **Problema:** Muitas mensagens de log aparecem duplicadas, com e sem o prefixo do logger.
-   **Impacto:** Dificulta a leitura, análise e depuração dos logs.
-   **Plano de Ação:** Inspecionar a configuração do logger (provavelmente em `app/core/logger.py`) e remover o handler redundante que causa a duplicação das mensagens.
-   **Status:** `Concluído`
