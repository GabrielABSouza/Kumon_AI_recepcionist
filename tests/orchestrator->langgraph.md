Plano de Testes — Gemini Orchestrator → LangGraph (com Estado)
Objetivo

Garantir que:

a intenção do Gemini acione o nó correto do LangGraph,

o estágio seja atualizado e persistido para a próxima interação,

apenas respostas em português sejam retornadas, e

ocorra uma única resposta por turno.

Fase A — Contrato & Mapeamento (Gemini → Grafo)

Escopo: o output do orquestrador dispara o nó correto.

Principais testes (exemplos de nomes):

test_map_greeting_to_greeting_node()

test_map_information_request_to_information_node()

test_map_qualification_to_qualification_node()

test_map_scheduling_to_scheduling_node()

test_map_fallback_to_fallback_node()

test_unknown_intent_routes_to_fallback()

Saídas esperadas:

node_executado == <nó_esperado>

response_text presente (não vazio)

lang == "pt-br" (ver Fase D)

stage_update definido (ver Fase B)

Fase B — Atualização de Estágio (State Manager)

Escopo: após cada nó, o estágio correto é calculado e persistido.

Principais testes:

test_stage_transition_greeting_to_qualification()

test_stage_stays_in_information_when_followup_questions()

test_stage_switch_to_scheduling_after_confirmed_interest()

test_stage_reset_to_greeting_on_new_conversation()

test_stage_persists_across_turns_redis()

test_stage_persists_across_turns_db_fallback_to_cache()

test_stage_update_atomic_single_turn()

test_stage_read_after_crash_recovery()

Saídas esperadas:

stage_before, stage_after coerentes com a política

Persistência: state_repo.get(conversation_id).stage == esperado

Operações atômicas (sem “skip”/condição de corrida)

Fase C — Execução dos Nós (OpenAI Stub/Mock)

Escopo: cada nó usa o prompt correto e retorna conteúdo esperado.

Principais testes:

test_greeting_node_prompt_contract()

test_information_node_uses_topic_entities()

test_qualification_node_collects_required_fields()

test_scheduling_node_confirms_slots()

test_fallback_node_minimal_helpful_response()

test_node_returns_single_message_only()

Saídas esperadas:

response_text não vazio e uma única mensagem por turno

metadata.routing_decision == "final" (sem encadear nós)

next_actions == None (nós não “chamam” outros nós)

pt_only_enforced == True (ver Fase D)

Fase D — Política de Idioma (PT-BR Apenas)

Escopo: qualquer saída deve estar em português.

Principais testes:

test_language_enforcement_basic_greeting_pt()

test_language_enforcement_info_answers_pt()

test_language_enforcement_no_english_allowed()

test_language_enforcement_mixed_input_output_pt()

Saídas esperadas:

Detector simples/heurístico/regex garantindo PT-BR

Se LLM tentar outra língua → normalizar para PT no pós-processamento

Flag de validação: language_policy_passed == True

Fase E — Persistência & Continuidade (Próximas Interações)

Escopo: o estado atualizado guia a próxima mensagem.

Principais testes:

test_next_turn_reads_previous_stage_from_store()

test_context_entities_merge_across_turns()

test_idempotency_same_message_not_advances_stage()

test_concurrent_turns_isolated_by_conversation_id()

test_state_consistency_after_timeout_or_retry()

Saídas esperadas:

Nova mensagem usa stage previamente salvo

entities/context acumulados conforme política

Idempotência: mesmo message_id não altera estado novamente

Fase F — Resiliência & Erros

Escopo: tolerância a falhas sem quebrar o fluxo/estado.

Principais testes:

test_orchestrator_timeout_returns_fallback_and_keeps_stage()

test_node_failure_returns_fallback_and_keeps_stage()

test_state_write_failure_fallback_to_cache_and_warn()

test_language_policy_violation_triggers_rewrite_pt()

Saídas esperadas:

Fallback amigável em PT-BR

Estado não corrompido

Logs estruturados de erro (ORCH|error / GRAPH|error / STATE|error)

Fase G — Observabilidade & Métricas

Escopo: logs e métricas para depuração e SLOs.

Principais testes:

test_logs_for_each_phase_present()

test_trace_propagation_gemini_to_graph_to_state()

test_latency_metrics_recorded_per_stage()

test_error_logs_on_node_exception()

Saídas esperadas:

Logs: ORCH|start/complete, GRAPH|node_start/node_complete, STATE|set/get

trace_id, turn_id propagados

latency_ms por fase

Fase H — Performance (Smoke)

Escopo: rápida verificação de SLIs.

Principais testes:

test_p95_under_target_for_single_turn() (com stub de LLM)

test_no_extra_hops_single_message() (1 nó, 1 resposta)

test_state_ops_under_10ms_avg() (mock de store)

Saídas esperadas:

P95 (stub) < alvo definido

Nenhum “loop” de nós

Persistência rápida

Notas de Implementação

Stubs/Mocks para OpenAI e storage (Redis/DB) para testes determinísticos.

Validador de idioma simples (heurístico/regex) + pós-processamento para PT.

StateManager com API mínima: get(conversation_id), set_stage(conversation_id, stage), append_context(...) — operações atômicas e idempotentes.

Contrato claro: cada nó retorna response_text e stage_update; não dispara outros nós, não envia mensagem direta.

Pronto. Isso cobre o fluxo Gemini → LangGraph (com estado), exige PT-BR sempre e garante persistência para a próxima interação.

📌 Adendo — Persistência, Estado e Idempotência (MVP)
1. LangGraph vs Custom Implementation

Decisão: Manter LangGraph oficial.

Justificativa: Evita complexidade desnecessária, garante estabilidade e permite evoluir gradualmente.

2. Estado Híbrido (Postgres + Redis)

Postgres: fonte de verdade, armazena o estado persistente das conversas.

Redis: suporte auxiliar (locks, deduplicação, cache).

Redis pode falhar sem comprometer o fluxo; Postgres mantém consistência.

3. Rollback de Estado

MVP simplificado: rollback completo não é necessário.

Estratégia: se falhar após escrita em Redis, o sistema se reidrata a partir do Postgres.

Futuro: rollback transacional pode ser avaliado em versões posteriores.

4. Idempotência

Implementar chave única para cada mensagem:

idempotency_key = f"{conversation_id}:{message_id}"


Antes de gravar no Postgres/Redis, verificar se a chave já existe.

Se existir → descartar para evitar duplicação.

Garante consistência mesmo em cenários de retry ou reprocessamento.

📌 Plano de Testes — Integração Gemini Orchestrator ↔ LangGraph Nodes ↔ Delivery
Objetivos

Validar a correta passagem de intenções do Gemini para os nós do LangGraph.

Garantir persistência de estado entre interações (Postgres como fonte de verdade, Redis auxiliar).

Assegurar idempotência no pipeline para evitar duplicações em retries/reprocessamentos.

Garantir que todas as respostas sejam em português.

🔹 Fase 1 — Execução Básica de Nós

Testes

Executar cada nó isolado (greeting, information, qualification, scheduling, fallback).

Verificar se sempre retorna resposta em português.

Confirmar que state["stage"] é atualizado corretamente.

Output esperado: todas as respostas em português + stage atualizado em Postgres.

🔹 Fase 2 — Persistência de Estado

Testes

Processar múltiplas mensagens sequenciais e confirmar que o stage é mantido entre interações.

Simular falha de Redis e confirmar que Postgres reidrata corretamente.

Output esperado: estado consistente em Postgres mesmo com falha em Redis.

🔹 Fase 3 — Idempotência

Testes

Reprocessar a mesma mensagem (mesmo message_id).

Confirmar que nenhuma nova resposta é enviada ao usuário.

Validar que o idempotency_key (conversation_id:message_id) está armazenado em Postgres.

Testar retries automáticos (delivery falha 1x, depois sucesso) e confirmar que apenas uma resposta final chega ao usuário.

Output esperado: nenhuma duplicação de mensagens; logs mostram IDEMPOTENT|skip nos casos de reprocessamento.

🔹 Fase 4 — Encadeamento com Gemini Orchestrator

Testes

Simular classificação correta → verificar que nó certo é chamado e estado é atualizado.

Simular classificação ambígua → verificar fallback + estado persistido como fallback.

Confirmar que latência total < 800ms (objetivo MVP).

Output esperado: rotas corretas + persistência confiável + performance dentro da meta.

🔹 Fase 5 — End-to-End com Delivery

Testes

Mensagem WhatsApp → Preprocessor → Gemini Orchestrator → LangGraph Node → Delivery.

Confirmar que apenas uma resposta em português é entregue por turno.

Testar erro de delivery (ex.: HTTP 500) → retry com sucesso → apenas uma resposta entregue.

Output esperado: entrega única garantida por idempotência; estado atualizado no Postgres.
