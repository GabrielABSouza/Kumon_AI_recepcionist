"""
Workflow Principal da Cecília usando LangGraph

Este módulo define o workflow LangGraph completo que orquestra toda a conversa,
conectando todos os nodes e implementando a lógica de roteamento com circuit breakers.

Segue rigorosamente a documentação do langgraph_orquestration.md
"""

from typing import Optional, Dict, Any
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from ..services.postgres_checkpointer import postgres_checkpointer
from ..services.workflow_state_repository import workflow_state_repository, WorkflowState
from ..core.config import settings
from ..workflows.workflow_orchestrator import workflow_orchestrator, WorkflowDefinition, WorkflowStep, WorkflowPriority
from .state.models import CeciliaState
from .state.managers import StateManager
from .nodes import (
    greeting_node,
    qualification_node,
    information_node,
    scheduling_node,
    validation_node,
    confirmation_node
)
from .nodes.handoff import handoff_node
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
        # Wave 3: Use PostgreSQL checkpointer for persistent state
        self.use_postgres_persistence = getattr(settings, 'USE_POSTGRES_PERSISTENCE', True)
        
        if self.use_postgres_persistence:
            self.checkpointer = postgres_checkpointer
            logger.info("🗄️ Using PostgreSQL checkpointer for persistent state")
        else:
            self.checkpointer = MemorySaver()
            logger.info("⚠️ Using memory checkpointer (non-persistent)")
        
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
        
        # Inicializar o grafo
        workflow = StateGraph(CeciliaState)
        
        # ========== ADICIONAR NODES ==========
        workflow.add_node("greeting", greeting_node)
        workflow.add_node("qualification", qualification_node)
        workflow.add_node("information", information_node)
        workflow.add_node("scheduling", scheduling_node)
        workflow.add_node("confirmation", confirmation_node)
        workflow.add_node("validation", validation_node)
        workflow.add_node("handoff", handoff_node)
        workflow.add_node("emergency_progression", emergency_progression_node)
        
        # ========== DEFINIR PONTO DE ENTRADA ==========
        workflow.set_entry_point("greeting")
        
        # ========== ADICIONAR EDGES CONDICIONAIS COM CIRCUIT BREAKER ==========
        
        # Do greeting
        workflow.add_conditional_edges(
            "greeting",
            route_from_greeting,
            {
                "qualification": "qualification",
                "scheduling": "scheduling",
                "validation": "validation",
                "handoff": "handoff",
                "emergency_progression": "emergency_progression"
            }
        )
        
        # Do qualification
        workflow.add_conditional_edges(
            "qualification",
            route_from_qualification,
            {
                "information": "information",
                "scheduling": "scheduling",
                "validation": "validation",
                "handoff": "handoff",
                "emergency_progression": "emergency_progression"
            }
        )
        
        # Do information gathering
        workflow.add_conditional_edges(
            "information",
            route_from_information,
            {
                "information": "information",  # Loop para mais perguntas
                "scheduling": "scheduling",
                "validation": "validation",
                "handoff": "handoff",
                "emergency_progression": "emergency_progression"
            }
        )
        
        # Do scheduling
        workflow.add_conditional_edges(
            "scheduling",
            route_from_scheduling,
            {
                "scheduling": "scheduling",  # Loop para completar agendamento
                "confirmation": "confirmation",
                "validation": "validation",
                "handoff": "handoff",
                "emergency_progression": "emergency_progression"
            }
        )
        
        # Do validation - pode voltar para qualquer node
        workflow.add_conditional_edges(
            "validation",
            route_from_validation,
            {
                "greeting": "greeting",
                "qualification": "qualification",
                "information": "information", 
                "scheduling": "scheduling",
                "confirmation": "confirmation",
                "handoff": "handoff",
                "retry_validation": "validation",
                "emergency_progression": "emergency_progression"
            }
        )
        
        # Emergency progression - vai direto para onde o circuit breaker decidiu
        workflow.add_conditional_edges(
            "emergency_progression",
            route_from_emergency_progression,
            {
                "information": "information",
                "scheduling": "scheduling", 
                "handoff": "handoff",
                "END": END
            }
        )
        
        # Handoff sempre vai para END
        workflow.add_edge("handoff", END)
        
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
            return await self._process_message_orchestrated(phone_number, user_message, thread_id)
        
        # Option 2: Direct LangGraph execution (legacy)
        else:
            return await self._process_message_internal(phone_number, user_message, thread_id)
    
    async def _process_message_orchestrated(
        self, 
        phone_number: str, 
        user_message: str,
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
            active_session = None
            
            # CORRECT APPROACH: CeciliaWorkflow manages conversation sessions after receiving preprocessed messages
            try:
                from ..services.conversation_memory_service import conversation_memory_service
                
                # Validate that ConversationMemoryService is ready (should be initialized by main.py)
                if not conversation_memory_service._initialized or conversation_memory_service.postgres_pool is None:
                    logger.error(f"🚨 ConversationMemoryService not ready for {phone_number} - startup initialization failed")
                    raise RuntimeError("ConversationMemoryService not properly initialized during startup")
                
                logger.info(f"📞 CeciliaWorkflow managing conversation session for {phone_number}")
                
                # Check for existing active session
                active_session = await conversation_memory_service.get_active_session_by_phone(phone_number)
                
                if active_session:
                    # Load existing conversation session
                    existing_state = self._convert_session_to_workflow_state(active_session)
                    session_id = active_session.session_id
                    logger.info(f"🔄 Loaded existing conversation session: {session_id}")
                else:
                    # Create new conversation session (this is the correct place to do it)
                    logger.info(f"🆕 CeciliaWorkflow creating new conversation session for {phone_number}")
                    session = await conversation_memory_service.create_session(
                        phone_number=phone_number,
                        user_name=None,  # Will be extracted during conversation
                        initial_message=user_message
                    )
                    session_id = session.session_id
                    active_session = session
                    logger.info(f"✅ CeciliaWorkflow created conversation session: {session_id}")
                    
            except Exception as memory_error:
                logger.error(f"🚨 CeciliaWorkflow session management failed for {phone_number}: {memory_error}")
                logger.error(f"Error details: {type(memory_error).__name__}: {str(memory_error)}")
                # Use PostgreSQL fallback if conversation memory fails
                active_session = None
                session_id = None
                logger.warning(f"⚠️ Using PostgreSQL fallback for {phone_number}")
            
            # Fallback to PostgreSQL if Redis not available or disabled
            if not active_session and self.use_postgres_persistence:
                existing_state = await self.state_repository.get_workflow_state(thread_id)
                
                # If no existing state, create initial state
                if not existing_state:
                    initial_state = WorkflowState(
                        phone_number=phone_number,
                        thread_id=thread_id,
                        current_stage="greeting",
                        state_data={"phone_number": phone_number},
                        conversation_history=[],
                        user_profile={}
                    )
                    
                    state_id = await self.state_repository.create_workflow_state(initial_state)
                    logger.debug(f"Created initial workflow state: {state_id}")
            
            # Preparar input para o workflow - CeciliaState completo otimizado
            input_data = StateManager.create_initial_state(phone_number, user_message)
            
            # Se existe estado anterior, incluir na entrada
            if existing_state:
                input_data.update({
                    "current_stage": existing_state.current_stage,
                    "current_step": existing_state.current_step,
                    "previous_state": existing_state.state_data,
                    "conversation_history": existing_state.conversation_history,
                    "user_profile": existing_state.user_profile
                })
            
            # Executar workflow
            result = await self.app.ainvoke(input_data, config=config)
            
            # PHASE 3: Use DeliveryService for atomic message delivery and state updates
            # Extract data for delivery
            planned_response = result.get("planned_response") or result.get("last_bot_response")
            routing_decision = result.get("routing_decision", {})
            current_stage = result.get("current_stage", "greeting")
            current_step = result.get("current_step")
            
            # Default response if none planned
            if not planned_response:
                planned_response = "Desculpe, houve um problema. Como posso ajudá-lo?"
            
            # PHASE 3: Use DeliveryService for atomic delivery and state updates
            from ..core.services.delivery_service import delivery_service
            
            # Deliver message and update state atomically
            delivery_result = await delivery_service.deliver_response(
                state=result,  # Pass the workflow result state
                phone_number=phone_number,
                planned_response=planned_response,
                routing_decision=routing_decision
            )
            
            # Extract updated state and delivery results
            if delivery_result["success"]:
                # Message was delivered successfully and state was updated
                updated_result_state = delivery_result["updated_state"]
                current_stage = updated_result_state.get("current_stage", current_stage)
                current_step = updated_result_state.get("current_step", current_step)
                response = planned_response
                
                logger.info(f"✅ DeliveryService succeeded for {phone_number}: {delivery_result['delivery_id']}")
            else:
                # Delivery failed - use fallback response and do not update stage
                response = "Olá! Sou Cecília do Kumon Vila A! 😊 Houve um problema técnico, mas estou aqui para ajudar. Como posso auxiliá-lo hoje?"
                # Keep original stage/step from workflow result (no progression)
                logger.warning(f"⚠️ DeliveryService failed for {phone_number}: {delivery_result.get('error')}")
            
            # Wave 3: Fallback persistence to PostgreSQL (if DeliveryService didn't handle it)
            processing_time = (time.time() - start_time) * 1000
            
            # Only do fallback persistence if DeliveryService failed or Redis unavailable
            if not delivery_result["success"] and self.use_postgres_persistence and not active_session:
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
                    
            elif delivery_result["success"]:
                logger.info(f"✅ DeliveryService handled persistence - no fallback needed")
                
            # Update Redis session if active (independent of DeliveryService)
            if active_session and session_id:
                try:
                    # Add user message to session
                    await conversation_memory_service.add_message_to_session(
                        session_id=session_id,
                        content=user_message,
                        is_from_user=True
                    )
                    
                    # Add assistant response to session
                    await conversation_memory_service.add_message_to_session(
                        session_id=session_id,
                        content=response,
                        is_from_user=False
                    )
                    
                    # Update session state - map workflow stages to conversation stages
                    stage_mapping = {
                        "greeting": "greeting",
                        "qualification": "qualification", 
                        "information_gathering": "information_gathering",
                        "scheduling": "scheduling",
                        "confirmation": "confirmation",
                        "follow_up": "follow_up"
                    }
                    
                    step_mapping = {
                        "welcome": "welcome",
                        "parent_name_collection": "parent_name_collection",
                        "initial_response": "initial_response",
                        "child_name_collection": "child_name_collection",
                        "child_age_collection": "child_age_collection",
                        "program_interest_detection": "program_interest_detection"
                    }
                    
                    # Update session with current workflow state (use DeliveryService updated state if available)
                    final_stage = current_stage
                    final_step = current_step
                    
                    active_session.current_stage = stage_mapping.get(final_stage, final_stage)
                    active_session.current_step = step_mapping.get(final_step, final_step) if final_step else "welcome"
                    active_session.last_activity = datetime.now()
                    
                    await conversation_memory_service.update_session(active_session)
                    logger.info(f"✅ Updated Redis session {session_id}: stage={final_stage}, step={final_step}")
                    
                except Exception as redis_update_error:
                    logger.error(f"🚨 Failed to update Redis session {session_id}: {redis_update_error}")
            
            return {
                "response": response,
                "stage": current_stage,
                "step": current_step,
                "thread_id": thread_id,
                "processing_time_ms": processing_time,
                "persistence_enabled": self.use_postgres_persistence,
                "coordination_method": "direct_langgraph",
                "redis_session_id": session_id,
                "redis_enabled": active_session is not None,
                "delivery_service": {
                    "delivery_id": delivery_result.get("delivery_id"),
                    "delivery_success": delivery_result["success"],
                    "delivery_time_ms": delivery_result.get("delivery_time_ms"),
                    "stage_updated": delivery_result.get("stage_updated", False),
                    "message_sent": delivery_result.get("message_sent", False)
                },
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
                "redis_enabled": active_session is not None if 'active_session' in locals() else False
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
    
    def _convert_session_to_workflow_state(self, active_session) -> Dict[str, Any]:
        """
        Convert ConversationMemoryService session to workflow state
        
        Args:
            active_session: Session object from conversation_memory_service
            
        Returns:
            Dict compatible with WorkflowState
        """
        try:
            # Map conversation session to workflow state format
            workflow_state = {
                "current_stage": active_session.current_stage or "greeting",
                "current_step": active_session.current_step or "welcome",
                "state_data": {
                    "phone_number": active_session.phone_number,
                    "session_id": active_session.session_id,
                    "user_profile": {
                        "phone_number": active_session.phone_number,
                        "user_name": getattr(active_session, 'user_name', None),
                        "created_at": active_session.created_at.isoformat() if hasattr(active_session, 'created_at') else None
                    }
                },
                "conversation_history": [],
                "user_profile": {
                    "phone_number": active_session.phone_number,
                    "user_name": getattr(active_session, 'user_name', None)
                },
                "last_activity": active_session.last_activity.isoformat() if hasattr(active_session, 'last_activity') else None
            }
            
            logger.debug(f"Converted session {active_session.session_id} to workflow state")
            return workflow_state
            
        except Exception as e:
            logger.error(f"Failed to convert session to workflow state: {e}")
            # Return minimal state as fallback
            return {
                "current_stage": "greeting",
                "current_step": "welcome",
                "state_data": {"phone_number": getattr(active_session, 'phone_number', 'unknown')},
                "conversation_history": [],
                "user_profile": {}
            }


# handoff_node agora está em nodes/handoff.py


# Instância global do workflow
cecilia_workflow = CeciliaWorkflow()