perfeito — vamos focar na integração Preprocessor → Gemini Orchestrator com TDD, incluindo testes de compreensão de contexto. abaixo está a estrutura de testes proposta, os casos essenciais (com Given/When/Then) e snippets pytest com mocks do Gemini.

Estrutura de pastas (tests)
tests/
  conftest.py
  helpers/
    factories.py                 # builders de mensagens e estados
    gemini_stubs.py              # respostas simuladas do Gemini
  preprocessor/
    test_preprocessor_contract.py # (já existe da fase 1)
  orchestrator/
    test_orchestrator_contract.py
    test_orchestrator_context_understanding.py
    test_orchestrator_thresholds.py
    test_orchestrator_error_handling.py
    test_orchestrator_performance.py
    test_orchestrator_logging_tracing.py

Escopo do que vamos testar

Contrato e Interface

Recebe PreprocessedMessage e retorna ClassificationResult com:

intent (enum: greeting, info_request, qualification, scheduling, fallback)

confidence (0–1)

entities (dict leve)

routing_hint (opcional)

Nunca gera texto final (apenas classifica).

Compreensão de contexto (context understanding)

Usa janela de contexto (histórico curto) para desambiguar:

Referências pronominais (“ele/isso/isso aí”)

Continuação de tópico (“sobre preços… e horários?”)

Mudança de intenção após objeção (“achei caro” → objection vs info_request)

Idioma/variação (“oi”, “ola”, “olá”, PT-BR vs PT-PT)

Código-mesclado (mensagem com números/emoji/link)

“fromMe”/eco não afeta contexto

Thresholds e ambiguidade

Faixas: alto (≥0.8), médio (0.5–0.79), baixo (<0.5)

Em ambiguidades, retorna intent=fallback + confidence<0.5 + routing_hint=request_clarification.

Robustez operacional

Timeout e retry (orquestrador aplica timeout curto e 1 retry)

Erros do provider → degrade para fallback com confidence=0.0

Entradas vazias ou sanitizadas ao extremo → fallback.

Observabilidade

Logs estruturados: ORCH|start|…, ORCH|complete|intent=…|confidence=…|latency_ms=…

Trace id/turn id propagados do preprocessor.

Performance

SLO: p95 ≤ 150ms (usando mock de rede)

Teste garante orçamento de latência (sem I/O real).

Casos de Teste (resumo Given/When/Then)
A) Contrato básico

Given mensagem pré-processada “olá”

When orquestrador consulta Gemini

Then retorna intent=greeting, confidence≥0.8, entities={} e não retorna texto gerado.

B) Contexto: referência pronominal

Given histórico: usuário perguntou preço; mensagem atual: “e ele inclui material?”

When classificar

Then intent=information_request, entities={"topic":"pricing","subtopic":"materials"}.

C) Mudança de intenção após objeção

Given histórico sobre matrícula; mensagem: “achei caro, tem desconto?”

Then intent=objection ou information_request com routing_hint="pricing_discount", confidence≥0.7.

D) Ambiguidade controlada

Given mensagem: “legal” (sem contexto)

Then intent=fallback, confidence<0.5, routing_hint="request_clarification".

E) Idioma/variação

Given “boa tarde, queria infos do método”

Then intent=information_request, entities={"topic":"method"}.

F) Rate-limit/sanitização já aplicados

Given entrada sanitizada (tags removidas)

Then classifica normalmente (não re-sanitiza).

G) Timeout/erro do provider

Given Gemini não responde em N ms ou lança erro

Then intent=fallback, confidence=0.0, log ORCH|error|timeout.

H) Thresholds

Given mensagem ambígua (“pode ser amanhã?” sem contexto)

Then confidence entre 0.5–0.79 e routing_hint="ask_time_context".

I) Performance

Given 50 chamadas concorrentes (mock)

Then p95 ≤ 150ms, nenhum leak de sessão.

J) Observabilidade

Given uma classificação bem-sucedida

Then logs contêm keys: trace_id, turn_id, intent, confidence, latency_ms.

Snippets (pytest) — essenciais
conftest.py (fixture principal)
import pytest
from app.core.models import PreprocessedMessage
from tests.helpers.gemini_stubs import GeminiStub

@pytest.fixture
def gemini_stub():
    return GeminiStub()

@pytest.fixture
def orchestrator(gemini_stub):
    from app.core.gemini_orchestrator import GeminiOrchestrator
    return GeminiOrchestrator(client=gemini_stub, timeout_ms=120, retries=1)

@pytest.fixture
def base_msg():
    return PreprocessedMessage(
        phone="555199999999",
        text="olá",
        headers={"x-forwarded-for":"1.2.3.4"},
        from_me=False,
        history=[]
    )

helpers/gemini_stubs.py
class GeminiStub:
    def __init__(self):
        self.behavior = "ok"
        self.next_response = {"intent":"greeting","confidence":0.92,"entities":{}}

    async def classify(self, prompt):
        if self.behavior == "timeout":
            raise TimeoutError("mock timeout")
        if self.behavior == "error":
            raise RuntimeError("mock provider error")
        return self.next_response

test_orchestrator_contract.py
import pytest

@pytest.mark.asyncio
async def test_contract_basic(orchestrator, base_msg, gemini_stub):
    gemini_stub.next_response = {"intent":"greeting","confidence":0.9,"entities":{}}
    result = await orchestrator.classify(base_msg)
    assert result.intent == "greeting"
    assert result.confidence >= 0.8
    assert isinstance(result.entities, dict)
    # garante que não tem texto final
    assert not getattr(result, "generated_text", None)

test_orchestrator_context_understanding.py
import pytest
from app.core.models import PreprocessedMessage, HistoryTurn

@pytest.mark.asyncio
async def test_context_pronoun_resolution(orchestrator, gemini_stub):
    hist = [
        HistoryTurn(role="user", text="Quais os preços?"),
        HistoryTurn(role="assistant", text="Temos planos X e Y.")
    ]
    msg = PreprocessedMessage(
        phone="5551", text="e ele inclui material?",
        headers={}, from_me=False, history=hist
    )
    gemini_stub.next_response = {
        "intent":"information_request",
        "confidence":0.86,
        "entities":{"topic":"pricing","subtopic":"materials"}
    }
    result = await orchestrator.classify(msg)
    assert result.intent == "information_request"
    assert result.entities.get("topic") == "pricing"
    assert result.confidence >= 0.8

test_orchestrator_thresholds.py
import pytest

@pytest.mark.asyncio
async def test_ambiguous_returns_fallback(orchestrator, base_msg, gemini_stub):
    base_msg.text = "legal"
    gemini_stub.next_response = {"intent":"fallback","confidence":0.42,"entities":{}, "routing_hint":"request_clarification"}
    result = await orchestrator.classify(base_msg)
    assert result.intent == "fallback"
    assert result.confidence < 0.5
    assert result.routing_hint == "request_clarification"

test_orchestrator_error_handling.py
import pytest

@pytest.mark.asyncio
async def test_timeout_degrades_to_fallback(orchestrator, base_msg, gemini_stub):
    gemini_stub.behavior = "timeout"
    result = await orchestrator.classify(base_msg)
    assert result.intent == "fallback"
    assert result.confidence == 0.0

test_orchestrator_performance.py
import asyncio
import statistics
import pytest

@pytest.mark.asyncio
async def test_p95_latency(orchestrator, base_msg, gemini_stub):
    latencies = []
    async def one_call():
        import time
        t0 = time.perf_counter()
        await orchestrator.classify(base_msg)
        latencies.append((time.perf_counter()-t0)*1000)

    await asyncio.gather(*[one_call() for _ in range(50)])
    p95 = sorted(latencies)[int(0.95*len(latencies))-1]
    assert p95 <= 150

test_orchestrator_logging_tracing.py
import pytest

@pytest.mark.asyncio
async def test_logs_have_trace_keys(orchestrator, base_msg, caplog, gemini_stub):
    caplog.set_level("INFO")
    await orchestrator.classify(base_msg)
    logs = "\n".join([r.message for r in caplog.records])
    assert "ORCH|start" in logs
    assert "ORCH|complete" in logs
    assert "intent=" in logs and "confidence=" in logs

Critérios de Aceite (Definition of Done)

✅ Todos os testes acima passando localmente e no CI.

✅ GeminiOrchestrator.classify() não gera texto final.

✅ Thresholds aplicados corretamente com routing_hint em ambiguidades.

✅ Logs estruturados presentes nas execuções.

✅ p95 ≤ 150ms em ambiente de testes com stubs.

Saída esperada (resumo executivo ao fim desta fase)

Resumo Executivo – Fase “Preprocessor → Gemini Orchestrator”

Cobertura: contrato, contexto, thresholds, erros, logs e performance.

Acurácia contextual: X/Y cenários críticos passaram (pronome, continuidade, objeção).

Ambiguidade: corretamente mapeada para fallback com routing_hint.

Robustez: timeouts/erros → degrade seguro; sem texto final gerado.

SLO: p95 = NN ms (≤ 150ms).

Próximo passo: integrar saída do orquestrador ao LangGraph (nós simples que enviam resposta) mantendo idempotência.

gemini_orchestrator.md — Plano de Testes + Saídas Esperadas
Objetivo

Garantir que o Gemini Orchestrator:

receba um PreprocessedMessage e apenas classifique intenção (sem gerar resposta final);

compreenda contexto curto (histórico imediatamente relevante);

respeite thresholds e sinalize ambiguidade;

degrade com segurança em timeout/erros;

forneça logs estruturados e atenda SLO de latência com mocks.

Fases (TDD)
Fase 1 — Contrato & Interface

Meta: validar a assinatura classify(msg) -> ClassificationResult.
Testes-alvo:

test_contract_basic (intenção simples “olá”)

assegura: intent, confidence, entities, sem generated_text.
Critérios de aceite:

Todos os testes da fase passam.

Logs mínimos: ORCH|start, ORCH|complete.

Fase 2 — Compreensão de Contexto

Meta: desambiguar por histórico curto.
Testes-alvo:

test_context_pronoun_resolution (referência “ele/isso”)

continuidade de tópico (preço → materiais; horários → datas)

mudança de intenção após objeção (“achei caro…”)
Critérios de aceite:

≥ 90% dos casos de contexto definidos passam.

entities preenchidas quando aplicável (ex.: {"topic":"pricing"}).

Fase 3 — Thresholds & Ambiguidade

Meta: mapear incerteza corretamente.
Testes-alvo:

test_ambiguous_returns_fallback (mensagem “legal” sem contexto)

casos 0.5–0.79 retornam routing_hint útil (ex.: request_clarification).
Critérios de aceite:

Regras de faixa aplicadas corretamente (baixo/médio/alto).

routing_hint presente nas ambiguidades.

Fase 4 — Robustez Operacional

Meta: comportamento seguro em falhas.
Testes-alvo:

test_timeout_degrades_to_fallback

erro do provider → fallback com confidence=0.0.
Critérios de aceite:

Sem exceções “vazando”; logs com ORCH|error|….

Fase 5 — Observabilidade

Meta: rastreabilidade e medição.
Testes-alvo:

test_logs_have_trace_keys (trace_id, turn_id, intent, confidence, latency)
Critérios de aceite:

Logs estruturados padronizados em todas as execuções.

Fase 6 — Performance (mock)

Meta: SLO de latência com stubs.
Testes-alvo:

test_p95_latency (p95 ≤ 150ms, 50 chamadas concorrentes)
Critérios de aceite:

p95 ≤ 150ms; zero vazamentos de sessão/recursos.

Saída que o agente DEVE retornar ao final de cada fase

Formato curto, objetivo, sem prosa desnecessária.

🔎 Resumo Executivo de Falhas — Modelo por Fase
FASE: <1..6> - <nome da fase>
STATUS: <APROVADA | REPROVADA>

TESTES FALHOS (nome → motivo curto):
- <arquivo::teste> → <asserção/expectativa quebrada>
- <arquivo::teste> → <...>

HIPÓTESES DE CAUSA RAIZ:
- <bullet 1>
- <bullet 2>

EVIDÊNCIAS (curtas):
- logs: <ORCH|error|... / ORCH|complete|intent=...,confidence=...>
- métricas: p95=<ms> (se fase 6)
- diffs relevantes: <arquivo/linha> (se houver)

AÇÕES RECOMENDADAS (prioridade ↑):
1) <mudança específica de código ou tratamento>
2) <ajuste de prompt ou parsing>
3) <melhoria de log/telemetria>

BLOQUEIOS/DEPENDÊNCIAS:
- <se houver>


Observação: se STATUS = APROVADA, listar “TESTES FALHOS” vazio e manter EVIDÊNCIAS mínimas (p.ex. “todos verdes, p95=XXms”).

Saída final (fim do ciclo TDD do Orchestrator)
🧾 Resumo Executivo — Encerramento do Orchestrator
COBERTURA: <% aproximado> (X/Y testes)
ROBUSTEZ: timeouts/erros → fallback OK (evidências: ORCH|error|timeout)
CONTEXTO: <% acerto cenários contexto> (listar 1 exemplo válido)
THRESHOLDS: <comportamento verificado> (ex.: fallback<0.5; hints 0.5–0.79)
OBSERVABILIDADE: logs padronizados (trace_id, turn_id, latency_ms OK)
PERFORMANCE (mock): p95=<ms> (target ≤150ms) | p99=<ms> (opcional)

RISKS/DEBTS:
- <itens curtos e acionáveis>

PRÓXIMO PASSO:
- Integrar saída do Orchestrator ao LangGraph (nós simples “send & return”).

Diretrizes de implementação (para o agente)

Não gerar texto final no GeminiOrchestrator; apenas ClassificationResult.

Sem re-sanitização: confiar no PreprocessedMessage.

Timeout curto + 1 retry; erros → fallback (confidence=0.0).

Logs padronizados: ORCH|start, ORCH|complete, ORCH|error, com trace_id, turn_id, latency_ms.

Sem criação de componentes extras: manter-se ao escopo do arquivo e interfaces definidos pelos testes.

Entregáveis esperados do agente por fase

Código mínimo para passar os testes daquela fase.

Resumo Executivo de Falhas (modelo acima).

Nenhum novo módulo/pacote além do estipulado (orchestrator + modelos).

Sem duplicar funcionalidades do preprocessor/delivery.
