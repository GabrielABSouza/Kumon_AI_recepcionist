"""
Workflow Principal da Cecília usando LangGraph

Este módulo define o workflow LangGraph completo que orquestra toda a conversa,
conectando todos os nodes e implementando a lógica de roteamento com circuit breakers.

Segue rigorosamente a documentação do langgraph_orquestration.md
"""

from typing import Optional, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass, field
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from ..services.postgres_checkpointer import postgres_checkpointer
from ..services.workflow_state_repository import workflow_state_repository, WorkflowState
from ..core.config import settings
from ..workflows.workflow_orchestrator import workflow_orchestrator, WorkflowDefinition, WorkflowStep, WorkflowPriority
from .state.models import CeciliaState, create_initial_cecilia_state, ConversationStage
from .state.managers import StateManager
from .nodes import (
    greeting_node,
    qualification_node,
    information_node,
    scheduling_node,
    validation_node,
    confirmation_node
)
from .shadow_integration import with_shadow_v2
from .nodes.handoff import handoff_node
from .nodes.emergency_progression import emergency_progression_node
from .edges.routing import (
    route_from_greeting,
    route_from_qualification,
    route_from_information,
    route_from_scheduling,
    route_from_validation,
    route_from_confirmation,
    route_from_emergency_progression
)
from .nodes.emergency_progression import emergency_progression_node
import logging

logger = logging.getLogger(__name__)


@dataclass
class DeliveryCtx:
    """Type-safe delivery context"""
    instance: Optional[str] = None


@dataclass
class ChannelCtx:
    """Type-safe channel context"""
    name: Optional[str] = None
    instance: Optional[str] = None


@dataclass
class EnvelopeCtx:
    """Type-safe envelope context"""
    meta: Dict[str, Any] = field(default_factory=dict)


def _normalize_state_shapes(state: Dict[str, Any]) -> None:
    """
    Normalize state shapes to ensure objects are proper types, not strings.
    
    This prevents 'str' object does not support item assignment errors
    by ensuring channel, delivery, and envelope are always objects.
    
    Args:
        state: State dictionary to normalize
    """
    # Normalize channel
    channel = state.get("channel")
    if isinstance(channel, str):
        state["channel"] = ChannelCtx(name=channel)
    elif channel is None:
        state["channel"] = ChannelCtx()
    elif not isinstance(channel, (dict, ChannelCtx)):
        state["channel"] = ChannelCtx()
    
    # Normalize delivery
    delivery = state.get("delivery")
    if isinstance(delivery, str):
        state["delivery"] = DeliveryCtx(instance=None)
    elif delivery is None:
        state["delivery"] = DeliveryCtx()
    elif not isinstance(delivery, (dict, DeliveryCtx)):
        state["delivery"] = DeliveryCtx()
    
    # Normalize envelope
    envelope = state.get("envelope")
    if envelope is None or isinstance(envelope, str):
        state["envelope"] = EnvelopeCtx()
    elif not hasattr(envelope, "meta") or not isinstance(getattr(envelope, "meta", None), dict):
        # If it's a dict without proper meta, preserve existing but ensure meta exists
        if isinstance(envelope, dict):
            meta = envelope.get("meta", {})
            if not isinstance(meta, dict):
                meta = {}
            state["envelope"] = EnvelopeCtx(meta=meta)
        else:
            state["envelope"] = EnvelopeCtx()


class CeciliaWorkflow:
    """
    Workflow principal da Cecília usando LangGraph
    
    Implementa a arquitetura completa de conversação com:
    - Circuit breakers para evitar loops
    - Progressive fallback system
    - Recovery mechanisms
    - Routing inteligente baseado em contexto
    """
    
    def __init__(self):
        """Inicializa o workflow com PostgreSQL persistence e orchestrator integration"""
        # TEMPORARY: Disable PostgreSQL checkpointing until workflow_checkpoints table is created
        # TODO: Re-enable after creating workflow_checkpoints table in Railway
        self.use_postgres_persistence = False  # Temporarily disabled
        
        self.checkpointer = MemorySaver()
        logger.info("⚠️ Using memory checkpointer (PostgreSQL checkpointing disabled temporarily)")
        
        self.workflow = self._create_workflow()
        self.app = self.workflow.compile(checkpointer=self.checkpointer)
        self.state_repository = workflow_state_repository
        
        # Integration with WorkflowOrchestrator
        self.orchestrator = workflow_orchestrator
        self._register_langgraph_workflows()
        
        logger.info("CeciliaWorkflow initialized successfully with orchestrator integration")
    
    def _create_workflow(self) -> StateGraph:
        """
        Cria o workflow LangGraph seguindo a documentação
        
        Returns:
            StateGraph: Workflow configurado e pronto para uso
        """
        logger.info("Creating Cecilia workflow graph...")
        
        # Check if V2 architecture should be used
        from .feature_flags import get_feature_flags
        ff = get_feature_flags()
        
        # Use V2 if explicitly enabled OR shadow mode is active
        use_v2 = ff.is_enabled("WORKFLOW_V2_ENABLED") or ff.is_enabled("ROUTER_V2_SHADOW")
        
        if use_v2:
            logger.info("🚀 V2 Architecture Enabled: Using workflow_migration.py")
            from .workflow_migration import create_migrated_workflow
            return create_migrated_workflow()
        
        logger.info("📍 V1 Architecture: Using legacy workflow.py")
        
        # Inicializar o grafo
        workflow = StateGraph(CeciliaState)
        
        # ========== ADICIONAR NODES COM SHADOW TRAFFIC ==========
        # Apply shadow traffic middleware to business nodes
        workflow.add_node("greeting", with_shadow_v2("greeting")(greeting_node))
        workflow.add_node("qualification", with_shadow_v2("qualification")(qualification_node))
        workflow.add_node("information", with_shadow_v2("information")(information_node))
        workflow.add_node("scheduling", with_shadow_v2("scheduling")(scheduling_node))
        workflow.add_node("confirmation", confirmation_node)  # No V2 implementation yet
        workflow.add_node("validation", validation_node)     # No V2 implementation yet
        workflow.add_node("handoff", handoff_node)
        workflow.add_node("emergency_progression", emergency_progression_node)
        
        # DELIVERY node: ONLY consumes routing_decision and intent_result from state
        def delivery_node(state: CeciliaState) -> CeciliaState:
            import asyncio
            from .state.utils import normalize_state_enums
            from .services.delivery_service import delivery_service

            phone_number = state.get("phone_number", "unknown")
            last_node = state.get("last_node", "unknown")
            logger.info(f"📦 DELIVERY node: starting for {phone_number[-4:]} from {last_node}")

            # Prevent reentrancy
            if state.get("delivery_executed"):
                logger.info("🔁 DELIVERY node: already executed, skipping")
                return state

            # Ensure consistent enum types
            try:
                normalize_state_enums(state)
            except Exception:
                pass

            # Create local loop for async calls
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # IMPORTANT: Use routing_decision already set by previous nodes/edges
            # DO NOT call smart_router_adapter here - that violates separation of concerns
            routing_decision = state.get("routing_decision", {})
            if not routing_decision:
                logger.warning("🚨 No routing_decision found in state - using fallback")
                routing_decision = {
                    "target_node": "fallback",
                    "threshold_action": "fallback_level2",
                    "confidence": 0.3,
                    "reasoning": "No routing_decision in state",
                    "rule_applied": "emergency_fallback"
                }

            # Get already planned response from state
            intent_result = state.get("intent_result", {})
            if not intent_result:
                logger.warning("🚨 No intent_result found in state - creating minimal fallback")
                intent_result = {
                    "response": "Obrigada pelo seu contato! Nossa equipe retornará em breve.",
                    "delivery_payload": {
                        "channel": "whatsapp",
                        "content": {"text": "Obrigada pelo seu contato! Nossa equipe retornará em breve."}
                    }
                }

            # DELIVERY: Just consume what's already in state
            
            delivery_result = loop.run_until_complete(
                delivery_service.deliver_response(
                    state=state,
                    phone_number=phone_number,
                    intent_result=intent_result,
                    routing_decision=routing_decision,
                )
            )

            # Persist minimal result into state to avoid post-invoke sending
            state["delivery_service_result"] = delivery_result
            state["delivery_executed"] = True
            logger.info("✅ DELIVERY node: delivery executed")

            # Merge updated state if available
            try:
                # Use getattr for DeliveryResult dataclass, .get() for dict
                if hasattr(delivery_result, "updated_state"):
                    updated = getattr(delivery_result, "updated_state", None)
                elif isinstance(delivery_result, dict):
                    updated = delivery_result.get("updated_state")
                else:
                    updated = None
                    
                if isinstance(updated, dict):
                    state.update({
                        "current_stage": updated.get("current_stage", state.get("current_stage")),
                        "current_step": updated.get("current_step", state.get("current_step")),
                        "last_delivery": updated.get("last_delivery", state.get("last_delivery"))
                    })
            except Exception:
                pass

            return state

        workflow.add_node("DELIVERY", delivery_node)
        
        # ========== V2 ARCHITECTURE: UNIVERSAL EDGE ROUTER ==========
        from .edges.routing import universal_edge_router
        
        # Add Universal Edge Router node  
        workflow.add_node("UNIVERSAL_EDGE_ROUTER", lambda state: state)
        
        # ========== V2 ENTRY POINT: Direct to Universal Edge Router ==========
        workflow.set_entry_point("UNIVERSAL_EDGE_ROUTER")
        
        # ========== V2 UNIVERSAL EDGE ROUTER ROUTING ==========
        workflow.add_conditional_edges(
            "UNIVERSAL_EDGE_ROUTER",
            universal_edge_router,
            {
                "greeting": "greeting",
                "qualification": "qualification", 
                "information": "information",
                "scheduling": "scheduling",
                "validation": "validation",
                "confirmation": "confirmation",
                "handoff": "handoff",
                "DELIVERY": "DELIVERY"  # Direct delivery for V2 flow
            }
        )
        
        # ========== ADICIONAR EDGES CONDICIONAIS COM CIRCUIT BREAKER ==========
        
        # Edges: always route to DELIVERY (dummy edges)
        # Do greeting
        workflow.add_conditional_edges(
            "greeting",
            route_from_greeting,
            {
                "DELIVERY": "DELIVERY"
            }
        )
        
        # Do qualification
        workflow.add_conditional_edges(
            "qualification",
            route_from_qualification,
            {
                "DELIVERY": "DELIVERY"
            }
        )
        
        # Do information gathering
        workflow.add_conditional_edges(
            "information",
            route_from_information,
            {
                "DELIVERY": "DELIVERY"
            }
        )
        
        # Do scheduling
        workflow.add_conditional_edges(
            "scheduling",
            route_from_scheduling,
            {
                "DELIVERY": "DELIVERY"
            }
        )
        
        # Do validation
        workflow.add_conditional_edges(
            "validation",
            route_from_validation,
            {
                "DELIVERY": "DELIVERY"
            }
        )
        
        # Do confirmation
        workflow.add_conditional_edges(
            "confirmation",
            route_from_confirmation,
            {
                "DELIVERY": "DELIVERY"
            }
        )
        
        # Emergency progression
        workflow.add_conditional_edges(
            "emergency_progression", 
            route_from_emergency_progression,
            {
                "DELIVERY": "DELIVERY"
            }
        )
        
        # Handoff sempre vai para END
        workflow.add_edge("handoff", END)
        
        # DELIVERY routes conditionally based on routing decision
        def route_from_delivery(state: CeciliaState) -> str:
            """Route from DELIVERY node based on routing decision and conversation state"""
            from .state.models import ConversationStage, ConversationStep
            
            # **ARQUITETURA MÍNIMA**: Check turn_status first - if delivered, END the turn
            turn_status = state.get("turn_status")
            if turn_status == "delivered":
                logger.info(f"📍 DELIVERY routing to END: turn completed (turn_status={turn_status})")
                return "END"
            elif turn_status in ("already_delivered", "no_content", "send_failed", "exception"):
                logger.info(f"📍 DELIVERY routing to END: turn terminated (turn_status={turn_status})")
                return "END"
            
            # Check if conversation is completed
            current_stage = state.get("current_stage")
            current_step = state.get("current_step")
            
            # If stage is COMPLETED or step is CONVERSATION_ENDED, route to END
            if (current_stage == ConversationStage.COMPLETED or 
                current_step == ConversationStep.CONVERSATION_ENDED or
                (hasattr(current_stage, 'value') and current_stage.value == 'completed') or
                (hasattr(current_step, 'value') and current_step.value == 'conversation_ended')):
                logger.info(f"📍 DELIVERY routing to END: conversation completed (stage={current_stage}, step={current_step})")
                return "END"
            
            # Otherwise, use routing decision
            routing_decision = state.get("delivery_service_result", {}).get("routing_decision", {})
            target_node = routing_decision.get("target_node", "END")
            
            # Completion targets should route to END
            completion_targets = {"completed", "END", "end"}
            if target_node in completion_targets:
                logger.info(f"📍 DELIVERY routing to END: completion target ({target_node})")
                return "END"
            
            # Valid stage nodes that can be reached from DELIVERY
            valid_stage_nodes = {
                "qualification", "information", "scheduling", 
                "validation", "confirmation", "handoff", "emergency_progression"
            }
            
            if target_node in valid_stage_nodes:
                logger.info(f"📍 DELIVERY routing to: {target_node}")
                return target_node
            else:
                logger.info(f"📍 DELIVERY routing to: END (target was {target_node})")
                return "END"

        workflow.add_conditional_edges(
            "DELIVERY",
            route_from_delivery,
            {
                "qualification": "qualification",
                "information": "information", 
                "scheduling": "scheduling",
                "validation": "validation",
                "confirmation": "confirmation",
                "handoff": "handoff",
                "emergency_progression": "emergency_progression",
                "END": END
            }
        )
        
        logger.info("Cecilia workflow created successfully")
        return workflow
    
    def _register_langgraph_workflows(self):
        """Register LangGraph workflows with the orchestrator"""
        
        # Define LangGraph conversation workflow
        conversation_workflow = WorkflowDefinition(
            workflow_id="langgraph_conversation",
            name="LangGraph Conversation Workflow",
            description="Complete conversation workflow using LangGraph with circuit breakers",
            version="1.0.0",
            steps=[
                WorkflowStep(
                    step_id="validate_input",
                    name="Input Validation",
                    description="Validate incoming message and context",
                    handler=self._orchestrator_validate_input,
                    timeout_seconds=10
                ),
                WorkflowStep(
                    step_id="execute_langgraph",
                    name="LangGraph Execution",
                    description="Execute LangGraph workflow with state management",
                    handler=self._orchestrator_execute_langgraph,
                    dependencies=["validate_input"],
                    timeout_seconds=120
                ),
                WorkflowStep(
                    step_id="post_process",
                    name="Post Processing",
                    description="Post-process results and update metrics",
                    handler=self._orchestrator_post_process,
                    dependencies=["execute_langgraph"],
                    timeout_seconds=30
                )
            ],
            priority=WorkflowPriority.HIGH,
            timeout_seconds=180
        )
        
        # Register with orchestrator
        self.orchestrator.register_workflow(conversation_workflow)
        logger.info("🔗 Registered LangGraph workflow with orchestrator")
    
    # ========== ORCHESTRATOR INTEGRATION HANDLERS ==========
    
    async def _orchestrator_validate_input(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrator handler: Validate input for LangGraph execution"""
        try:
            phone_number = context.get("phone_number")
            user_message = context.get("user_message")
            
            if not phone_number or not user_message:
                raise ValueError("Missing required fields: phone_number or user_message")
            
            # Basic validation
            if len(user_message.strip()) == 0:
                raise ValueError("Empty user message")
            
            if len(phone_number) < 10:
                raise ValueError("Invalid phone number format")
            
            logger.info(f"✅ Input validation passed for {phone_number}")
            return {
                "validation_passed": True,
                "phone_number": phone_number,
                "user_message": user_message,
                "validated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Input validation failed: {e}")
            return {
                "validation_passed": False,
                "error": str(e),
                "validated_at": datetime.now().isoformat()
            }
    
    async def _orchestrator_execute_langgraph(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrator handler: Execute LangGraph workflow"""
        try:
            phone_number = context["phone_number"]
            user_message = context["user_message"]
            thread_id = context.get("thread_id", f"thread_{phone_number}")
            
            logger.info(f"🚀 Executing LangGraph workflow for {phone_number}")
            
            # Execute the original LangGraph workflow
            result = await self._process_message_internal(phone_number, user_message, thread_id)
            
            return {
                "langgraph_executed": True,
                "result": result,
                "execution_time": result.get("processing_time_ms", 0),
                "success": result.get("success", False)
            }
            
        except Exception as e:
            logger.error(f"❌ LangGraph execution failed: {e}")
            return {
                "langgraph_executed": False,
                "error": str(e),
                "success": False
            }
    
    async def _orchestrator_post_process(self, context: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrator handler: Post-process LangGraph results"""
        try:
            result = context.get("result", {})
            phone_number = context.get("phone_number")
            
            # Update orchestrator metrics
            if hasattr(self.orchestrator, 'track_conversation_metrics'):
                await self.orchestrator.track_conversation_metrics({
                    "phone_number": phone_number,
                    "stage": result.get("stage"),
                    "success": result.get("success"),
                    "processing_time": result.get("processing_time_ms"),
                    "persistence_enabled": result.get("persistence_enabled")
                })
            
            logger.info(f"✅ Post-processing completed for {phone_number}")
            return {
                "post_processing_completed": True,
                "metrics_updated": True,
                "final_result": result
            }
            
        except Exception as e:
            logger.error(f"❌ Post-processing failed: {e}")
            return {
                "post_processing_completed": False,
                "error": str(e)
            }
    
    async def process_message(
        self, 
        phone_number: str, 
        user_message: str,
        instance: Optional[str] = None,
        thread_id: Optional[str] = None,
        use_orchestrator: bool = True
    ) -> Dict[str, Any]:
        """
        Processa uma mensagem através do workflow com persistência
        
        Args:
            phone_number: Número do WhatsApp
            user_message: Mensagem do usuário
            thread_id: ID do thread (opcional)
            use_orchestrator: Use workflow orchestrator coordination
            
        Returns:
            Dict contendo resposta e metadados
        """
        
        # Option 1: Use orchestrator coordination (recommended)
        if use_orchestrator:
            return await self._process_message_orchestrated(phone_number, user_message, instance, thread_id)
        
        # Option 2: Direct LangGraph execution (legacy)
        else:
            return await self._process_message_internal(phone_number, user_message, instance, thread_id)
    
    async def _process_message_orchestrated(
        self, 
        phone_number: str, 
        user_message: str,
        instance: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process message using workflow orchestrator coordination
        """
        try:
            logger.info(f"🎯 Processing message via orchestrator for {phone_number}")
            
            # Execute LangGraph workflow through orchestrator
            execution_id = await self.orchestrator.execute_workflow(
                workflow_id="langgraph_conversation",
                context={
                    "phone_number": phone_number,
                    "user_message": user_message,
                    "thread_id": thread_id or f"thread_{phone_number}"
                },
                priority=WorkflowPriority.HIGH
            )
            
            # Wait for completion and get results
            result = await self._wait_for_orchestrator_completion(execution_id)
            
            if result and result.get("success"):
                final_result = result.get("final_result", {})
                final_result["orchestrator_execution_id"] = execution_id
                final_result["coordination_method"] = "orchestrator"
                return final_result
            else:
                # Fallback to direct execution if orchestrator fails
                logger.warning(f"Orchestrator execution failed, falling back to direct LangGraph")
                return await self._process_message_internal(phone_number, user_message, thread_id)
                
        except Exception as e:
            logger.error(f"Orchestrator processing failed: {e}")
            # Fallback to direct execution
            return await self._process_message_internal(phone_number, user_message, thread_id)
    
    async def _wait_for_orchestrator_completion(self, execution_id: str, timeout_seconds: int = 180) -> Dict[str, Any]:
        """
        Wait for orchestrator workflow completion
        """
        import asyncio
        
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout_seconds:
            status = self.orchestrator.get_workflow_status(execution_id)
            
            if not status:
                await asyncio.sleep(1)
                continue
                
            if status["status"] == "completed":
                # Get final results from orchestrator execution history
                execution_history = self.orchestrator.execution_history
                for execution in execution_history:
                    if execution.execution_id == execution_id:
                        # Extract the actual LangGraph result from post_process step
                        post_process_result = execution.step_results.get("post_process", {})
                        final_result = post_process_result.get("final_result", {})
                        
                        return {
                            "success": True,
                            "final_result": final_result,
                            "execution_time": status.get("total_time", 0),
                            "orchestrator_metadata": {
                                "execution_id": execution_id,
                                "steps_completed": len(execution.completed_steps),
                                "total_steps": len(execution.step_results)
                            }
                        }
                
                # Fallback if execution not found in history
                return {
                    "success": True,
                    "final_result": {},
                    "execution_time": status.get("total_time", 0)
                }
                
            elif status["status"] == "failed":
                return {
                    "success": False,
                    "error": "Orchestrator workflow failed",
                    "orchestrator_status": status
                }
            
            await asyncio.sleep(0.5)
        
        # Timeout
        return {
            "success": False,
            "error": "Orchestrator workflow timeout"
        }
    
    async def _process_message_internal(
        self, 
        phone_number: str, 
        user_message: str,
        instance: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Internal LangGraph message processing (original implementation)
        """
        import time
        
        start_time = time.time()
        logger.info(f"🔄 Direct LangGraph processing for {phone_number}")
        
        if not thread_id:
            thread_id = f"thread_{phone_number}"
        
        config = {"configurable": {"thread_id": thread_id}}
        
        try:
            logger.info(f"Processing message for {phone_number}: {user_message[:50]}...")
            
            # Wave 3: Check for existing state and attempt recovery if needed
            existing_state = None
            session_id = None
            
            # CeciliaState Management - Pure state system without legacy dependencies
            try:
                logger.info(f"📞 CeciliaWorkflow managing CeciliaState for {phone_number}")
                
                # Use optimized CeciliaState system exclusively
                existing_state = None
                session_id = f"conv_{phone_number}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                
                # Try to get existing state from checkpointer (if available)
                try:
                    if hasattr(self, 'checkpointer') and self.checkpointer:
                        # MemorySaver uses different API than PostgreSQL checkpointer
                        if hasattr(self.checkpointer, 'get_state'):
                            existing_state = await self.checkpointer.get_state(phone_number)
                        else:
                            # MemorySaver stores by thread_id, try different approach
                            existing_state = None
                        if existing_state:
                            # Check if state is complete and should create new
                            current_stage = existing_state.get("current_stage")
                            if current_stage == ConversationStage.COMPLETED:
                                logger.info(f"📋 Found completed state, creating new session")
                                existing_state = None
                            else:
                                logger.info(f"🔄 Resuming CeciliaState session for {phone_number}")
                except Exception as e:
                    logger.warning(f"Failed to retrieve existing state: {e}")
                    existing_state = None
                
                # Create new CeciliaState if no existing state found
                if not existing_state:
                    logger.info(f"🆕 Creating new CeciliaState for {phone_number}")
                    valid_instance = instance if instance else "kumon_assistant"
                    existing_state = create_initial_cecilia_state(phone_number, user_message, instance=valid_instance)
                    session_id = existing_state["conversation_id"]
                    
                    # STEP 1: Normalize state shapes to prevent type errors
                    _normalize_state_shapes(existing_state)
                    
                    # STEP 2: Inject instance using type-safe method
                    from .router.instance_resolver import inject_instance_to_state
                    inject_instance_to_state(existing_state, valid_instance)
                    
                    logger.info(f"✅ Created new CeciliaState session: {session_id} with instance: {valid_instance}")
                    
                    # Apply StageResolver to define initial context for V2 architecture
                    from .nodes.stage_resolver import StageResolver
                    existing_state = StageResolver.apply(existing_state)
                    logger.info(f"🎯 StageResolver applied: stage={existing_state['current_stage']}, step={existing_state['current_step']}")
                else:
                    session_id = existing_state["conversation_id"]
                
                # Update last user message in existing state
                existing_state["last_user_message"] = user_message
                existing_state["conversation_metrics"]["message_count"] += 1
                
            except Exception as state_error:
                logger.error(f"🚨 CeciliaState management failed for {phone_number}: {state_error}")
                logger.error(f"Error details: {type(state_error).__name__}: {str(state_error)}")
                # Create minimal fallback state
                valid_instance = instance if instance else "kumon_assistant"
                existing_state = create_initial_cecilia_state(phone_number, user_message, instance=valid_instance)
                session_id = existing_state["conversation_id"]
                
                # STEP 1: Normalize state shapes to prevent type errors
                _normalize_state_shapes(existing_state)
                
                # STEP 2: Inject instance using type-safe method
                from .router.instance_resolver import inject_instance_to_state
                inject_instance_to_state(existing_state, valid_instance)
                
                # Apply StageResolver to fallback state too
                from .nodes.stage_resolver import StageResolver
                existing_state = StageResolver.apply(existing_state)
                logger.warning(f"⚠️ Using fallback CeciliaState for {phone_number} with StageResolver applied")
            
            # Use the existing_state directly as CeciliaState input - no conversion needed
            input_data = existing_state
            logger.info(f"🔄 Using CeciliaState: stage={input_data['current_stage']}, step={input_data['current_step']}, conversation_id={input_data['conversation_id']}")
            
            # PHASE 2.1: Execute LangGraph directly - Stage Node → Routing Node (edges) → DeliveryService
            logger.info(f"🚀 Executing LangGraph workflow for {phone_number}")
            
            # Execute LangGraph: Stage Node will collect/validate, Edge will call Routing Node, DeliveryService sends
            try:
                result = await self.app.ainvoke(input_data, config=config)
            except Exception as critical_error:
                logger.error(f"🚨 Critical LangGraph error: {critical_error}")
                # Emergency fallback - generate basic response
                result = input_data.copy()
                # Build a typed CoreRoutingDecision to avoid attribute errors downstream
                from .router.smart_router_adapter import CoreRoutingDecision
                critical_decision = CoreRoutingDecision(
                    target_node="fallback",
                    confidence=0.0,
                    reasoning=f"Critical error: {str(critical_error)}",
                    rule_applied="emergency_fallback",
                    threshold_action="fallback_level1",
                    intent_confidence=0.0,
                    pattern_confidence=0.0,
                )
                # Keep a dict snapshot for telemetry if needed
                result["routing_decision"] = {
                    "target_node": critical_decision.target_node,
                    "threshold_action": critical_decision.threshold_action,
                    "confidence": critical_decision.confidence,
                    "reasoning": critical_decision.reasoning,
                    "rule_applied": critical_decision.rule_applied,
                    "bypass_reason": "critical_error",
                    "error": str(critical_error)
                }

                # Generate emergency fallback response using a typed decision
                from .router.response_planner import response_planner
                await response_planner.plan_and_generate(result, critical_decision)
            
            # DELIVERY is now executed inside the DELIVERY node.
            # If DELIVERY already executed, return early without re-sending.
            if result.get("delivery_service_result"):
                delivery_result = result["delivery_service_result"]
                logger.info("🚚 Delivery executed in DELIVERY node; skipping post-invoke delivery")
                response = result.get("intent_result", {}).get("response") or ""
                current_stage = result.get("current_stage", "greeting")
                current_step = result.get("current_step")
                processing_time = (time.time() - start_time) * 1000
                return {
                    "success": getattr(delivery_result, "success", True) if hasattr(delivery_result, "success") else delivery_result.get("success", True) if isinstance(delivery_result, dict) else True,
                    "delivery_id": getattr(delivery_result, "delivery_id", None) if hasattr(delivery_result, "delivery_id") else delivery_result.get("delivery_id") if isinstance(delivery_result, dict) else None,
                    "final_state": result,
                    "response_sent": response,
                    "processing_time_ms": processing_time
                }

            # If for any reason DELIVERY did not execute, provide a safe fallback response (no send here)
            response = result.get("intent_result", {}).get("response") or "Olá! Obrigada por entrar em contato. Em instantes retorno com mais informações."
            current_stage = result.get("current_stage", "greeting")
            current_step = result.get("current_step")
            processing_time = (time.time() - start_time) * 1000

            # Wave 3: Fallback persistence to PostgreSQL (if DeliveryService didn't handle it)
            
            # Only do fallback persistence if DeliveryService failed or Redis unavailable
            if self.use_postgres_persistence:
                # DeliveryService failed, use PostgreSQL fallback
                conversation_history = existing_state.conversation_history if existing_state else []
                conversation_history.append({
                    "role": "user",
                    "content": user_message,
                    "timestamp": time.time()
                })
                conversation_history.append({
                    "role": "assistant", 
                    "content": response,
                    "timestamp": time.time()
                })
                
                # Keep only last 20 messages to manage size
                if len(conversation_history) > 20:
                    conversation_history = conversation_history[-20:]
                
                # Prepare fallback state updates (no stage progression on delivery failure)
                state_updates = {
                    "current_stage": result.get("current_stage", current_stage),  # Keep original stage
                    "current_step": result.get("current_step", current_step),
                    "state_data": result,
                    "conversation_history": conversation_history,
                    "last_activity": datetime.now(),
                    "delivery_failed": True
                }
                
                # Update PostgreSQL as fallback
                update_success = await self.state_repository.update_workflow_state(
                    thread_id, 
                    state_updates, 
                    processing_time
                )
                
                if not update_success:
                    logger.warning(f"Failed to update workflow state for {thread_id}")
                else:
                    logger.info(f"✅ PostgreSQL fallback persistence for {phone_number}")
                    
            else:
                logger.info(f"ℹ️ Skipping DB persistence or already handled")
                
            # State is already managed by CeciliaState and PostgreSQL checkpointer
            # No need for legacy session management
            
            return {
                "response": response,
                "stage": current_stage,
                "step": current_step,
                "thread_id": thread_id,
                "processing_time_ms": processing_time,
                "persistence_enabled": self.use_postgres_persistence,
                "coordination_method": "direct_langgraph",
                "redis_session_id": session_id,
                "redis_enabled": False,  # Using CeciliaState only
                "delivery_service": result.get("delivery_service_result", {}),
                "success": True
            }
            
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            error_details = {
                "phone_number": phone_number,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "processing_time_ms": processing_time,
                "session_id": session_id if 'session_id' in locals() else None,
                "redis_enabled": False  # Using CeciliaState only
            }
            logger.error(f"🚨 Error processing message: {error_details}")
            
            # Wave 3: Attempt recovery from checkpoint
            recovery_attempted = False
            if self.use_postgres_persistence:
                try:
                    recovery_result = await self.recover_workflow_state(thread_id)
                    if recovery_result and recovery_result.get("success"):
                        recovery_attempted = True
                        logger.info(f"Successfully recovered workflow state for {thread_id}")
                except Exception as recovery_error:
                    logger.error(f"Recovery failed for {thread_id}: {recovery_error}")
            
            # Resposta de fallback
            fallback_response = {
                "response": "Olá! Sou Cecília do Kumon Vila A! 😊 Houve um problema técnico, mas estou aqui para ajudar. Como posso auxiliá-lo hoje?",
                "stage": "greeting",
                "step": "welcome",
                "thread_id": thread_id,
                "processing_time_ms": processing_time,
                "persistence_enabled": self.use_postgres_persistence,
                "recovery_attempted": recovery_attempted,
                "success": False,
                "error": str(e)
            }
            
            return fallback_response
    
    async def recover_workflow_state(self, thread_id: str) -> Dict[str, Any]:
        """
        Attempt to recover workflow state from checkpoint
        
        Args:
            thread_id: Thread ID to recover
            
        Returns:
            Recovery result dict
        """
        try:
            # Implementation placeholder for recovery logic
            logger.info(f"Attempting workflow state recovery for {thread_id}")
            return {"success": False, "reason": "recovery_not_implemented"}
        except Exception as e:
            logger.error(f"Recovery attempt failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_conversation_state(self, thread_id: str) -> Optional[CeciliaState]:
        """
        Recupera estado atual da conversa
        
        Args:
            thread_id: ID do thread
            
        Returns:
            Estado atual ou None se não encontrado
        """
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = await self.app.aget_state(config)
            return state.values if state else None
        except Exception as e:
            logger.error(f"Error getting conversation state for {thread_id}: {str(e)}")
            return None
    
    async def reset_conversation(self, thread_id: str) -> bool:
        """
        Reset conversa (para testes ou reinício)
        
        Args:
            thread_id: ID do thread
            
        Returns:
            True se sucesso, False caso contrário
        """
        try:
            # LangGraph não tem reset direto, mas podemos criar novo thread
            return True
        except Exception as e:
            logger.error(f"Error resetting conversation {thread_id}: {str(e)}")
            return False
    
    # Legacy conversion method removed - using CeciliaState exclusively


# handoff_node agora está em nodes/handoff.py


# Instância global do workflow
# Lazy initialization to avoid circular imports and startup crashes
_cecilia_workflow = None


def get_cecilia_workflow() -> CeciliaWorkflow:
    """
    Get the global Cecilia workflow instance with lazy initialization
    
    Returns:
        CeciliaWorkflow: The global workflow instance
    """
    global _cecilia_workflow
    if _cecilia_workflow is None:
        logger.info("🔄 Initializing Cecilia workflow (lazy loading)")
        _cecilia_workflow = CeciliaWorkflow()
    return _cecilia_workflow


# Legacy compatibility for immediate imports
def get_workflow():
    """Legacy alias for get_cecilia_workflow()"""
    return get_cecilia_workflow()
