Testing Flow — Evolution API → FastAPI (Preprocessor) → (Classifier/Router) → Delivery

Objetivo: implementar e validar, via TDD, o fluxo mínimo e rápido:
Evolution Webhook → Preprocessador → (futuro) Classifier/Router → Delivery
Sem criar componentes novos, sem duplicação e com mudanças mínimas para fazer os testes passarem.

Pastas & Convenções
kumon-assistant/
  app/
    api/evolution.py
    services/message_preprocessor.py
    core/delivery.py
    core/dedup.py
  tests/
    unit/
      test_preprocessor_unit.py
    integration/
      test_webhook_integration.py
      test_delivery_integration.py
    e2e/
      test_happy_path_minimal.py


Use pytest.

Mock de I/O externo (HTTP Evolution API, Redis) com pytest-mock/unittest.mock.

Nenhum teste deve bater na internet.

Todos os testes devem ser determinísticos (fixar seeds/horários quando necessário).

FASE 1 — Unit (Preprocessor)

Alvo: app/services/message_preprocessor.py
Escopo mínimo:

Auth: aceita headers válidos do Evolution; rejeita ausência/headers inválidos.

Sanitização: remove <script> / payloads perigosos + limita comprimento (ex.: 1000 chars).

fromMe: marca mensagens do próprio número (eco) para ignorar.

Rate limit (janela 60s): até 10 msgs/min por telefone → 429 lógico.

Arquivos de teste:

tests/unit/test_preprocessor_unit.py

Comandos:

pytest -q tests/unit/test_preprocessor_unit.py --maxfail=1 --disable-warnings


Critérios de aceite:

100% dos testes desta suíte passando.

Sem chamadas externas reais (mocks para Redis, tempo congelado quando preciso).

Resumo Executivo (retornar após esta fase):

Formato descrito em “Formato do Resumo Executivo” no final (use suite: "preprocessor_unit").

FASE 2 — Integração (Webhook → Preprocessor)

Alvo: app/api/evolution.py (endpoint do webhook).
Escopo mínimo:

POST /api/v1/evolution/webhook:

Retorna 200 imediatamente e enfileira processamento em background (pode mockar a fila/tarefa).

Ignora fromMe = True (não dispara pipeline).

Passa headers ao preprocessor; rejeita faltas de headers com erro lógico (sem expor detalhes sensíveis).

Deduplicação por message_id (in-memory ou mock Redis) — mesma mensagem não processa duas vezes.

Arquivos de teste:

tests/integration/test_webhook_integration.py

Comandos:

pytest -q tests/integration/test_webhook_integration.py --maxfail=1 --disable-warnings


Critérios de aceite:

100% dos testes desta suíte passando.

Logs estruturados mínimos: PIPELINE|event=auth_ok|... e DEDUP|event=new_message|....

Resumo Executivo (retornar após esta fase):

Use suite: "webhook_integration".

FASE 3 — Integração (Delivery)

Alvo: app/core/delivery.py
Escopo mínimo:

send_text(phone, text, instance):

Formata número (ex.: +55…).

Faz POST mockado para Evolution API /message/sendText/{instance}.

Repetição com backoff para 5xx (simulado).

Retorna objeto com status, provider_message_id (mock) e idempotency_key.

Idempotência: se idempotency_key já marcado como enviado, não reenvia.

Arquivos de teste:

tests/integration/test_delivery_integration.py

Comandos:

pytest -q tests/integration/test_delivery_integration.py --maxfail=1 --disable-warnings


Critérios de aceite:

100% desta suíte passando.

Nenhum request externo real.

Resumo Executivo (retornar após esta fase):

Use suite: "delivery_integration".

FASE 4 — E2E Minimal (Happy Path)

Alvo: fluxo mínimo end-to-end (sem classifier real ainda; stub simples).
Escopo mínimo:

Recebe webhook válido com texto “olá”.

Preprocessor aceita.

Stub do nó de resposta: retorna texto fixo “Olá! Como posso ajudar?” (ou chama um prompt estático) — não integrar LLM nesta fase.

Delivery envia (mock HTTP), guarda idempotência (mock store) e retorna sucesso.

Arquivos de teste:

tests/e2e/test_happy_path_minimal.py

Comandos:

pytest -q tests/e2e/test_happy_path_minimal.py --maxfail=1 --disable-warnings


Critérios de aceite:

100% desta suíte passando.

Logs principais presentes: PIPELINE|start, preprocess_complete, delivery_complete.

Resumo Executivo (retornar após esta fase):

Use suite: "e2e_happy_path".

Regras de Implementação

Sem novos componentes/camadas.

Sem duplicar funcionalidades.

Mudar o mínimo necessário para fazer os testes passarem.

Mocks para tudo que for rede/Redis/DB.

Tempo/clock controlado nos testes onde necessário (ex.: rate limit).

Logs estruturados mínimos conforme já existem nos exemplos (PIPELINE/DEDUP).

Formato do Resumo Executivo (após cada fase)

Retorne duas partes: (A) humano curto; (B) JSON parseável.

(A) Resumo humano (≤ 12 linhas)

Status geral: ❇️ verde | 🟡 parcial | 🔴 quebrado

Falhas críticas (top 3): teste → 1 linha do erro/traço

Causa raiz (hipótese): 1–2 bullets

Impacto no fluxo: 1–2 bullets

Ações recomendadas (próximo TDD): 3–5 bullets (arquivo + mudança + efeito)

Risco de regressão: baixo | médio | alto (1 frase)

Go/No-Go: Go | No-Go

(B) JSON
{
  "suite": "preprocessor_unit | webhook_integration | delivery_integration | e2e_happy_path",
  "overall_status": "green | yellow | red",
  "summary": {
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "duration_seconds": 0.0
  },
  "failures": [
    {
      "test": "nome_do_teste",
      "error_short": "mensagem_1_linha",
      "file": "caminho/arquivo.py",
      "line": 0
    }
  ],
  "root_cause_hypotheses": [
    "hipotese_1",
    "hipotese_2"
  ],
  "impact": [
    "efeito_pratico_no_fluxo"
  ],
  "recommended_actions": [
    {
      "file": "caminho/alvo.py",
      "change": "descricao_concisa_da_mudanca",
      "expected_outcome": "efeito_verificavel_no_teste"
    }
  ],
  "regression_risk": "low | medium | high",
  "decision": "GO | NO_GO"
}

Como o agente deve proceder

Criar/ajustar os arquivos de teste de cada fase, rodar a suíte daquela fase.

Se falhar, implementar apenas o mínimo no código de produção para verdejar a suíte.

Retornar o Resumo Executivo (A + B) ao final da fase.

Só então avançar para a próxima fase.
