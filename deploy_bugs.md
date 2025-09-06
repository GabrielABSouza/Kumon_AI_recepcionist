Aqui está um checklist técnico, organizado por criticidade e com locais exatos para corrigir. Use como “guia de PRs” e
resolva um a um.

CRÍTICO

- Segredos expostos nos logs (GOOGLE_SERVICE_ACCOUNT_JSON)
    - Sintoma: startup log imprime o JSON completo com chave privada.
    - Causa: startup_event faz dump de todas as envs sem mascarar.
    - Correção:
    - app/main.py → função `startup_event`:
      - Remover o bloco que loga todas as variáveis ou aplicar máscara.
      - Crie helper `mask_env(var_name, value)` e NUNCA logue: `*_KEY`, `*_SECRET`, `*_TOKEN`, `*_PASSWORD`,
`GOOGLE_SERVICE_ACCOUNT_JSON`.
      - Onde ainda precisar logar, use placeholders: “[SET - N chars]”.
- Complexidade: baixa.
Complexidade: baixa.
- 
Startup Validation contraditória + dependência do IntentClassifier
    - Sintoma: “APPLICATION CANNOT START” por “Service ‘intent_classifier’ is missing dependency
‘llm_service_instance’”, e logo depois “Startup validation passed”.
    - Causa: ordem de init: intent_classifier nasce sem LLM durante optimized startup; o fallback via ServiceFactory
injeta depois. O validador não tolera essa ordem.
    - Correção:
    - app/core/startup_validation.py:
      - Em `validate_startup_requirements` e `validate_service_interfaces`, tornar `llm_service_instance` opcional se
`ProductionLLMService` estiver disponível via ServiceFactory/unified_service_resolver (downgrade para WARN).
      - Rodar essa checagem APÓS a tentativa de fallback/injeção (ver item seguinte).
    - app/core/optimized_startup.py:
      - Garanta que `llm_service` é inicializado antes de `intent_classifier` OU, após criar `llm_service`, setar
`intent_classifier.llm_service_instance = llm_service`.
    - app/core/service_registry.py:
      - Em `_initialize_intent_classifier`, se `llm_service` estiver disponível, associe-o antes de registrar o
classifier.
- Complexidade: média.
Complexidade: média.
- 
“Service initialized but instance not stored!”
    - Sintoma: health_monitor, security_manager, vector_store, cost_monitor, workflow_orchestrator, cache_manager,
memory_service iniciam e o log acusa não armazenado — “FIXED: Manually stored…” em seguida.
    - Causa: bug no fluxo de registro em optimized_startup._initialize_single_service (ou factories) — não persiste
imediatamente no registry.
    - Correção:
    - app/core/optimized_startup.py:
      - Em `_initialize_single_service`, salve o instance no registry assim que retornar; elimine o log de erro e o
“FIXED: Manually stored”.
    - app/core/service_registry.py:
      - Padronize factories para SEMPRE retornarem o instance e a chave de registro. Registre assim que criar.
- Complexidade: média.
Complexidade: média.
- 
Evolution API usando “fallback key”
    - Sintoma: “Using authentication key: fallback key” mesmo com EVOLUTION_API_KEY setado depois.
    - Causa: o cliente EvolutionAPI é inicializado antes do RailwayEnvironmentFix/settings finalizarem.
    - Correção:
    - app/api/clients/evolution_api.py (ou app/services/evolution_api.py):
      - Inicializar cliente tardiamente (lazy) quando for enviar, lendo `settings`.
    - app/main.py:
      - Mover qualquer inicialização do Evolution API para após `railway_environment_fix` e `startup_event`
completarem.
- Complexidade: baixa.

ALTA

- Reabrir conversa quando estado == COMPLETED
    - Sintoma: novo input chega com state COMPLETED/CONVERSATION_ENDED; roteamento tenta greeting → DELIVERY
(fallback), “invalid_routing”.
    - Correção:
    - app/core/workflow.py:
      - Após restaurar state e antes do primeiro node: se `current_stage == ConversationStage.COMPLETED`, resetar
`current_stage = GREETING` e `current_step = WELCOME`.
- Complexidade: baixa.
Complexidade: baixa.
- 
Planner/Resolver usando current_stage ao invés do target/pending_stage
    - Sintoma: em qualification/information/scheduling o Planner continua usando templates de GREETING; edges
“corrigem” target em cascata.
    - Correção:
    - app/core/router/response_planner.py:
      - Em `plan_and_generate(state, decision)`, derive `next_stage` de `decision.target_node` (mapping canônico) e use
esse `next_stage` para selecionar template/estratégia — NÃO `state["current_stage"]`.
    - app/prompts/template_variables.py:
      - Em `get_template_variables`, se `state["pending_stage"]` existir, use-o; fallback para `current_stage`.
    - Introduzir pending stage:
      - app/core/edges/routing.py: após roteamento, salve `state["pending_stage"]`/`state["pending_step"]` via mapping
do target; Delivery efetiva após envio.
- Complexidade: média.
Complexidade: média.
- 
Node Information enviando diretamente (quebra a via central)
    - Sintoma: “Using legacy information logic (planned_response not found) – Template response delivered in 0ms”.
    - Correção:
    - app/core/nodes/information.py:
      - Remover envio direto (Evolution API). O node deve apenas enriquecer o `state`. O envio é SEMPRE via Planner
+ DeliveryService.
- Complexidade: baixa.
Complexidade: baixa.
- 
SmartRouter devolvendo o mesmo estágio (edges corrigem)
    - Sintoma: “Corrected invalid target: qualification → information”, etc.
    - Correção:
    - app/workflows/smart_router.py:
      - Em `make_routing_decision`, evite retornar o mesmo estágio do edge. Ex.: em GREETING/proceed =>
`target_node="qualification"`; em QUALIFICATION, preferir `information` ou `scheduling` conforme regras.
      - Normalize `current_stage` para aceitar Enum/str sem `.value` inseguro (use `stage_str = getattr(stage, "value",
str(stage))` nos logs/decisões).
- Complexidade: média.
Complexidade: média.
- 
Templates bloqueados por Safety (diretrizes/persona)
    - Sintoma: Safety detecta “DIRETRIZES…”, “CECÍLIA recepcionista…”, bloqueando fallback/menu.
    - Correção:
    - app/prompts/templates/**:
      - Remover diretrizes/persona do corpo do texto enviado; manter em comentários ou metadados não injetados.
    - app/core/router/response_planner.py + app/core/services/delivery_service.py:
      - Sanitização final antes de enviar (`sanitize_for_delivery`) para remover palavras-chave perigosas, com fallback
amigável.
- Complexidade: baixa.

MÉDIA

- Google Calendar “Incorrect padding” (env → base64)
    - Sintoma: tenta base64 e falha; depois lê JSON direto e funciona.
    - Correção:
    - app/integrations/google_calendar_hardened.py (e a versão não-hardened se existir):
      - Se `GOOGLE_SERVICE_ACCOUNT_JSON` começa com “{”, tratar como JSON puro; não tentar base64.
      - Só tentar base64 se não for JSON.
- Complexidade: baixa.
Complexidade: baixa.
- 
LLM indisponível ao nascer o IntentClassifier
    - Sintoma: “LLM service not available for intent classifier, pattern matching only”.
    - Correção:
    - Já coberto na seção de startup (ordenar init e/ou tolerar dependência opcional).
- Complexidade: baixa.
Complexidade: baixa.
- 
    - Sintoma: “ConversationMemoryService initialized” e “Enhanced Cache Service initializing…” aparecem repetidas.
    - Correção:
    - app/core/health_monitor.py e locais de health check:
      - Não reinicializar serviços; apenas consultar. Adicionar guard de singleton.
- Complexidade: baixa.

BAIXA

- “file_cache is only supported with oauth2client<4.0.0”
    - Sintoma: aviso do googleapiclient; inócuo.
    - Correção: opcional — suprimir, ou mudar estratégia de cache (não prioritário).
    - Complexidade: baixa.
    - Complexidade: baixa.
- 
Mensagens de monitoramento/performance/alert temporariamente desabilitadas
    - Sintoma: logs de “temporarily disabled”.
    - Correção: se intencional para produção inicial, mantenha; caso contrário, habilitar conforme dependências.
    - Complexidade: baixa.

Ajustes Transversais (importantes para estabilizar a conversa)

- Reset pós-envio e turno único
    - app/core/edges/routing.py:
    - Após `response_planner.plan_and_generate(...)`, chamar `DeliveryService.send(state, target_node)` e encerrar o
turno (não encadear novos edges na mesma mensagem).
- app/core/services/delivery_service.py:
    - Atualizar `current_stage/current_step` a partir de `state["pending_stage"]`/`pending_step` somente após envio
bem-sucedido.
    - Se `invalid_routing`, não enviar e não marcar COMPLETED; registrar erro e manter stage atual.

- Reabertura de conversas
    - app/core/workflow.py:
    - Se `current_stage == COMPLETED` e houve novo input, resetar para `GREETING/WELCOME` antes do roteamento.

- Normalização de tipos e .value
    - app/workflows/smart_router.py, app/workflows/intelligent_threshold_system.py:
    - Aceitar Enum/str em `current_stage`; ao logar, usar `getattr(stage, "value", str(stage))`.
- app/core/state/utils.py (novo):
    - Função `normalize_state_enums(state)` a ser chamada no início do workflow.

- Mapping canônico target_node → Stage/Step
    - app/core/state/stage_mapping.py (novo):
    - `map_target_to_stage_step(target_node, current_stage)` retorna `(ConversationStage, ConversationStep)`.
- Usar esse mapping no Planner (para escolher template via pending_stage) e no DeliveryService (para atualizar o stage
final).
Usar esse mapping no Planner (para escolher template via pending_stage) e no DeliveryService (para atualizar o stage
final).
- 
Remover envio direto em qualquer node
    - app/core/nodes/**/*.py:
    - Nodes apenas enriquecem state; Planner+Delivery são responsáveis por enviar.

- Sanitização final de conteúdo
    - app/core/services/delivery_service.py:
    - `sanitize_for_delivery` antes de enviar; se bloquear, usar fallback amigável.