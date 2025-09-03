from typing import Dict, Any, Optional, Union
import time
import logging
from dataclasses import asdict
from ...prompts.manager import prompt_manager
from ...prompts.template_variables import template_variable_resolver
from ...core.service_factory import get_langchain_rag_service
from ...services.production_llm_service import ProductionLLMService
from ..state.models import CeciliaState
from ...workflows.contracts import RoutingDecision, MessageEnvelope
from .smart_router_adapter import CoreRoutingDecision, routing_mode_from_decision, normalize_rd_obj

logger = logging.getLogger(__name__)

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
            # Emergency fallback
            state["planned_response"] = self._get_emergency_response()
            state["response_metadata"] = {
                "strategy": "emergency_fallback",
                "error": str(e),
                "generation_time_ms": round((time.time() - start_time) * 1000, 2)
            }
    
    async def _generate_template(self, state: CeciliaState, decision: Union[RoutingDecision, CoreRoutingDecision]) -> str:
        """Gera resposta usando PromptManager (templates)"""
        # Determine template name based on stage + intent
        stage = state.get("current_stage", "unknown")
        
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


def response_planner_node(state: dict) -> dict:
    """
    ResponsePlanner Node - Action façade que enfileira MessageEnvelope
    
    Responsibilities:
    - Read routing_decision from SmartRouter
    - Convert to internal mode (template/llm_rag/handoff/fallback)
    - Enqueue MessageEnvelope in state["outbox"] 
    - NO IO operations (defer to Delivery)
    """
    
    rd = state.get("routing_decision")
    mode = routing_mode_from_decision(normalize_rd_obj(rd)) if rd else "fallback_l2"
    
    state.setdefault("outbox", [])
    
    if mode == "template":
        return _plan_template(state, fallback_level=None)
    elif mode == "llm_rag":
        return _plan_llm_rag(state)
    elif mode == "handoff":
        return _plan_handoff(state)
    elif mode == "fallback_l1":
        return _plan_template(state, fallback_level=1)
    else:  # fallback_l2
        return _plan_template(state, fallback_level=2)


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
    
    # Create MessageEnvelope and enqueue
    env = MessageEnvelope(
        text=text,
        channel=resolve_channel(state),
        meta={"template_id": template_name, "fallback_level": fallback_level, "mode": "template"}
    )
    
    state["outbox"].append(asdict(env))
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
    
    # Create MessageEnvelope and enqueue
    env = MessageEnvelope(
        text=answer,
        channel=resolve_channel(state),
        meta={"mode": "llm_rag", "llm_used": True}
    )
    
    state["outbox"].append(asdict(env))
    return state


def _plan_handoff(state: dict):
    """Generate handoff response and enqueue"""
    
    handoff_text = (
        "Para melhor atendimento, nossa equipe especializada "
        "entrará em contato:\n\n"
        "📞 **(51) 99692-1999**\n"
        "🕐 Segunda a Sexta, 8h às 18h"
    )
    
    # Create MessageEnvelope and enqueue
    env = MessageEnvelope(
        text=handoff_text,
        channel=resolve_channel(state),
        meta={"mode": "handoff", "escalated": True}
    )
    
    state["outbox"].append(asdict(env))
    return state
