from typing import Dict, Any, Optional, Union
import time
import logging
from ...prompts.manager import prompt_manager
from ...prompts.template_variables import template_variable_resolver
from ...core.service_factory import get_langchain_rag_service
from ...services.production_llm_service import ProductionLLMService
from ..state.models import CeciliaState
from ...workflows.contracts import RoutingDecision
from .smart_router_adapter import CoreRoutingDecision

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
    
    async def plan_and_generate(self, state: CeciliaState, decision: Union[RoutingDecision, CoreRoutingDecision]) -> None:
        """
        Planeja e gera resposta baseada na decisão do SmartRouter.
        Popula state["planned_response"] e state["response_metadata"].
        """
        start_time = time.time()
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
        intent = routing_info.get("intent_category")
        
        if not intent:
            # Fallback: derive intent from target_node
            if decision.target_node == "greeting":
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