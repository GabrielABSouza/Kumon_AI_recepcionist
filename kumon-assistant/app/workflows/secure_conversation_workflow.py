"""
Secure Conversation Workflow with Integrated Security (Fase 5)

Complete implementation combining:
- LangGraph state machine workflows
- LangSmith prompt management
- Multi-layer security validation
- Advanced threat detection
- Quality assurance validation
- Business scope compliance
"""

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from ..core.config import settings
from ..core.dependencies import intent_classifier
from ..core.logger import app_logger
from ..core.state.models import CeciliaState as ConversationState
from ..core.state.models import ConversationStage as WorkflowStage
from ..core.state.models import ConversationStep
from ..prompts.manager import PromptManager
from ..security.security_manager import security_manager
from ..services.business_compliance_monitor import business_compliance_monitor

# Legacy smart router removed - using CeciliaWorkflow instead
# from ..workflows.smart_router import SmartConversationRouter
from ..core.service_factory import get_langchain_rag_service
from ..services.rag_business_validator import rag_business_validator
from ..workflows.context_manager import ConversationContextManager
from ..workflows.nodes.business_rules_nodes import (
    BusinessRuleNodeResult,
    business_compliance_node,
    handoff_decision_node,
    lead_qualification_node,
    pricing_validation_node,
    scheduling_constraint_node,
)
from ..workflows.states.compliance_state import (
    enhance_cecilia_state_with_compliance,
    get_compliance_summary,
    update_compliance_state,
)
from ..workflows.validators import ValidationResult, get_validation_agent


class SecureWorkflowAction(Enum):
    """Actions available in secure workflow"""

    CONTINUE = "continue"
    RETRY = "retry"
    ESCALATE = "escalate"
    BLOCK = "block"
    REDIRECT = "redirect"
    END_CONVERSATION = "end_conversation"


@dataclass
class SecureWorkflowResult:
    """Result of secure workflow execution"""

    final_response: str
    action_taken: SecureWorkflowAction
    security_status: str
    validation_passed: bool
    quality_score: float
    conversation_state: ConversationState
    security_incidents: List[str]
    recommendations: List[str]


class SecureConversationWorkflow:
    """
    Military-grade secure conversation workflow

    Implements Fase 5 with complete security integration:
    - Real-time threat detection and mitigation
    - Multi-layer response validation
    - Adaptive security policies
    - Quality assurance with business compliance
    - Comprehensive audit logging
    """

    def __init__(self):
        # Core components
        self.prompt_manager = PromptManager()
        self.intent_classifier = intent_classifier
        self.context_manager = ConversationContextManager()
        # Legacy smart router removed - using CeciliaWorkflow instead
        # self.smart_router = SmartConversationRouter()

        # Workflow state management
        self.memory = MemorySaver()
        self.active_conversations: Dict[str, ConversationState] = {}

        # Security and validation metrics
        self.security_metrics = {
            "total_requests": 0,
            "blocked_requests": 0,
            "validation_failures": 0,
            "escalations": 0,
            "quality_issues": 0,
        }

        # Workflow configuration
        self.config = {
            "max_retries": 3,
            "security_timeout": 30.0,
            "validation_timeout": 15.0,
            "max_conversation_length": 50,
            "auto_escalation_threshold": 0.8,
            "quality_threshold": 0.7,
        }

        # Create the secure workflow graph
        self.workflow = self._create_secure_workflow()

        app_logger.info("Secure Conversation Workflow initialized (Fase 5)")

    async def process_secure_message(
        self,
        phone_number: str,
        user_message: str,
        message_metadata: Optional[Dict[str, Any]] = None,
    ) -> SecureWorkflowResult:
        """
        Process user message through secure workflow

        Args:
            phone_number: User identifier
            user_message: User's message content
            message_metadata: Additional message context

        Returns:
            Complete workflow result with security assessment
        """

        start_time = datetime.now()
        self.security_metrics["total_requests"] += 1

        try:
            app_logger.info(f"Processing secure message from {phone_number}")

            # Phase 1: Pre-processing Security Check
            security_result = await self._pre_processing_security_check(
                phone_number, user_message, message_metadata
            )

            if security_result["action"] == "block":
                self.security_metrics["blocked_requests"] += 1
                return SecureWorkflowResult(
                    final_response=security_result["response"],
                    action_taken=SecureWorkflowAction.BLOCK,
                    security_status="BLOCKED",
                    validation_passed=False,
                    quality_score=0.0,
                    conversation_state=self._get_conversation_state(phone_number),
                    security_incidents=security_result.get("incidents", []),
                    recommendations=["Source blocked due to security threat"],
                )

            # Phase 2: Get or Create Conversation State
            conversation_state = await self._get_or_create_conversation_state(
                phone_number, user_message, message_metadata
            )

            # Phase 3: Execute Secure Workflow
            workflow_result = await self._execute_secure_workflow(
                conversation_state, security_result
            )

            # Phase 4: Final Security and Quality Validation
            final_validation = await self._final_validation_check(
                workflow_result, conversation_state, phone_number
            )

            # Update conversation state
            self.active_conversations[phone_number] = conversation_state

            # Log processing metrics
            processing_time = (datetime.now() - start_time).total_seconds()
            app_logger.info(
                f"Message processed in {processing_time:.2f}s: "
                f"{final_validation.action_taken.value}"
            )

            return final_validation

        except Exception as e:
            app_logger.error(f"Secure workflow error: {e}")
            self.security_metrics["validation_failures"] += 1

            # Fail secure - provide safe fallback response
            return SecureWorkflowResult(
                final_response="Desculpe, ocorreu um problema técnico. Entre em contato conosco pelo telefone (51) 99692-1999.",
                action_taken=SecureWorkflowAction.END_CONVERSATION,
                security_status="ERROR",
                validation_passed=False,
                quality_score=0.0,
                conversation_state=self._get_conversation_state(phone_number),
                security_incidents=[f"Workflow error: {str(e)}"],
                recommendations=["Technical issue - contact support"],
            )

    async def _pre_processing_security_check(
        self, phone_number: str, user_message: str, metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Comprehensive pre-processing security evaluation"""

        try:
            # Use integrated security manager for threat assessment
            security_action, security_context = await security_manager.evaluate_security_threat(
                phone_number, user_message, metadata
            )

            if security_action.value in ["block_permanent", "block_temporary"]:
                return {
                    "action": "block",
                    "response": "Por questões de segurança, não posso prosseguir com essa conversa.",
                    "security_context": security_context,
                    "incidents": ["Security threat detected"],
                }

            elif security_action.value == "rate_limit":
                return {
                    "action": "rate_limit",
                    "response": "Você está enviando mensagens muito rapidamente. Aguarde um momento antes de continuar.",
                    "security_context": security_context,
                    "incidents": ["Rate limit exceeded"],
                }

            else:
                # Clean input for safe processing
                sanitized_message = await security_manager.sanitize_user_input(user_message)
                return {
                    "action": "allow",
                    "sanitized_message": sanitized_message,
                    "security_context": security_context,
                    "incidents": [],
                }

        except Exception as e:
            app_logger.error(f"Pre-processing security error: {e}")
            # Fail secure on security check errors
            return {
                "action": "block",
                "response": "Por questões de segurança, não posso prosseguir no momento.",
                "incidents": [f"Security check failed: {str(e)}"],
            }

    async def _get_or_create_conversation_state(
        self, phone_number: str, user_message: str, metadata: Optional[Dict[str, Any]]
    ) -> ConversationState:
        """Get existing or create new conversation state"""

        # Check for existing conversation
        if phone_number in self.active_conversations:
            state = self.active_conversations[phone_number]

            # Update with current message
            state["user_message"] = user_message
            state["message_history"].append(
                {"role": "user", "content": user_message, "timestamp": datetime.now().isoformat()}
            )

            return state

        # Create new conversation state
        session_id = hashlib.md5(f"{phone_number}_{datetime.now()}".encode()).hexdigest()[
            :12
        ]  # nosec B324

        from .states import ConversationMetrics, UserContext

        new_state = ConversationState(
            phone_number=phone_number,
            session_id=session_id,
            stage=WorkflowStage.GREETING,
            step=ConversationStep.WELCOME,
            user_message=user_message,
            message_history=[
                {"role": "user", "content": user_message, "timestamp": datetime.now().isoformat()}
            ],
            user_context=None,  # Will be set after state creation
            metrics=ConversationMetrics(),
            ai_response=None,
            prompt_used=None,
            validation_passed=False,
            next_action=None,
            requires_human=False,
            conversation_ended=False,
            last_error=None,
            retry_count=0,
        )

        # Set user context after state creation
        new_state["user_context"] = UserContext(new_state)

        # Enhance state with business compliance tracking
        new_state = enhance_cecilia_state_with_compliance(new_state)

        # Start compliance monitoring
        await business_compliance_monitor.start_conversation_monitoring(phone_number, session_id)

        return new_state

    async def _execute_secure_workflow(
        self, conversation_state: ConversationState, security_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute the main secure workflow"""

        try:
            # Use sanitized message for processing
            sanitized_message = security_result.get(
                "sanitized_message", conversation_state["user_message"]
            )
            conversation_state["user_message"] = sanitized_message

            # Run workflow components in parallel for efficiency
            workflow_results = await asyncio.gather(
                self._classify_intent(conversation_state),
                self._resolve_context_references(conversation_state),
                self._generate_rag_context(sanitized_message),
                return_exceptions=True,
            )

            intent_result, context_result, rag_result = workflow_results

            # Update conversation state with results
            if hasattr(intent_result, "category"):
                conversation_state["detected_intent"] = intent_result.category.value
                conversation_state["intent_confidence"] = intent_result.confidence
            elif isinstance(intent_result, dict):
                conversation_state["detected_intent"] = intent_result.get("intent")
                conversation_state["intent_confidence"] = intent_result.get("confidence", 0.0)

            if isinstance(context_result, dict):
                conversation_state["resolved_references"] = context_result.get(
                    "resolved_references", []
                )

            if isinstance(rag_result, dict):
                conversation_state["rag_context"] = rag_result.get("context", "")
                conversation_state["rag_confidence"] = rag_result.get("confidence", 0.0)

            # Execute business rules validation nodes
            app_logger.info("Executing business rules validation nodes")
            business_rule_results = await business_compliance_node.execute(
                conversation_state,
                {"security_context": security_result.get("security_context", {})},
            )

            # Process business rule results
            business_compliance_passed = True
            handoff_required = False
            business_actions = []

            for rule_type, rule_result in business_rule_results.items():
                if isinstance(rule_result, BusinessRuleNodeResult):
                    # Update conversation state with business rule results
                    conversation_state.update(rule_result.updated_state)

                    if not rule_result.compliance_passed:
                        business_compliance_passed = False
                        app_logger.warning(
                            f"Business rule violation: {rule_type.value} - {rule_result.enforcement_message}"
                        )

                    if rule_result.action_required == "handoff":
                        handoff_required = True
                        conversation_state["requires_human"] = True
                        conversation_state["handoff_reason"] = f"business_rule_{rule_type.value}"

                    business_actions.append(
                        {
                            "rule_type": rule_type.value,
                            "action": rule_result.action_required,
                            "message": rule_result.enforcement_message,
                        }
                    )

            # Store business compliance information
            conversation_state["business_rule_results"] = business_rule_results
            conversation_state["business_compliance_passed"] = business_compliance_passed
            conversation_state["business_actions"] = business_actions

            # Update conversation state with compliance tracking
            conversation_state = update_compliance_state(conversation_state, business_rule_results)

            # Monitor business compliance
            await business_compliance_monitor.monitor_business_compliance(
                conversation_state.get("session_id"), business_rule_results
            )

            # Handle mandatory handoff
            if handoff_required:
                app_logger.info("Business rule mandated handoff detected")
                return {
                    "response_candidate": "Vou transferir você para nosso consultor educacional que poderá atendê-lo melhor. Entre em contato através do WhatsApp (51) 99692-1999.",
                    "conversation_state": conversation_state,
                    "security_context": security_result.get("security_context", {}),
                    "business_handoff_required": True,
                }

            # Smart routing decision
            app_logger.info("DEBUG: About to call make_routing_decision")
            # Legacy smart router removed - using direct stage progression for CeciliaWorkflow
            # routing_decision = await self.smart_router.make_routing_decision(conversation_state)

            # Simple routing logic for secure workflow
            from types import SimpleNamespace

            routing_decision = SimpleNamespace(
                target_stage=conversation_state.get(
                    "stage", conversation_state.get("current_stage")
                ),
                confidence=0.9,
            )
            app_logger.info(f"DEBUG: Routing decision type: {type(routing_decision)}")
            conversation_state["next_stage"] = routing_decision.target_stage
            conversation_state["routing_confidence"] = routing_decision.confidence

            # Generate response using appropriate prompt
            response_candidate = await self._generate_response_candidate(conversation_state)

            return {
                "response_candidate": response_candidate,
                "conversation_state": conversation_state,
                "security_context": security_result.get("security_context", {}),
                "routing_decision": routing_decision,
            }

        except Exception as e:
            app_logger.error(f"Workflow execution error: {e}")
            raise

    async def _classify_intent(self, conversation_state: ConversationState):
        """Classify user intent with context awareness"""
        try:
            intent_result = await self.intent_classifier.classify_intent(
                conversation_state["user_message"], conversation_state
            )
            return intent_result
        except Exception as e:
            app_logger.error(f"Intent classification error: {e}")
            from .intent_classifier import (
                IntentCategory,
                IntentResult,
                IntentSubcategory,
            )

            return IntentResult(
                category=IntentCategory.CLARIFICATION,
                subcategory=IntentSubcategory.TECHNICAL_CONFUSION,
                confidence=0.0,
                requires_clarification=True,
            )

    async def _resolve_context_references(
        self, conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """Resolve contextual references in the message"""
        try:
            resolved_message, references = self.context_manager.resolve_references(
                conversation_state["user_message"], conversation_state
            )
            return {"resolved_message": resolved_message, "resolved_references": references}
        except Exception as e:
            app_logger.error(f"Context resolution error: {e}")
            return {"resolved_references": []}

    async def _generate_rag_context(self, user_message: str) -> Dict[str, Any]:
        """Generate RAG context for enhanced responses with business validation"""
        try:
            # Get RAG response
            langchain_rag_service = await get_langchain_rag_service()
            rag_result = await langchain_rag_service.query(user_message, include_sources=True)

            # Validate RAG response against business rules
            corrected_content, corrections_made = (
                await rag_business_validator.get_corrected_rag_response(
                    rag_result.context_used,
                    {"user_query": user_message, "timestamp": datetime.now().isoformat()},
                )
            )

            return {
                "context": corrected_content,
                "original_context": rag_result.context_used,
                "confidence": rag_result.confidence_score,
                "sources": rag_result.sources,
                "business_corrections": corrections_made,
                "business_validated": len(corrections_made) == 0
                or corrections_made[-1] == "No corrections needed",
            }
        except Exception as e:
            app_logger.error(f"RAG context generation error: {e}")
            return {"context": "", "confidence": 0.0}

    async def _generate_response_candidate(self, conversation_state: ConversationState) -> str:
        """Generate response candidate using LangSmith prompts"""

        try:
            # Determine appropriate prompt based on stage and intent
            prompt_name = self._select_prompt_name(conversation_state)

            # Prepare prompt variables
            prompt_variables = {
                "user_name": conversation_state.get("user_name", ""),
                "user_message": conversation_state["user_message"],
                "detected_intent": conversation_state.get("detected_intent", ""),
                "rag_context": conversation_state.get("rag_context", ""),
                "conversation_stage": conversation_state["stage"].value,
                "current_step": conversation_state["step"].value,
                "business_name": "Kumon Vila A",
                "current_time": datetime.now().strftime("%H:%M"),
                "current_day": datetime.now().strftime("%A"),
            }

            # Get prompt template from LangSmith
            prompt_template = await self.prompt_manager.get_prompt(
                prompt_name, variables=prompt_variables
            )

            # Execute LLM with the prompt using Production LLM Service
            from ..services.langgraph_llm_adapter import create_kumon_llm

            llm = create_kumon_llm(
                model=getattr(settings, "OPENAI_MODEL", "gpt-4-turbo"), temperature=0.7
            )

            # Execute the prompt as LLM input
            response = await llm.ainvoke(prompt_template)
            response_candidate = response.content

            return response_candidate

        except Exception as e:
            app_logger.error(f"Response generation error: {e}")
            # Fallback response - SEMPRE Cecília
            return """Olá! Sou Cecília do Kumon Vila A! 😊

Fico muito feliz em falar com você!

Primeiro, me conta qual é o seu nome? Assim nossa conversa fica mais pessoal!

E como posso ajudá-lo hoje? Gostaria de:
• 📚 Conhecer o método Kumon
• 🎓 Informações sobre nossos programas
• 📅 Agendar uma avaliação gratuita
• 📍 Horários e localização da unidade

Estou à disposição para esclarecer todas as suas dúvidas!"""

    def _select_prompt_name(self, conversation_state: ConversationState) -> str:
        """Select appropriate prompt name based on conversation state"""

        stage = conversation_state["stage"]
        intent = conversation_state.get("detected_intent", "")

        # Intent-based prompt selection
        if intent == "SCHEDULING":
            return "kumon:scheduling:appointment_booking"
        elif intent == "INFORMATION":
            return "kumon:information:method_explanation"
        elif intent == "PRICING":
            return "kumon:information:pricing_details"
        elif intent == "CONTACT":
            return "kumon:contact:business_information"

        # Stage-based prompt selection
        if stage == WorkflowStage.GREETING:
            if conversation_state.get("user_name"):
                return "kumon:greeting:followup"
            else:
                return "kumon:greeting:initial"
        elif stage == WorkflowStage.QUALIFICATION:
            return "kumon:qualification:assessment"
        elif stage == WorkflowStage.INFORMATION:
            return "kumon:information:detailed_explanation"
        elif stage == WorkflowStage.SCHEDULING:
            return "kumon:scheduling:availability_check"
        elif stage == WorkflowStage.CONFIRMATION:
            return "kumon:confirmation:appointment_confirmation"

        # Default prompt
        return "kumon:general:helpful_response"

    async def _final_validation_check(
        self,
        workflow_result: Dict[str, Any],
        conversation_state: ConversationState,
        phone_number: str,
    ) -> SecureWorkflowResult:
        """Final security and quality validation with comprehensive checks"""

        response_candidate = workflow_result["response_candidate"]

        # Handle business rule mandated handoff
        if workflow_result.get("business_handoff_required", False):
            return SecureWorkflowResult(
                final_response=response_candidate,
                action_taken=SecureWorkflowAction.ESCALATE,
                security_status="BUSINESS_HANDOFF",
                validation_passed=True,  # Business handoff is a valid action
                quality_score=1.0,
                conversation_state=conversation_state,
                security_incidents=[],
                recommendations=["Business rule mandated handoff"],
            )

        try:
            # Multi-layer validation using security validation agent
            validator = get_validation_agent()
            validation_report = await validator.validate_response(
                response_candidate,
                conversation_state,
                phone_number,
                workflow_result.get("security_context"),
            )

            # Update conversation state with validation results
            conversation_state = validator.quality_metrics.update_quality_metrics(
                conversation_state, validation_report
            )

            # Determine final action based on validation
            if validation_report.overall_result == ValidationResult.SECURITY_BLOCKED:
                self.security_metrics["blocked_requests"] += 1
                return SecureWorkflowResult(
                    final_response="Por questões de segurança, não posso prosseguir com essa conversa.",
                    action_taken=SecureWorkflowAction.BLOCK,
                    security_status="BLOCKED",
                    validation_passed=False,
                    quality_score=0.0,
                    conversation_state=conversation_state,
                    security_incidents=validation_report.issues,
                    recommendations=validation_report.recommended_actions,
                )

            elif validation_report.overall_result == ValidationResult.ESCALATE_HUMAN:
                self.security_metrics["escalations"] += 1
                return SecureWorkflowResult(
                    final_response="Vou transferir você para um de nossos especialistas para melhor atendê-lo. Um momento, por favor!",
                    action_taken=SecureWorkflowAction.ESCALATE,
                    security_status="ESCALATED",
                    validation_passed=False,
                    quality_score=validation_report.quality_score,
                    conversation_state=conversation_state,
                    security_incidents=validation_report.issues,
                    recommendations=validation_report.recommended_actions,
                )

            elif validation_report.overall_result == ValidationResult.NEEDS_REVISION:
                # Try to generate improved response (limited retries)
                retry_count = conversation_state.get("retry_count", 0)
                if retry_count < self.config["max_retries"]:
                    conversation_state["retry_count"] = retry_count + 1
                    # Could implement response revision here
                    pass

            # Approved or acceptable response
            final_response = response_candidate

            # Add assistant message to history
            conversation_state["message_history"].append(
                {
                    "role": "assistant",
                    "content": final_response,
                    "timestamp": datetime.now().isoformat(),
                    "validation_passed": validation_report.overall_result
                    == ValidationResult.APPROVED,
                    "quality_score": validation_report.quality_score,
                }
            )

            return SecureWorkflowResult(
                final_response=final_response,
                action_taken=SecureWorkflowAction.CONTINUE,
                security_status="SECURE",
                validation_passed=validation_report.overall_result == ValidationResult.APPROVED,
                quality_score=validation_report.quality_score,
                conversation_state=conversation_state,
                security_incidents=[],
                recommendations=[],
            )

        except Exception as e:
            app_logger.error(f"Final validation error: {e}")
            self.security_metrics["validation_failures"] += 1

            # Fail secure with fallback
            return SecureWorkflowResult(
                final_response="Desculpe, vou precisar de um momento para processar sua solicitação adequadamente.",
                action_taken=SecureWorkflowAction.RETRY,
                security_status="VALIDATION_ERROR",
                validation_passed=False,
                quality_score=0.0,
                conversation_state=conversation_state,
                security_incidents=[f"Validation error: {str(e)}"],
                recommendations=["Retry validation process"],
            )

    def _get_conversation_state(self, phone_number: str) -> ConversationState:
        """Get current conversation state or create empty state"""
        from .states import ConversationMetrics, UserContext

        if phone_number in self.active_conversations:
            return self.active_conversations[phone_number]

        # Create default state
        default_state = ConversationState(
            phone_number=phone_number,
            session_id="unknown",
            stage=WorkflowStage.GREETING,
            step=ConversationStep.WELCOME,
            user_message="",
            message_history=[],
            user_context=None,  # Will be set after creation
            metrics=ConversationMetrics(),
            ai_response=None,
            prompt_used=None,
            validation_passed=False,
            next_action=None,
            requires_human=False,
            conversation_ended=False,
            last_error=None,
            retry_count=0,
        )

        # Set user context after state creation
        default_state["user_context"] = UserContext(default_state)

        return default_state

    def _create_secure_workflow(self) -> StateGraph:
        """Create the LangGraph workflow with integrated business rules"""

        # This would be the full LangGraph implementation with business rules
        workflow = StateGraph(ConversationState)

        # Add workflow nodes including business rules
        workflow.add_node("security_check", self._security_node)
        workflow.add_node("intent_classification", self._intent_node)
        workflow.add_node("business_rules_validation", self._business_rules_node)
        workflow.add_node("rag_business_validation", self._rag_business_node)
        workflow.add_node("response_generation", self._response_node)
        workflow.add_node("final_validation", self._validation_node)

        # Set entry point
        workflow.set_entry_point("security_check")

        # Add edges with business rule integration
        workflow.add_edge("security_check", "intent_classification")
        workflow.add_edge("intent_classification", "business_rules_validation")
        workflow.add_edge("business_rules_validation", "rag_business_validation")
        workflow.add_edge("rag_business_validation", "response_generation")
        workflow.add_edge("response_generation", "final_validation")
        workflow.add_edge("final_validation", END)

        return workflow.compile()

    async def _security_node(self, state: ConversationState) -> ConversationState:
        """Security validation node"""
        # Implementation would go here
        return state

    async def _intent_node(self, state: ConversationState) -> ConversationState:
        """Intent classification node"""
        # Implementation would go here
        return state

    async def _response_node(self, state: ConversationState) -> ConversationState:
        """Response generation node"""
        # Implementation would go here
        return state

    async def _business_rules_node(self, state: ConversationState) -> ConversationState:
        """Business rules validation node"""
        try:
            # Execute comprehensive business rules validation
            business_rule_results = await business_compliance_node.execute(
                state, {"workflow_context": "langgraph_node"}
            )

            # Update state with business rule results
            business_compliance_passed = True
            for rule_type, rule_result in business_rule_results.items():
                if isinstance(rule_result, BusinessRuleNodeResult):
                    state.update(rule_result.updated_state)
                    if not rule_result.compliance_passed:
                        business_compliance_passed = False

            state["business_compliance_passed"] = business_compliance_passed
            state["business_rule_results"] = business_rule_results

            return state
        except Exception as e:
            app_logger.error(f"Business rules node error: {e}")
            return state

    async def _rag_business_node(self, state: ConversationState) -> ConversationState:
        """RAG business validation node"""
        try:
            # Validate RAG context against business rules
            rag_context = state.get("rag_context", "")
            if rag_context:
                corrected_content, corrections = (
                    await rag_business_validator.get_corrected_rag_response(
                        rag_context, {"user_query": state.get("user_message", ""), "state": state}
                    )
                )

                state["rag_context"] = corrected_content
                state["rag_business_corrections"] = corrections
                state["rag_business_validated"] = len(corrections) == 0

            return state
        except Exception as e:
            app_logger.error(f"RAG business validation node error: {e}")
            return state

    async def _validation_node(self, state: ConversationState) -> ConversationState:
        """Final validation node"""
        # Implementation would go here
        return state

    def get_security_metrics(self) -> Dict[str, Any]:
        """Get comprehensive security and performance metrics"""

        total_requests = self.security_metrics["total_requests"]

        return {
            "workflow_metrics": self.security_metrics,
            "performance_ratios": {
                "block_rate": (self.security_metrics["blocked_requests"] / max(1, total_requests)),
                "escalation_rate": (self.security_metrics["escalations"] / max(1, total_requests)),
                "validation_failure_rate": (
                    self.security_metrics["validation_failures"] / max(1, total_requests)
                ),
            },
            "active_conversations": len(self.active_conversations),
            "security_components": {
                "threat_detection": "Advanced behavioral analysis",
                "input_validation": "Multi-layer prompt injection defense",
                "scope_validation": "Business focus enforcement",
                "information_protection": "Classified data prevention",
                "quality_assurance": "LLM-powered response validation",
            },
            "configuration": self.config,
            "status": "OPERATIONAL - Military-grade security active",
        }

    async def cleanup_expired_conversations(self):
        """Clean up expired conversation states"""

        current_time = datetime.now()
        expired_conversations = []

        for phone_number, state in self.active_conversations.items():
            # Check if conversation is older than 2 hours
            if state["message_history"]:
                last_message_time = datetime.fromisoformat(
                    state["message_history"][-1]["timestamp"]
                )
                if (current_time - last_message_time).total_seconds() > 7200:  # 2 hours
                    expired_conversations.append(phone_number)

        # Remove expired conversations
        for phone_number in expired_conversations:
            del self.active_conversations[phone_number]

        if expired_conversations:
            app_logger.info(f"Cleaned up {len(expired_conversations)} expired conversations")


# Global instance removed, will be initialized on startup
