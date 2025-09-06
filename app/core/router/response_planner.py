from typing import Dict, Any, Optional, Union
import time
import logging
import hashlib
from enum import Enum
from dataclasses import asdict
from ...prompts.manager import prompt_manager
from ...prompts.template_variables import template_variable_resolver
from ...core.service_factory import get_langchain_rag_service
from ...services.production_llm_service import ProductionLLMService
from ..state.models import CeciliaState, ConversationStage
from ...workflows.contracts import RoutingDecision, MessageEnvelope, ensure_outbox, normalize_outbox_messages, OUTBOX_KEY
from .smart_router_adapter import CoreRoutingDecision, routing_mode_from_decision, normalize_rd_obj
from ..contracts.outbox import OutboxItem, enqueue_to_outbox
from ..outbox_store import persist_outbox

logger = logging.getLogger(__name__)


def _coerce_stage(stage_val) -> ConversationStage:
    """Coerce stage value to ConversationStage enum safely."""
    if isinstance(stage_val, ConversationStage):
        return stage_val
    if isinstance(stage_val, str):
        try:
            # Try uppercase first (most common)
            return ConversationStage[stage_val.upper()]
        except (KeyError, AttributeError):
            try:
                # Try as-is
                return ConversationStage(stage_val.lower())
            except (ValueError, AttributeError):
                pass
    # Default fallback
    logger.warning(f"Could not coerce stage value '{stage_val}' to enum, using GREETING")
    return ConversationStage.GREETING


def ensure_idempotency_key(item: OutboxItem, phone_number: str, turn_id: str) -> None:
    """
    Garante que OutboxItem tem idempotency_key para deduplicação
    
    Args:
        item: OutboxItem para processar
        phone_number: Número do telefone
        turn_id: ID do turno do TurnController
    """
    if item.idempotency_key:
        return
    
    # Gera chave determinística baseada no turno
    raw = f"{phone_number}:{turn_id}:delivery"
    item.idempotency_key = hashlib.sha256(raw.encode()).hexdigest()[:16]


class ResponsePlanner:
    """
    Serviço central de geração de resposta baseado na decisão do SmartRouter.
    
    Responsabilidades:
    - proceed: PromptManager (templates) com variáveis resolvidas
    - enhance_with_llm: LLM + RAG opcional para queries complexas
    - fallback_level1/2: Templates de fallback simples
    - handoff: Template de transferência humana
    
    Saída: popula state["planned_response"] e state["response_metadata"]
    """
    
    def __init__(self):
        self.template_mappings = {
            # Greeting stage mappings
            ("greeting", "welcome"): "kumon:greeting:welcome:initial",
            ("greeting", "parent_name"): "kumon:greeting:collection:parent_name", 
            ("greeting", "child_interest"): "kumon:greeting:response:child_interest",
            ("greeting", "self_interest"): "kumon:greeting:response:self_interest",
            
            # Qualification stage mappings
            ("qualification", "age_feedback"): "kumon:qualification:age_feedback:ideal_age",
            ("qualification", "age_too_young"): "kumon:qualification:age_feedback:too_young",
            ("qualification", "age_adult"): "kumon:qualification:age_feedback:adult_age",
            
            # Scheduling stage mappings  
            ("scheduling", "appointment_start"): "kumon:scheduling:introduction:appointment_start",
            ("scheduling", "saturday_restriction"): "kumon:scheduling:restriction:saturday_unavailable",
            
            # Information stage mappings
            ("information", "pricing"): "kumon:information:pricing:complete_pricing",
            ("information", "methodology"): "kumon:information:methodology:overview",
            ("information", "programs"): "kumon:information:programs:overview"
        }
    
    async def plan_and_generate(self, state: CeciliaState, decision: Union[RoutingDecision, CoreRoutingDecision, Dict[str, Any]]) -> None:
        """
        Planeja e gera resposta baseada na decisão do SmartRouter.
        Popula state["planned_response"] e state["response_metadata"].
        """
        start_time = time.time()
        # Defensive: accept raw dict decisions in emergency paths
        if isinstance(decision, dict):
            try:
                from .smart_router_adapter import CoreRoutingDecision as _CRD
                decision = _CRD(
                    target_node=decision.get("target_node", "fallback"),
                    confidence=float(decision.get("confidence", 0.0) or 0.0),
                    reasoning=decision.get("reasoning", ""),
                    rule_applied=decision.get("rule_applied", "unknown"),
                    threshold_action=decision.get("threshold_action", "fallback_level1"),
                    intent_confidence=float(decision.get("intent_confidence", 0.0) or 0.0),
                    pattern_confidence=float(decision.get("pattern_confidence", 0.0) or 0.0),
                )
            except Exception:
                # Minimal shim if import fails for any reason
                class _Shim:
                    def __init__(self, d: Dict[str, Any]):
                        self.target_node = d.get("target_node", "fallback")
                        self.confidence = float(d.get("confidence", 0.0) or 0.0)
                        self.reasoning = d.get("reasoning", "")
                        self.rule_applied = d.get("rule_applied", "unknown")
                        self.threshold_action = d.get("threshold_action", "fallback_level1")
                        self.intent_confidence = float(d.get("intent_confidence", 0.0) or 0.0)
                        self.pattern_confidence = float(d.get("pattern_confidence", 0.0) or 0.0)
                decision = _Shim(decision)  # type: ignore

        threshold_action = decision.threshold_action
        
        try:
            logger.info(f"Planning response with strategy: {threshold_action}")
            
            if threshold_action == "proceed":
                response_text = await self._generate_template(state, decision)
                strategy_used = "template"
                
            elif threshold_action == "enhance_with_llm":
                response_text = await self._generate_llm_rag(state, decision)
                strategy_used = "llm_rag"
                
            elif threshold_action in ["fallback_level1", "fallback_level2"]:
                response_text = await self._generate_fallback(state, decision)
                strategy_used = f"fallback_{threshold_action[-1]}"
                
            elif threshold_action == "escalate_human":
                response_text = await self._generate_handoff(state)
                strategy_used = "handoff"
                
            else:
                logger.warning(f"Unknown threshold_action: {threshold_action}, using fallback")
                response_text = await self._generate_fallback(state, decision)
                strategy_used = "fallback_unknown"
            
            # Populate state with planned response
            state["planned_response"] = response_text
            state["response_metadata"] = {
                "strategy": strategy_used,
                "threshold_action": threshold_action,
                "target_node": decision.target_node,
                "confidence": decision.confidence,
                "generation_time_ms": round((time.time() - start_time) * 1000, 2),
                "timestamp": time.time()
            }
            
            logger.info(
                f"Response planned successfully: {strategy_used} "
                f"({state['response_metadata']['generation_time_ms']}ms)"
            )
            
        except Exception as e:
            logger.error(f"Response planning failed: {e}", exc_info=True)
            # Emergency fallback - always provide a response
            response_text = "Oi! Sou o assistente da Kumon. Como posso ajudar você hoje?"
            state["planned_response"] = response_text
            state["response_metadata"] = {
                "strategy": "emergency_fallback",
                "error": str(e),
                "generation_time_ms": round((time.time() - start_time) * 1000, 2)
            }
        
        # CRITICAL: Always populate outbox snapshot for delivery
        # This ensures outbox_count > 0 even on errors
        response_text = state.get("planned_response", "")
        if response_text:
            state["_planner_snapshot_outbox"] = [{
                "text": response_text,
                "channel": "whatsapp",
                "meta": {
                    "source": "response_planner",
                    "route": decision.target_node if hasattr(decision, 'target_node') else "unknown",
                    "strategy": state.get("response_metadata", {}).get("strategy", "unknown")
                }
                # idempotency_key will be generated during persistence
            }]
            logger.info(f"PLANNER|outbox_populated|count={len(state.get('_planner_snapshot_outbox', []))}")
        else:
            # Absolute fallback - should never happen but be defensive
            state["_planner_snapshot_outbox"] = [{
                "text": "Olá! Como posso ajudar?",
                "channel": "whatsapp",
                "meta": {"source": "response_planner_fallback"}
            }]
            logger.warning("PLANNER|empty_response|using_absolute_fallback")
    
    async def _generate_template(self, state: CeciliaState, decision: Union[RoutingDecision, CoreRoutingDecision]) -> str:
        """Gera resposta usando PromptManager (templates)"""
        # Determine template name based on stage + intent
        raw_stage = state.get("current_stage", "greeting")
        
        # Coerce stage to enum safely
        stage = _coerce_stage(raw_stage)
        
        # Log if coercion was needed
        if not isinstance(raw_stage, ConversationStage):
            logger.info(f"ResponsePlanner: coerced stage from {type(raw_stage).__name__}('{raw_stage}') to {stage.name}")
        
        # Get intent from routing_info if available, otherwise derive from target_node
        routing_info = state.get("routing_info", {})
        raw_intent = routing_info.get("intent_category")
        
        # Map classification intents to template intents
        intent_mapping = {
            "greeting": "welcome",
            "information_request": "general", 
            "scheduling": "appointment_start",
            "clarification": "general",
            "handoff": "general"
        }
        
        if raw_intent and raw_intent in intent_mapping:
            intent = intent_mapping[raw_intent]
        elif decision.target_node == "greeting":
            intent = "welcome"
        elif decision.target_node == "information":
            intent = "general"
        elif decision.target_node == "scheduling":
            intent = "appointment_start"
        else:
            intent = "general"
        
        # Map to template name
        template_key = (stage.lower(), intent.lower())
        template_name = self.template_mappings.get(template_key)
        
        if not template_name:
            # Fallback to generic template
            template_name = f"kumon:{stage}:response:general"
            logger.warning(f"No specific template for {template_key}, using {template_name}")
        
        # Resolve template variables
        variables = template_variable_resolver.get_template_variables(state)
        
        # Get template response
        response = await prompt_manager.get_prompt(
            name=template_name,
            variables=variables,
            conversation_state=state
        )
        
        # Store metadata
        state["response_metadata"] = state.get("response_metadata", {})
        state["response_metadata"].update({
            "prompt_used": template_name,
            "variables_resolved": len(variables),
            "sources": ["template"]
        })
        
        return response
    
    async def _generate_llm_rag(self, state: CeciliaState, decision: Union[RoutingDecision, CoreRoutingDecision]) -> str:
        """Gera resposta usando LLM + RAG opcional"""
        user_message = state.get("last_user_message", "")
        
        # Determine if RAG is needed (for information queries)
        needs_rag = self._should_use_rag(user_message, decision)
        rag_context = ""
        
        if needs_rag:
            try:
                rag_service = await get_langchain_rag_service()
                rag_result = await rag_service.query(
                    question=user_message,
                    search_kwargs={"score_threshold": 0.3, "k": 3},
                    include_sources=False
                )
                
                if rag_result.answer:
                    rag_context = f"\nContext from knowledge base:\n{rag_result.answer}\n"
                    logger.info("RAG context retrieved successfully")
                
            except Exception as e:
                logger.warning(f"RAG retrieval failed: {e}")
        
        # Build enhanced prompt
        variables = template_variable_resolver.get_template_variables(state)
        system_context = self._build_system_context(state, variables)
        
        enhanced_prompt = f"""
{system_context}

User question: {user_message}
{rag_context}

Provide a helpful, personalized response as Cecília from Kumon Vila A.
Be warm, professional, and focus on how Kumon can help the student.
"""
        
        # Call LLM service
        llm_service = ProductionLLMService()
        response = await llm_service.generate_response(enhanced_prompt)
        
        # Store metadata
        state["response_metadata"] = state.get("response_metadata", {})
        state["response_metadata"].update({
            "prompt_used": "llm_enhanced",
            "rag_used": needs_rag,
            "variables_resolved": len(variables),
            "sources": ["llm"] + (["rag"] if needs_rag else [])
        })
        
        return response
    
    async def _generate_fallback(self, state: CeciliaState, decision: Union[RoutingDecision, CoreRoutingDecision]) -> str:
        """Gera resposta de fallback simples"""
        fallback_level = decision.threshold_action
        
        # Determine appropriate fallback template
        if fallback_level == "fallback_level1":
            # More informative fallback
            template_name = "kumon:fallback:level1:general"
        else:  # fallback_level2
            # Very simple, safe fallback
            template_name = "kumon:fallback:level2:basic"
        
        try:
            variables = template_variable_resolver.get_template_variables(state)
            response = await prompt_manager.get_prompt(
                name=template_name,
                variables=variables,
                conversation_state=state
            )
            
            state["response_metadata"] = state.get("response_metadata", {})
            state["response_metadata"].update({
                "prompt_used": template_name,
                "fallback_level": fallback_level,
                "sources": ["fallback_template"]
            })
            
            return response
            
        except Exception as e:
            logger.warning(f"Fallback template failed: {e}")
            return self._get_emergency_response()
    
    async def _generate_handoff(self, state: CeciliaState) -> str:
        """Gera resposta de transferência humana"""
        try:
            variables = template_variable_resolver.get_template_variables(state)
            response = await prompt_manager.get_prompt(
                name="kumon:handoff:transfer:human_contact",
                variables=variables,
                conversation_state=state
            )
            
            state["response_metadata"] = state.get("response_metadata", {})
            state["response_metadata"].update({
                "prompt_used": "kumon:handoff:transfer:human_contact",
                "sources": ["handoff_template"]
            })
            
            return response
            
        except Exception as e:
            logger.warning(f"Handoff template failed: {e}")
            return (
                "Para melhor atendimento, nossa equipe especializada "
                "entrará em contato:\n\n"
                "📞 **(51) 99692-1999**\n"
                "🕐 Segunda a Sexta, 8h às 18h"
            )
    
    def _should_use_rag(self, user_message: str, decision: RoutingDecision) -> bool:
        """Determina se deve usar RAG baseado na query"""
        message_lower = user_message.lower()
        
        # Use RAG for complex information queries
        rag_triggers = [
            "metodologia", "como funciona", "material", "programa",
            "matemática", "português", "inglês", "preço", "valor",
            "horário", "idade", "série"
        ]
        
        return any(trigger in message_lower for trigger in rag_triggers)
    
    def _build_system_context(self, state: CeciliaState, variables: Dict[str, Any]) -> str:
        """Constrói contexto do sistema para LLM"""
        parent_name = variables.get("parent_name", "")
        child_name = variables.get("child_name", "")
        stage = state.get("current_stage", "")
        
        context = """
You are Cecília, the AI receptionist for Kumon Vila A in Porto Alegre.
You're professional, warm, and knowledgeable about the Kumon method.

Key information:
- Location: Rua Amoreira, 571, Salas 6 e 7, Jardim das Laranjeiras
- Phone: (51) 99692-1999
- Hours: Monday to Friday, 8am to 6pm
- Programs: Mathematics, Portuguese, English
- Investment: R$ 375/month per subject + R$ 100 enrollment fee
"""
        
        if parent_name:
            context += f"\n- Parent's name: {parent_name}"
        if child_name:
            context += f"\n- Student's name: {child_name}"
        if stage:
            context += f"\n- Conversation stage: {stage}"
            
        return context
    
    def _get_emergency_response(self) -> str:
        """Resposta de emergência quando tudo falha"""
        return (
            "Obrigada pelo seu interesse no Kumon Vila A! 😊\n\n"
            "Para melhor atendimento, entre em contato:\n"
            "📞 **(51) 99692-1999**\n"
            "🕐 Segunda a Sexta, 8h às 18h"
        )

# Singleton instance
response_planner = ResponsePlanner()

# ========== COMPATIBILITY LAYER ==========

@staticmethod  
def plan(state: dict) -> dict:
    """
    Static method for backward compatibility with old calls to ResponsePlanner.plan()
    
    Redirects to the proper response_planner_node function which handles V2 architecture.
    
    Args:
        state: Conversation state
        
    Returns:
        dict: Updated state with intent_result
    """
    return response_planner_node(state)

# Add static method to class
ResponsePlanner.plan = plan


# ========== NEW FACADE FUNCTIONS FOR MIGRATION ==========

def resolve_channel(state: Dict[str, Any]) -> str:
    """Resolve channel from state context"""
    channel_mapping = state.get("channel_mapping", {})
    default_channel = state.get("default_channel", "whatsapp")
    
    # Logic to determine channel based on state
    # For now, use whatsapp as default but preserve existing logic
    return channel_mapping.get("preferred", default_channel)


def render_template(template_name: str, state: Dict[str, Any]) -> str:
    """Render template with state variables"""
    variables = template_variable_resolver.get_template_variables(state)
    
    # Use existing prompt_manager infrastructure
    import asyncio
    try:
        response = asyncio.run(prompt_manager.get_prompt(
            name=template_name,
            variables=variables,
            conversation_state=state
        ))
        return response
    except Exception as e:
        logger.warning(f"Template render failed: {e}")
        return f"Obrigada pelo contato! Para atendimento, ligue (51) 99692-1999."


def plan_response(state: dict, routing_decision: dict = None) -> dict:
    """
    Main API for ResponsePlanner - generates response and enqueues to outbox
    
    Args:
        state: Conversation state
        routing_decision: Optional routing decision (uses state["routing_decision"] if not provided)
        
    Returns:
        dict: Intent result with delivery_payload
    """
    
    # Use provided routing_decision or get from state
    if routing_decision:
        state["routing_decision"] = routing_decision
    
    # Call the node implementation
    updated_state = response_planner_node(state)
    
    # Extract intent result for routing_and_planning compatibility
    intent_result = {
        "delivery_payload": {
            "messages": []
        },
        "planned_response": updated_state.get("planned_response", ""),
        "response_metadata": updated_state.get("response_metadata", {}),
        "routing_mode": updated_state.get("response_metadata", {}).get("mode", "unknown")
    }
    
    # Convert outbox messages to delivery_payload format for backward compatibility
    outbox = updated_state.get(OUTBOX_KEY, [])
    for msg in outbox:
        if isinstance(msg, dict) and "text" in msg:
            intent_result["delivery_payload"]["messages"].append({
                "text": msg["text"],
                "type": msg.get("meta", {}).get("type", "text"),
                "channel": msg.get("channel", "whatsapp")
            })
    
    return intent_result


def plan_single_response(state: dict, aggregated_text: str) -> dict:
    """
    NEW FUNCTION: Plan exactly 1 OutboxItem and persist to DB
    
    Arquitetura mínima: TurnController → Planner → Delivery
    - Gera exatamente 1 resposta (coalesça qualquer multiplicidade)
    - Persiste no DB via outbox_store (fonte de verdade durável)
    - Mantém snapshot em memória para compatibilidade
    
    Args:
        state: Conversation state with turn_id, phone_number
        aggregated_text: User message aggregated by TurnController
        
    Returns:
        dict: Updated state with outbox + persisted response
    """
    
    # Extract required data for turn-based processing
    turn_id = state.get("turn_id")
    phone_number = state.get("phone_number", "unknown")  
    conversation_id = state.get("conversation_id", f"conv_{phone_number}")
    
    if not turn_id:
        logger.error(f"PLANNER|missing_turn_id|phone={phone_number[-4:]}")
        turn_id = f"emergency_{int(time.time())}"
        state["turn_id"] = turn_id
    
    logger.info(
        f"PLANNER|planning_single_response|phone={phone_number[-4:]}|"
        f"turn={turn_id}|text_len={len(aggregated_text)}"
    )
    
    # Clear any existing outbox for this turn (1 resposta por turno)
    ensure_outbox(state)
    state[OUTBOX_KEY].clear()
    
    # Update state with aggregated user message
    state["last_user_message"] = aggregated_text
    
    # Generate response using existing planner logic
    rd = state.get("routing_decision")
    mode = routing_mode_from_decision(normalize_rd_obj(rd)) if rd else "template"
    
    try:
        # Use existing planning functions but ensure single response
        if mode == "template":
            state = _plan_template(state, fallback_level=None)
        elif mode == "llm_rag":
            state = _plan_llm_rag(state)
        elif mode == "handoff":
            state = _plan_handoff(state)
        elif mode == "fallback_l1":
            state = _plan_template(state, fallback_level=1)
        else:  # fallback_l2
            state = _plan_template(state, fallback_level=2)
        
        # Ensure exactly 1 item in outbox
        outbox_items = state.get(OUTBOX_KEY, [])
        if len(outbox_items) == 0:
            logger.warning(f"PLANNER|empty_outbox|generating_fallback|turn={turn_id}")
            # Add emergency fallback
            fallback_item = OutboxItem(
                text="Olá! Como posso ajudar?",
                channel="whatsapp", 
                meta={"source": "emergency_fallback"}
            )
            outbox_items = [fallback_item]
            state[OUTBOX_KEY] = [fallback_item.to_dict()]
        elif len(outbox_items) > 1:
            logger.info(f"PLANNER|coalescing_multiple|count={len(outbox_items)}|turn={turn_id}")
            # Coalesce multiple items into single response
            texts = []
            for item in outbox_items:
                if isinstance(item, dict):
                    texts.append(item.get("text", ""))
                else:
                    texts.append(str(item))
            
            coalesced_text = "\n\n".join(filter(None, texts))
            coalesced_item = OutboxItem(
                text=coalesced_text,
                channel="whatsapp",
                meta={"source": "planner_coalesced", "original_count": len(outbox_items)}
            )
            outbox_items = [coalesced_item]
            state[OUTBOX_KEY] = [coalesced_item.to_dict()]
        
        # Process the single OutboxItem
        single_item = outbox_items[0]
        if isinstance(single_item, dict):
            # Convert dict back to OutboxItem for processing
            outbox_item = OutboxItem(
                text=single_item.get("text", ""),
                channel=single_item.get("channel", "whatsapp"),
                meta=single_item.get("meta", {}),
                idempotency_key=single_item.get("idempotency_key")
            )
        else:
            outbox_item = single_item
        
        # Ensure idempotency key
        ensure_idempotency_key(outbox_item, phone_number, turn_id)
        
        # Update state with processed item
        state[OUTBOX_KEY] = [outbox_item.to_dict()]
        
        # **ESSENCIAL**: Persistir no DB (fonte de verdade durável)
        db_connection = state.get("db")
        if db_connection:
            success = persist_outbox(
                db=db_connection,
                conversation_id=conversation_id,
                turn_id=turn_id,
                items=[outbox_item.to_dict()]
            )
            
            if success:
                logger.info(
                    f"PLANNER|persisted_to_db|turn={turn_id}|"
                    f"idem={outbox_item.idempotency_key}|text_len={len(outbox_item.text)}"
                )
            else:
                logger.error(f"PLANNER|persist_failed|turn={turn_id}")
        else:
            logger.warning(f"PLANNER|no_db_connection|turn={turn_id}|persistence_skipped")
        
        # Create snapshot for memory-based delivery (compatibilidade)
        state["_planner_snapshot_outbox"] = list(state[OUTBOX_KEY])
        
        return state
        
    except Exception as e:
        logger.error(f"PLANNER|planning_failed|turn={turn_id}|error={e}")
        
        # Emergency fallback with idempotency  
        fallback_item = OutboxItem(
            text="Desculpe, houve um erro interno. Como posso ajudar?",
            channel="whatsapp",
            meta={"source": "emergency_error_fallback", "error": str(e)}
        )
        ensure_idempotency_key(fallback_item, phone_number, turn_id)
        
        state[OUTBOX_KEY] = [fallback_item.to_dict()]
        state["_planner_snapshot_outbox"] = list(state[OUTBOX_KEY])
        
        # Try to persist emergency fallback too
        db_connection = state.get("db")
        if db_connection:
            persist_outbox(
                db=db_connection,
                conversation_id=conversation_id, 
                turn_id=turn_id,
                items=[fallback_item.to_dict()]
            )
        
        return state


def response_planner_node(state: dict) -> dict:
    """
    ResponsePlanner Node - Action façade que enfileira MessageEnvelope
    
    Responsibilities:
    - Read routing_decision from SmartRouter
    - Convert to internal mode (template/llm_rag/handoff/fallback)
    - Enqueue MessageEnvelope in state[OUTBOX_KEY] 
    - NO IO operations (defer to Delivery)
    """
    
    # Ensure outbox exists and add structured telemetry
    ensure_outbox(state)
    
    # Structured logging - OUTBOX_TRACE planner phase
    from ..observability.structured_logging import log_outbox_trace
    log_outbox_trace("planner", state)
    
    outbox_before = len(state[OUTBOX_KEY])
    logger.info(f"planner_outbox_count_before: {outbox_before}")
    
    rd = state.get("routing_decision")
    mode = routing_mode_from_decision(normalize_rd_obj(rd)) if rd else "fallback_l2"
    
    try:
        if mode == "template":
            state = _plan_template(state, fallback_level=None)
        elif mode == "llm_rag":
            state = _plan_llm_rag(state)
        elif mode == "handoff":
            state = _plan_handoff(state)
        elif mode == "fallback_l1":
            state = _plan_template(state, fallback_level=1)
        else:  # fallback_l2
            state = _plan_template(state, fallback_level=2)
        
        # Post-planning structured telemetry
        outbox_after = len(state[OUTBOX_KEY])
        log_outbox_trace("planner", state)  # Second trace for after-planning state
        logger.info(f"planner_outbox_count_after: {outbox_after}")
        
        if outbox_after > 0:
            first_item = state[OUTBOX_KEY][0]
            logger.info(f"planner_first_item_type: {type(first_item).__name__}")
            if isinstance(first_item, dict):
                logger.info(f"planner_first_item_keys: {list(first_item.keys())}")
                
        # Validate no template placeholders remain
        for i, msg in enumerate(state[OUTBOX_KEY]):
            text = msg.get("text", "") if isinstance(msg, dict) else str(msg)
            if "{{" in text and "}}" in text:
                logger.warning(f"planner_template_placeholder_detected: message {i} contains {{...}}")
    
        # PERSISTENT OUTBOX: Save messages to Redis (atomic handoff to Delivery)
        _persist_outbox_redis(state)
        
        return state
        
    except Exception as e:
        logger.error(f"ResponsePlanner node failed: {e}", exc_info=True)
        # Emergency fallback
        envelope = MessageEnvelope(
            text="Desculpe, houve um erro interno. Como posso ajudar?",
            channel="whatsapp",
            meta={
                "mode": "emergency_fallback", 
                "error": str(e),
                "instance": state.get("instance", "") if isinstance(state, dict) else ""
            }
        )
        state[OUTBOX_KEY].append(envelope.to_dict())
        
        outbox_after = len(state[OUTBOX_KEY])
        logger.info(f"planner_outbox_count_after: {outbox_after} (emergency)")
        
        # PERSISTENT OUTBOX: Save emergency messages to Redis (atomic handoff to Delivery)
        _persist_outbox_redis(state)
        
        return state


def _plan_template(state: dict, fallback_level: int | None):
    """Generate template-based response and enqueue"""
    
    # Determine template name based on stage + intent
    stage = state.get("current_stage", "greeting")
    
    if fallback_level == 1:
        template_name = f"kumon:fallback:level1:general"
    elif fallback_level == 2:
        template_name = f"kumon:fallback:level2:basic"
    else:
        # Use existing template_mappings logic
        planner = response_planner
        template_key = (stage.lower(), "general")
        template_name = planner.template_mappings.get(template_key, f"kumon:{stage}:response:general")
    
    # Render template
    text = render_template(template_name, state)
    
    # Create OutboxItem and enqueue using unified format
    item = OutboxItem(
        text=text,
        channel=resolve_channel(state),
        meta={
            "template_id": template_name, 
            "fallback_level": fallback_level, 
            "mode": "template",
            "source": "response_planner",
            "instance": state.get("instance", "kumon_assistant")  # Use valid default
        }
    )
    
    # Use unified enqueue function
    enqueue_to_outbox(state, item)
    
    # Create snapshot for bridge protection
    state["_planner_snapshot_outbox"] = list(state.get(OUTBOX_KEY, []))
    
    return state


def _plan_llm_rag(state: dict):
    """Generate LLM+RAG response and enqueue"""
    
    # Use existing ResponsePlanner LLM logic as fallback
    try:
        # Simplified LLM call - reuse existing infrastructure
        user_message = state.get("last_user_message", "")
        llm_service = ProductionLLMService()
        
        # Build context (reuse existing method)
        variables = template_variable_resolver.get_template_variables(state)
        parent_name = variables.get("parent_name", "")
        
        simple_prompt = f"""
Você é Cecília, recepcionista do Kumon Vila A em Porto Alegre.
Responda de forma profissional e acolhedora.

{f"Nome dos pais: {parent_name}" if parent_name else ""}
Pergunta: {user_message}

Responda brevemente sobre o método Kumon e como podemos ajudar.
"""
        
        import asyncio
        answer = asyncio.run(llm_service.generate_response(simple_prompt))
        
    except Exception as e:
        logger.warning(f"LLM generation failed: {e}")
        answer = "Obrigada pela pergunta! Para melhor esclarecimento, entre em contato: (51) 99692-1999"
    
    # Create OutboxItem and enqueue using unified format
    item = OutboxItem(
        text=answer,
        channel=resolve_channel(state),
        meta={
            "mode": "llm_rag", 
            "llm_used": True,
            "source": "response_planner",
            "instance": state.get("instance", "kumon_assistant")  # Use valid default
        }
    )
    
    # Use unified enqueue function
    enqueue_to_outbox(state, item)
    
    # Create snapshot for bridge protection
    state["_planner_snapshot_outbox"] = list(state.get(OUTBOX_KEY, []))
    
    return state


def _plan_handoff(state: dict):
    """Generate handoff response and enqueue"""
    
    handoff_text = (
        "Para melhor atendimento, nossa equipe especializada "
        "entrará em contato:\n\n"
        "📞 **(51) 99692-1999**\n"
        "🕐 Segunda a Sexta, 8h às 18h"
    )
    
    # Create OutboxItem and enqueue using unified format
    item = OutboxItem(
        text=handoff_text,
        channel=resolve_channel(state),
        meta={
            "mode": "handoff", 
            "escalated": True,
            "source": "response_planner",
            "instance": state.get("instance", "kumon_assistant")  # Use valid default
        }
    )
    
    # Use unified enqueue function
    enqueue_to_outbox(state, item)
    
    # Create snapshot for bridge protection
    state["_planner_snapshot_outbox"] = list(state.get(OUTBOX_KEY, []))
    
    return state

def _persist_outbox_redis(state: dict) -> None:
    """
    Persist outbox messages to Redis for atomic handoff to Delivery
    
    Belt and suspenders: persiste no Redis (fonte da verdade) E mantém
    no state (backup). Resolve o problema crítico de outbox perdido.
    
    Args:
        state: LangGraph state containing outbox messages
    """
    from ..outbox_repo_redis import outbox_push
    
    # Get conversation ID from state
    conversation_id = state.get("session_id") or state.get("conversation_id")
    if not conversation_id:
        logger.warning("REDIS_OUTBOX|no_conversation_id|skipping_persistence")
        return
    
    # Get outbox messages
    outbox_messages = state.get(OUTBOX_KEY, [])
    if not outbox_messages:
        logger.debug(f"REDIS_OUTBOX|no_messages|conv={conversation_id}")
        return
    
    # Normalize messages to dict format
    normalized_messages = []
    for i, message in enumerate(outbox_messages):
        try:
            # Ensure message is dict format
            if hasattr(message, 'to_dict'):
                message_dict = message.to_dict()
            elif isinstance(message, dict):
                message_dict = message.copy()
            else:
                logger.warning(f"REDIS_OUTBOX|invalid_message_type|conv={conversation_id}|idx={i}|type={type(message)}")
                continue
                
            normalized_messages.append(message_dict)
            
        except Exception as e:
            logger.error(f"REDIS_OUTBOX|normalize_error|conv={conversation_id}|idx={i}|error={e}")
            continue
    
    if not normalized_messages:
        logger.warning(f"REDIS_OUTBOX|no_valid_messages|conv={conversation_id}")
        return
    
    # ❶ Persist to Redis (fonte da verdade para handoff)
    persisted_count = outbox_push(conversation_id, normalized_messages)
    
    # �② Update state with normalized messages (backup + compatibility)
    state[OUTBOX_KEY] = normalized_messages
    
    logger.info(
        f"REDIS_OUTBOX|planner_persisted|conv={conversation_id}|"
        f"redis_count={persisted_count}|state_count={len(normalized_messages)}"
    )