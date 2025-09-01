Objetivos

- Centralizar geração e envio de respostas no ResponsePlanner + DeliveryService.
- Manter CeciliaWorkflow como fonte de verdade de estágio e intenção.
- Remover “bypass do LangGraph” como caminho padrão.
- Garantir tipos consistentes em state (Enums vs strings) e tolerância a ambos.
- Corrigir erros do SmartRouter, IntentClassifier, Threshold, templates e nós.

Decisões De Arquitetura

- Stage Node: os nodes atuais por estágio (greeting, qualification, information, scheduling, validation, confirmation)
— coletam/validam e enriquecem state. Não enviam e não avançam estágio.
- Routing Node: papel exercido pelos edges (ou um node único) chamando smart_router_adapter.decide_route(state), e o
ResponsePlanner para montar planned_response. Retorna target_node.
- Delivery central: DeliveryService envia planned_response, faz safety e atualiza current_stage/current_step a partir
de um mapping canônico target_node → Stage/Step.

Refatoração: Ordem De Execução (padrão)

1. Preprocessamento → CeciliaWorkflow.
2. Stage Node do estágio atual: coleta/valida e atualiza state.
3. Routing Node: smart_router_adapter.decide_route → ResponsePlanner.plan_and_generate.
4. DeliveryService: envia planned_response, atualiza estágio/step e persiste.
5. Edges avançam para target_node.

Passos De Implementação (por arquivo)

1) app/core/workflow.py

- Remover o “bypass LangGraph” como caminho padrão.
- Garantir a sequência: Stage Node → Routing Node (edges) → DeliveryService.
- Após o edge retornar target_node e o Planner ter preenchido state["planned_response"], chamar o DeliveryService:
    - Ler state["planned_response"].
    - Efetuar safety.
    - Atualizar estágio/step via mapping canônico.
    - Persistir sessão.
- Se threshold_action == "escalate_human" ou erro crítico, permitir “bypass” pontual.
- Adicionar normalização de estado no início do processamento:
    - Chamar utilitário normalize_state_enums(state) (ver item 4) para garantir ConversationStage/ConversationStep
como Enums.

2) app/core/edges/routing.py

- Tratar oficialmente como “Routing Node”:
    - Manter chamada a smart_router_adapter.decide_route(state, "<edge_name>").
    - Sempre chamar response_planner.plan_and_generate(state, routing_decision) antes de retornar o target_node (sem
enviar).
- Garantir mapping de targets inválidos por edge:
    - GREETING: validos → ["qualification","scheduling","validation","handoff","emergency_progression"]. Se vier
fallback, remapear para qualification.
    - QUALIFICATION: defaults seguros para information.
    - INFORMATION: defaults seguros para scheduling.
    - SCHEDULING: defaults seguros para confirmation.
- Remover fluxos de envio dentro dos edges (envio fica no DeliveryService/workflow).
- Manter “intelligent validation” (quando aplicável), mas sem enviar resposta localmente.

3) app/core/router/response_planner.py

- Confirmar API padrão plan_and_generate(state, decision) (já existe).
- Corrigir/resguardar variáveis:
    - Resolver variáveis via função utilitária (garantir que não se chame classe como função).
- Implementar sanitize pré-envio:
    - Nova função interna sanitize_for_delivery(text) removendo seções de “DIRETRIZES/IMPORTANT/NUNCA/OBRIGATÓRIO” do
conteúdo final que vai ao usuário.
    - Se sanitize bloquear, usar fallback amigável (já há emergency fallback).
- Tratar “enhance_with_llm”:
    - Em plan_and_generate, se decision.threshold_action == "enhance_with_llm", usar caminho llm_rag (já implementado
em _generate_llm_rag) — e permitir usar state["response_override"] se o Stage Node tiver gerado algo específico.
- Telemetria: registrar strategy, rag_used, threshold_action, target_node, tempo de geração.

4) app/core/state/models.py (ou util novo app/core/state/utils.py)

- Adicionar utilitário:
    - normalize_state_enums(state): converte state["current_stage"] e state["current_step"] de string → Enum; tolera
já-Enums; se ausente, define defaults (GREETING, WELCOME).
    - Retornar estado coerente para que SmartRouter, Threshold, Planner e edges aceitem consistentemente Enums.
- Expor o util e chamar no início do workflow.

5) app/workflows/smart_router.py

- Corrigir uso de .value em current_stage e outros lugares:
    - Onde hoje se loga conversation_state.get("current_stage", ConversationStage.GREETING).value, fazer função
util local: stage = conversation_state.get("current_stage", ConversationStage.GREETING); stage_str = stage.value if
hasattr(stage, "value") else str(stage).
    - Aplicar isso em TODOS os logs e campos extra para evitar “‘str’ object has no attribute ‘value’”.
- Garantir self.intent_classifier não-nulo:
    - self.intent_classifier = intent_classifier (de app/core/dependencies.py). Se None, lazy import do classifier
padrão (from .intent_classifier import AdvancedIntentClassifier) com log de warning.
- Onde compara estágio: usar Enum quando possível, mas tolerar string:
    - Ex.: conversation_state.get("current_stage") == ConversationStage.INFORMATION_GATHERING deve ser precedido de
normalização do state (item 4) e/ou aceitar string "information".
- Retorno fallback como target_node:
    - Permitir, mas documentar que edges corrigem para alvo válido; também pode-se mapear fallback → qualification
dentro do Adapter (ver item 7).

6) app/workflows/intelligent_threshold_system.py

- Ajustar _get_stage_multiplier (ou lógica de obtenção do multiplicador):
    - Aceitar ConversationStage Enum OU str.
    - Converter com segurança e retornar multiplicador sem warnings (“Invalid stage type”).
- Revisar determine_action e cálculo de penalidades:
    - Evitar que saudações triviais caiam em human_handoff/fallback por thresholds agressivos. Ajustar penalidades base
ou mínimos, especialmente no GREETING.
- Opcional: se current_stage == GREETING, reduzir probabilidade de enhance_with_llm (templates bastam), salvo
sinalização do Stage Node (ex.: state["llm_required"]=True).

7) app/core/router/smart_router_adapter.py

- Garantir fallback robusto:
    - Em _fallback_decision, manter mapping por estágio (já existe).
    - Se o SmartRouter retornar target_node="fallback", aplicar mapping mais assertivo por contexto do edge (ex.:
greeting→qualification), e propagar isso em core_decision.
- Persistir routing_info no state como hoje, porém acrescentar stage_type e target_validated (true/false) para
diagnósticos de stuck.

8) app/workflows/intent_classifier.py

- Corrigir erro de contexto:
    - Remover qualquer acesso a context.conversation_state (o ConversationContext não tem esse atributo).
    - Garantir que _get_conversation_context não tente acessar atributos inexistentes — só copiar dados do state
via .get(...).
- Recalibrar thresholds para “greeting”:
    - Evitar que mensagens curtas (“oi”, “olá”, nomes) caiam em escalate_human.
    - Confirmar peso/boost do GREETING e reduzir penalidades iniciais.

9) app/core/services/delivery_service.py (ou local equivalente)

- Atualizar estágio/step só com target_node válido (não “fallback”):
    - Se target_node == "fallback": não avançar estágio; ou remapear greeting→qualification antes de atualizar.
    - Adicionar mapping canônico target_node → ConversationStage/Step.
- Executar safety final usando sanitize_for_delivery do Planner (ou uma função compartilhada).
- Garantir idempotência por message_id (já há).
- Logar: old_stage, new_stage, target_node, threshold_action.

10) app/core/templates e app/prompts

- Remover “DIRETRIZES/IMPORTANT/NUNCA/OBRIGATÓRIO” dos templates que são enviados ao usuário:
    - Mover diretrizes para comentários no arquivo ou metadados (não parte do texto final).
    - Alternativa: o PromptManager.get_prompt pode recortar tudo acima de um marcador “--- user-output-below ---”.
- Garantir que template_variable_resolver não dispare exceção; providenciar defaults amigáveis (já há “responsável”).

11) app/services/conversation_memory_service.py e afins

- Padronizar retorno de sessão/estado:
    - Se retornar dicionários, converter para CeciliaState canônico no workflow antes de uso (util do item 4).
    - Evitar AttributeError: “‘dict’ object has no attribute 'current_stage'”.
- Circuit breakers: após correções, resetar contadores e revisar mensagens.


- Opção A: criar a tabela workflow_checkpoints com migração.
- Opção B: desabilitar leitura de checkpoints enquanto schema não existe (feature flag), logando info.

13) Nodes/Enums de passos

- Corrigir AttributeError: 'SUBJECT_INTEREST':
    - Incluir SUBJECT_INTEREST em ConversationStep se esse passo for real, OU
    - Atualizar o node de qualification para usar o step válido existente (ex.: PARENT_NAME_COLLECTION, etc.), mantendo
consistência.

Tópicos De “.value” E Tipos (Itens Críticos)

- Onde loga/usa .value (SmartRouter, telemetria, regras), trocar por acesso seguro:
    - v = x.value if hasattr(x, "value") else x.
- Normalizar current_stage/current_step previamente (item 4) e sempre tolerar Enum/str.
- Threshold: remover warnings e aceitar tipos mistos sem quebrar.

Critérios De Aceitação

- Mensagens “oi”, “olá”, e “Gabriel” resultam em:
    - SmartRouter → RoutingDecision com target válido (ex.: greeting→qualification).
    - ResponsePlanner gera planned_response sem exceptions.
    - DeliveryService envia e atualiza estágio para QUALIFICATION (não fica preso em GREETING).
- Sem “Invalid stage type” no Threshold.
- Sem “‘str’ object has no attribute ‘value’” em SmartRouter.
- Sem “‘ConversationContext’ object has no attribute 'conversation_state’”.
- Sem bloqueio de template por “DIRETRIZES…”.
- Sem “bypass LangGraph” em GREETING no caminho normal.

Testes Rápidos (smoke)

- Caso 1: “oi”
    - Esperado: GREETING → QUALIFICATION; texto via template; nenhum erro.
- Caso 2: “Gostaria de saber mais sobre o Kumon de matemática”
    - Esperado: GREETING → INFORMATION; enhance_with_llm opcional; RAG pode ser usado; resposta coerente.
- Caso 3: “Quero agendar uma visita amanhã”
    - Esperado: QUALIFICATION/INFORMATION → SCHEDULING; coleta campos obrigatórios; sem fallback.

Ordem De Execução Sugerida

1. Remover bypass nos edges/workflow; ligar Planner e Delivery no fluxo normal.
2. Normalizar Enums de state e corrigir .value no SmartRouter.
3. Consertar IntentClassifier (contexto) e Threshold (multiplier).
4. Ajustar DeliveryService (stage update + fallback mapping) e templates (remover diretrizes).
5. Endurecer mapeamentos de target nos edges (sempre alvos válidos).
6. Tratar SUBJECT_INTEREST e checkpoint (tabela ou feature flag).

Observabilidade

- Antes de cada decisão de roteamento, logar:
    - stage_type: tipo real de current_stage (str/Enum).
    - target_node recebido, target_validated após mapping.
    - threshold_action, final_confidence, tempos do Planner/Delivery.
- Métrica “stuck_in_greeting”: contador de respostas enviadas em GREETING sem progressão em N mensagens.

1. Stage Node sem gerar resposta

- Regra: Stage Nodes (greeting/qualification/information/…) NÃO enviam nem montam a resposta final.
- Comportamento: Retornam apenas atualizações de state (collected_data, metrics, hints para LLM/RAG).
- Implementação:
    - Garantir que nenhum Stage Node chame ResponsePlanner ou DeliveryService.
    - Opcional: permitir state["response_override"] quando o estágio precisa produzir uma resposta específica (o
Planner usa isso no fim).
- Onde tocar:
    - app/core/nodes/*.py: Remover qualquer chamada de envio/entrega; manter apenas coleta/validação e updates no
state.

2. Routing Node nos edges vs node único

- Recomendação prática: manter nos edges atuais (menos refatoração, menor risco).
    - Edges já chamam smart_router_adapter.decide_route(...) e response_planner.plan_and_generate(...).
    - Padronize a sequência em TODOS os edges de estágio.
- Onde tocar:
    - app/core/edges/routing.py:
    - Depois do Stage Node, chamar `smart_router_adapter.decide_route(state, "<edge_name>")`.
    - Em seguida `response_planner.plan_and_generate(state, routing_decision)`.
    - Retornar apenas `target_node` (sem enviar).

3. Normalização de state no início

- Decisão: Normalizar assim que o workflow montar/restaurar o CeciliaState, antes de qualquer Stage/Router/Threshold.
- Local exato:
    - app/core/workflow.py (logo após carregar/restaurar sessão/estado, antes de executar o primeiro node/edge):
    - `from app.core.state.utils import normalize_state_enums`
    - `state = normalize_state_enums(state)`
- Observação: É seguro reaplicar nas bordas críticas (ex.: início dos edges) como guard rail.

4. Mapping canônico target_node → Stage/Step

- Decisão: Centralizar em util compartilhado e usar no DeliveryService (fonte de verdade única).
- Implementação:
    - Criar app/core/state/stage_mapping.py com:
    - `def map_target_to_stage_step(target_node: str, current_stage: ConversationStage) -> tuple[ConversationStage,
ConversationStep]: ...`
- Uso:
    - app/core/services/delivery_service.py:
    - Após obter `target_node`, aplicar `map_target_to_stage_step(...)` para atualizar `current_stage/current_step`.
- Edges: não atualizam estágio; só retornam o target_node.

5. Templates e sanitização

- Decisão: Sanitização final deve ocorrer no DeliveryService, moments antes do envio (single choke point).
- Implementação:
    - app/core/services/delivery_service.py:
    - Chamar `sanitize_for_delivery(text)` antes de enviar (remove DIRETRIZES/IMPORTANT/NUNCA/OBRIGATÓRIO e similares).
    - Se sanitização bloquear, usar fallback amigável (mensagem de emergência do Planner).
- Extra (higiene de base): ajustar templates para não conter diretrizes no corpo enviado ao usuário:
    - app/prompts/templates/* e PromptManager: mover diretrizes para comentários/metadados, ou usar separador “---
user-output-below ---”.

6. enhance_with_llm com Stage Node

- Decisão: ResponsePlanner controla a geração em modo llm_rag, mas respeita state["response_override"] se existir.
- Implementação:
    - app/core/router/response_planner.py:
    - Em `plan_and_generate(...)`, se `state.get("response_override")` existir, usar como resposta final (com
sanitização e metadata).
    - Caso contrário, no `threshold_action == "enhance_with_llm"`, usar `_generate_llm_rag(...)` (com heurística
`_should_use_rag` + hints do Stage Node em `state["rag_query"]`, `state["knowledge_tags"]`, etc.).

Pontos críticos adicionais (para fechar os gaps que travam o GREETING)

- .value e tipos:
    - app/workflows/smart_router.py: substituir acessos diretos .value por extração segura:
    - `stage = state.get("current_stage", ConversationStage.GREETING)`
    - `stage_str = stage.value if hasattr(stage, "value") else str(stage)`
- app/workflows/intelligent_threshold_system.py: _get_stage_multiplier aceitar Enum/str sem warning.
- normalize_state_enums(state) (item 3) garante base consistente; ainda assim, tolerância a ambos os tipos localmente.
- IntentClassifier:
    - app/workflows/intent_classifier.py: remover acessos a context.conversation_state (não existe no dataclass).
    - Recalibrar thresholds/penalidades para GREETING (evitar human_handoff em “oi/olá/nome”).
- Fallback e avanço de estágio:
    - DeliveryService: não atualizar estágio quando target_node == "fallback". Opcional: remapear
fallback→qualification SOMENTE quando em GREETING, para destravar (com telemetria).
    - Edges: manter validação de target_node e corrigir alvos inválidos (ex.: greeting: fallback→qualification), mas
evitar enviar por ali.
- Remover bypass padrão:
    - app/core/workflow.py e edges: “Bypassing LangGraph” só em erro crítico ou escalate_human. Caminho normal deve
processar edge e depois DeliveryService.
- Checkpoint:
    - app/services/workflow_state_repository.py: desativar leitura se tabela workflow_checkpoints não existir (flag),
ou criar migração.
- Enums de passos:
    - Corrigir SUBJECT_INTEREST no ConversationStep ou substituir pela constante válida nos nodes de qualificação.