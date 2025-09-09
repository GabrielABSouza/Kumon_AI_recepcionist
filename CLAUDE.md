# CLAUDE.md - Kumon Assistant Instructions


**SOB NENHUMA CIRCUNSTÂNCIA ALTERE A INSTÂNCIA EVOLUTION API, URLs DE ACESSO AOS SERVIÇOS OU CHAVES API
## Database Connection Commands

### Railway PostgreSQL Production Database

**Connection Details:**
- Host: yamabiko.proxy.rlwy.net
- Port: 20931
- User: postgres
- Password: XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR
- Database: railway

**Base Command Pattern:**
```bash
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "YOUR_SQL_COMMAND"
```

### Common Database Operations

**List Tables:**
```bash
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "\dt"
```

**Describe Table Structure:**
```bash
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "\d conversation_sessions"
```

**Query Recent Conversations:**
```bash
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "SELECT session_id, phone_number, current_stage, current_step, updated_at FROM conversation_sessions ORDER BY updated_at DESC LIMIT 5;"
```

**Delete Conversation History:**
```bash
# Delete messages first
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "DELETE FROM conversation_messages WHERE conversation_id = 'SESSION_ID';"

# Then delete session
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "DELETE FROM conversation_sessions WHERE session_id = 'SESSION_ID';"
```

**Reset Conversation State:**
```bash
PGPASSWORD=XnpZDyhnuKYENKoBwxSmNoqUBkJtcscR psql -h yamabiko.proxy.rlwy.net -p 20931 -U postgres -d railway -c "UPDATE conversation_sessions SET current_stage = 'greeting', current_step = 'initial_contact', status = 'active', updated_at = NOW(), ended_at = NULL WHERE session_id = 'SESSION_ID';"
```

### Database Schema

**Main Tables:**
- `conversation_sessions` - Session metadata and state
- `conversation_messages` - Individual messages
- `user_profiles` - User profile information
- `daily_conversation_metrics` - Analytics data

**Key Fields in conversation_sessions:**
- `session_id` - Primary key
- `phone_number` - WhatsApp number
- `current_stage` - greeting, qualification, information_gathering, scheduling, completed
- `current_step` - Specific step within stage
- `status` - active, completed, ended
- `updated_at` - Last modification timestamp

---

# CLAUDE.md — Kumon Assistant (Arquitetura Mínima, Rápida e Funcional)

> **Objetivo**: Este documento é a **fonte única de verdade** para o agente *Claude Code (Sonnet-4)* implementar e manter uma arquitetura mínima.
> **Proibido** criar novos componentes, duplicar funcionalidades ou adicionar camadas desnecessárias. Foque em **latência baixa**, **simplicidade** e **confiabilidade**.

---

## 1) Visão Geral

### Fluxo Mínimo (único caminho feliz)

1. **Receber Webhook** do Evolution API.
2. **Pré-processar** a mensagem (sanitização leve + dedupe por `message_id`).
3. **Classificar intenção** usando **Gemini Flash Mini** (somente decisão de intenção + confiança + atributos simples).
4. **Executar o nó** correspondente em **LangGraph** (1 grafo simples; nós determinísticos).
5. **Gerar resposta** e **enviar** via Evolution API.

> O *Turn Controller* existe **apenas** como *guardrail* (dedupe/lock/recursion cooldown). **Nunca** toma decisões de produto, **nunca** envia mensagem, **nunca** reprocessa o pipeline.

### Não-objetivos

* Sem RAG, sem Pinecone, sem banco relacional, sem múltiplas arquiteturas de fallback.
* Sem SmartRouter proprietário, sem Threshold Engine separado, sem “planner” complexo.
* Sem reprocessar etapas já feitas; **1 passagem** por turno.

---

## 2) Regras de Ouro (obrigatórias)

* **Nenhum novo componente** além do que está definido aqui.
* **Sem duplicação** de responsabilidades. Cada módulo tem **uma** razão de existir.
* **Tudo síncrono** num único request background: webhook → pipeline → Evolution API.
* **Logs padronizados** e mínimos (ver §7). Se não aparece, é bug.
* **Idempotência** por `message_id` do Evolution: nunca responda duas vezes ao mesmo `message_id`.
* **Tempo de resposta P95 < 800ms** em produção (conteúdo curto).
* **Erros → fallback textual único** e 200 OK para webhook (quando possível).

---

## 3) Estrutura de Pastas (apenas estes arquivos/módulos)

```
app/
  api/
    evolution.py           # FastAPI webhook handler + background task
  core/
    guardrails.py          # turn lock, dedupe, recursion cooldown
    preprocess.py          # sanitização leve e normalização
    intent_gemini.py       # chamada ao Gemini Flash Mini
    langgraph_runner.py    # execução de um LangGraph simples
    delivery.py            # cliente Evolution API (sendText)
    logging.py             # util de logging estruturado (leve)
  config.py                # leitura de env vars (única fonte)
```

> **Não criar** pastas adicionais, repositórios, caches paralelos, feature flags, etc.

---

## 4) Contratos de Dados (estritos)

### 4.1 Webhook (entrada minimamente necessária)

```json
{
  "instance": "kumon_assistant",
  "message_id": "3A...",
  "phone": "555199999999",
  "text": "oi",
  "timestamp": 1699999999
}
```

### 4.2 Preprocess → Intent Request (input do Gemini)

```json
{
  "text": "oi",
  "history": [],            // opcional, curto (<= 3 últimas trocas)
  "locale": "pt-BR"        // default
}
```

### 4.3 Intent Response (Gemini Flash Mini)

```json
{
  "intent": "greeting|info|qualification|scheduling|fallback",
  "confidence": 0.0-1.0,
  "entities": {"name": "...", "age": 10} // opcional, chaves simples
}
```

### 4.4 LangGraph Node Input

```json
{
  "intent": "greeting",
  "entities": {...},
  "phone": "555199999999",
  "locale": "pt-BR"
}
```

### 4.5 LangGraph Node Output (único texto)

```json
{
  "text": "Olá! Sou o assistente da Kumon. Como posso ajudar?"
}
```

### 4.6 Delivery Request (Evolution API)

```json
{
  "instance": "kumon_assistant",
  "number": "555199999999",
  "text": "..."
}
```

---

## 5) Pseudocódigo do Pipeline

```python
# app/api/evolution.py
@router.post("/api/v1/evolution/webhook")
async def messages_upsert(payload: dict, background_tasks: BackgroundTasks):
    # 1) Extração mínima
    evt = extract_minimal(payload)
    if not evt.text:
        return {"status": "ignored"}

    # 2) Turn guard (dedupe + lock + recursion)
    if guardrails.is_duplicate(evt.message_id):
        return {"status": "duplicate"}
    async with guardrails.turn_lock(evt.phone):
        # 3) Pré-processo
        pre = preprocess.clean(evt.text)

        # 4) Intent (Gemini Flash Mini)
        intent = await intent_gemini.classify(pre, locale="pt-BR")

        # 5) LangGraph
        out = await langgraph_runner.run(intent=intent.intent, entities=intent.entities, phone=evt.phone)
        text = out.text or "Tive um problema técnico. Pode repetir, por favor?"

        # 6) Delivery
        await delivery.send_text(instance=evt.instance, number=evt.phone, text=text)
        return {"status": "ok"}
```

**Observações**:

* `guardrails` **não** envia mensagens e **não** decide conteúdo.
* `langgraph_runner` tem **um** grafo e **nós mínimos** (por intenção) com lógica determinística e rápida.

---

## 6) Implementação de Cada Módulo (mínimo necessário)

### 6.1 `guardrails.py`

* `is_duplicate(message_id)`: Redis **opcional**; se não houver Redis, usar `in-memory LRU` com TTL curto.
* `turn_lock(phone)`: lock com TTL 10s (Redis ou dummy local). Não faça I/O desnecessário.
* `recursion_cooldown(phone, intent)`: simples contador por 30s para `greeting`.
* **Proibido**: qualquer envio de mensagem ou alteração do texto final.

### 6.2 `preprocess.py`

* Normalização leve: strip, collapse spaces, limiter 1000 chars, remove caracteres de controle.
* Sem listas negras complexas, sem regex pesadas.

### 6.3 `intent_gemini.py`

* Chamada **direta** ao Gemini Flash Mini com prompt enxuto e retorno no contrato §4.3.
* Mapeie intenções em 5 rótulos fixos.
* **Não** faça geração de texto aqui; **apenas** decisão.

### 6.4 `langgraph_runner.py`

* 1 grafo com 5 nós: `greeting`, `info`, `qualification`, `scheduling`, `fallback`.
* Cada nó retorna **um** `text` curto.
* Sem LLM adicionais aqui por padrão; permitir *apenas* frases template simples.
* Se necessário, **um** LLM rápido (opcional) **somente** para preencher pequenos slots (ex.: formatação), nunca para roteamento.

### 6.5 `delivery.py`

* `send_text(instance, number, text)`: HTTP POST simples; 1 retry com backoff curto (200-500ms).
* Idempotência garantida **pelo dedupe de message\_id** (guardrails). Não reenvie na mesma chamada.

### 6.6 `logging.py`

* Funções utilitárias para logs padrão (ver §7). Sem bibliotecas pesadas.

---

## 7) Logging Padronizado (mínimo e suficiente)

Sempre imprimir **exatamente** estas linhas (níveis indicativos):

* `PIPELINE|start phone=**** msg_id=...`
* `PIPELINE|preprocess_ok len=...`
* `PIPELINE|intent_ok intent=... conf=...`
* `PIPELINE|langgraph_ok node=...`
* `PIPELINE|delivery_ok provider_id=...`
* `PIPELINE|complete`

Erros:

* `PIPELINE|intent_error err=...`
* `PIPELINE|langgraph_error err=...`
* `PIPELINE|delivery_error err=...`

> Se qualquer etapa falhar, retornar **fallback textual único** e logar o erro correspondente.

---

## 8) Configuração (única fonte: `config.py`)

Variáveis de ambiente obrigatórias:

* `EVOLUTION_API_BASE` (ex.: `https://evolution-api...`)
* `EVOLUTION_INSTANCE` (ex.: `kumon_assistant`)
* `GEMINI_API_KEY`

Opcionais:

* `REDIS_URL` (para lock/dedupe; se ausente, usar memória local)
* `LOG_LEVEL` (`INFO` default)

**Proibido** ler env em qualquer outro lugar.

---

## 9) Performance e SLOs

* **P95 < 800ms**, **P50 < 350ms** (texto curto).
* **Erros** < 1% (excluindo falhas externas do Evolution/Gemini).
* **Timeouts**: Gemini 300ms; Delivery 400ms (1 retry).

---

## 10) Segurança e Confiabilidade

* Validar `instance`, `phone`, `message_id` presentes.
* Rejeitar mensagens vazias ou > 1000 chars (após preprocess).
* **Idempotência**: chave = `message_id`. Nunca responder 2x ao mesmo `message_id`.
* **Sem DB**. Nada de migrações.

---

## 11) Testes (Check-list mínimo)

1. **Feliz**: `oi` → intent `greeting` → nó `greeting` → envia 200 OK e mensagem.
2. **Intent erro**: time-out no Gemini → usar `fallback` e enviar.
3. **Delivery erro**: 500 Evolution → 1 retry → se falha, logar `delivery_error` e **não** retry adicional.
4. **Dedupe**: mesmo `message_id` 2x → 1 resposta apenas.
5. **Lock**: dois requests simultâneos para mesmo `phone` → apenas um executa; o outro aguarda ou desiste silenciosamente.
6. **Recursion**: múltiplos `greeting` em <30s → responder 1 vez; demais passam mas caem em `fallback` curto.

---

## 12) Política de Mudanças (rigorosa)

* **Não adicionar** arquivos além dos listados em §3.
* **Não mover** responsabilidades entre módulos.
* Commits pequenos, mensagens claras, sem refactors grandes.
* Se precisar alterar contrato (§4), **atualize este documento primeiro**.

---

## 13) Definição de Pronto (DoD)

* Todos os testes de §11 passando.
* Logs padrão de §7 aparecendo em produção.
* P95 < 800ms sob carga leve.
* Zero criação de novos componentes/módulos.

---

## 14) Guia de Implementação (passo-a-passo para Claude)

1. Criar `config.py` e ler envs.
2. Implementar `guardrails.py` (dedupe + lock + cooldown) com fallback in-memory.
3. Implementar `preprocess.py` (sanitização leve).
4. Implementar `intent_gemini.py` (chamada mínima ao Gemini + mapeamento fixo).
5. Implementar `langgraph_runner.py` (grafo único, 5 nós, respostas simples por intenção).
6. Implementar `delivery.py` (Evolution sendText, 1 retry).
7. Implementar `api/evolution.py` com o **pseudocódigo do §5**, sem variações.
8. Implementar `logging.py` e garantir logs de §7.
9. Rodar testes de §11 e validar SLOs.

> Se alguma decisão não estiver coberta, **escolha sempre a opção mais simples e mais rápida**, mantendo os contratos.
