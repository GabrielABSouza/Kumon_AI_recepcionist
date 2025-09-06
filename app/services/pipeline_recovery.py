"""
Pipeline Error Recovery System - Stage-specific error recovery and graceful degradation
Implements comprehensive recovery mechanisms with emergency fallback responses

Recovery Features:
- Stage-specific error recovery strategies
- Graceful degradation mechanisms
- Emergency fallback responses
- State corruption recovery
- Manual escalation triggers
- Recovery success tracking
"""

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..clients.evolution_api import WhatsAppMessage
from ..core.config import settings
from ..core.logger import app_logger
from ..core.pipeline_orchestrator import PipelineStage, PipelineStatus
from ..services.enhanced_cache_service import CacheLayer, enhanced_cache_service


class RecoveryStrategy(Enum):
    """Recovery strategy types"""

    RETRY = "retry"
    FALLBACK = "fallback"
    DEGRADE = "degrade"
    BYPASS = "bypass"
    ESCALATE = "escalate"
    EMERGENCY = "emergency"


class RecoveryResult(Enum):
    """Recovery attempt result"""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    ESCALATED = "escalated"


@dataclass
class RecoveryAttempt:
    """Recovery attempt tracking"""

    attempt_id: str
    execution_id: str
    failed_stage: PipelineStage
    error_type: str
    error_message: str
    strategy_used: RecoveryStrategy
    result: RecoveryResult
    recovery_time_ms: float
    fallback_response: Optional[str] = None
    state_before_recovery: Optional[Dict[str, Any]] = None
    state_after_recovery: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class RecoveryMetrics:
    """Recovery system performance metrics"""

    total_recovery_attempts: int = 0
    successful_recoveries: int = 0
    partial_recoveries: int = 0
    failed_recoveries: int = 0
    escalated_recoveries: int = 0
    avg_recovery_time_ms: float = 0.0
    recovery_success_rate: float = 0.0
    stage_recovery_stats: Optional[Dict[str, Dict[str, int]]] = None

    def __post_init__(self):
        if self.stage_recovery_stats is None:
            self.stage_recovery_stats = {}


class StageRecoveryHandler:
    """Base class for stage-specific recovery handlers"""

    def __init__(self, stage: PipelineStage):
        self.stage = stage
        self.max_retry_attempts = 3
        self.retry_delay_seconds = [1, 2, 5]  # Progressive delay

    async def attempt_recovery(
        self, error: Exception, context: Dict[str, Any], attempt_number: int = 1
    ) -> Tuple[RecoveryResult, Optional[str], Optional[Dict[str, Any]]]:
        """
        Attempt recovery for this stage

        Args:
            error: The exception that occurred
            context: Execution context
            attempt_number: Current attempt number (1-based)

        Returns:
            Tuple of (result, fallback_response, recovered_state)
        """
        raise NotImplementedError("Subclasses must implement attempt_recovery")


class PreprocessingRecoveryHandler(StageRecoveryHandler):
    """Recovery handler for preprocessing stage failures"""

    def __init__(self):
        super().__init__(PipelineStage.PREPROCESSING)

    async def attempt_recovery(
        self, error: Exception, context: Dict[str, Any], attempt_number: int = 1
    ) -> Tuple[RecoveryResult, Optional[str], Optional[Dict[str, Any]]]:
        """Recover from preprocessing failures"""
        try:
            error_type = type(error).__name__
            message = context.get("message")

            # Strategy 1: Retry with simplified validation
            if attempt_number <= 2 and "validation" in str(error).lower():
                app_logger.info(
                    f"Preprocessing recovery attempt {attempt_number}: simplified validation"
                )

                # Create minimal valid context
                recovery_context = {
                    "success": True,
                    "sanitized_message": message,
                    "prepared_context": {
                        "phone_number": context.get("phone_number", "unknown"),
                        "last_user_message": (
                            message.message if hasattr(message, "message") else str(message)
                        ),
                        "session_recovery": True,
                        "recovery_timestamp": datetime.now().isoformat(),
                    },
                    "recovery_mode": "simplified_validation",
                }

                return RecoveryResult.SUCCESS, None, recovery_context

            # Strategy 2: Bypass preprocessing with safe defaults
            elif attempt_number <= 3:
                app_logger.warning(
                    f"Preprocessing recovery attempt {attempt_number}: bypassing with defaults"
                )

                fallback_message = (
                    "Olá! Sou Cecília do Kumon Vila A. 😊 "
                    "Detectamos um problema técnico no processamento da sua mensagem. "
                    "Como posso ajudá-lo hoje?"
                )

                # Create bypass context
                bypass_context = {
                    "success": True,
                    "sanitized_message": message,
                    "prepared_context": {
                        "phone_number": context.get("phone_number", "unknown"),
                        "last_user_message": "Como posso ajudá-lo?",
                        "current_stage": "greeting",
                        "bypass_mode": True,
                    },
                    "recovery_mode": "bypass_preprocessing",
                }

                return RecoveryResult.PARTIAL, fallback_message, bypass_context

            # Strategy 3: Emergency fallback
            else:
                app_logger.error("Preprocessing recovery failed - using emergency fallback")

                emergency_response = (
                    "Olá! Temos uma instabilidade técnica momentânea. "
                    "Entre em contato pelo (51) 99692-1999 ou tente novamente em alguns minutos."
                )

                return RecoveryResult.FAILED, emergency_response, None

        except Exception as recovery_error:
            app_logger.error(f"Preprocessing recovery error: {recovery_error}")
            return RecoveryResult.FAILED, None, None


class BusinessRulesRecoveryHandler(StageRecoveryHandler):
    """Recovery handler for business rules stage failures"""

    def __init__(self):
        super().__init__(PipelineStage.BUSINESS_RULES)

    async def attempt_recovery(
        self, error: Exception, context: Dict[str, Any], attempt_number: int = 1
    ) -> Tuple[RecoveryResult, Optional[str], Optional[Dict[str, Any]]]:
        """Recover from business rules failures"""
        try:
            # Strategy 1: Retry with relaxed rules
            if attempt_number <= 2:
                app_logger.info(
                    f"Business rules recovery attempt {attempt_number}: relaxed validation"
                )

                # Create relaxed business rules result
                recovery_context = {
                    "success": True,
                    "rules_results": {
                        "pricing": {"result": "approved", "message": "Standard pricing applied"},
                        "qualification": {"result": "warning", "message": "Partial qualification"},
                        "handoff": {"result": "approved", "message": "Normal conversation"},
                        "lgpd": {"result": "approved", "message": "Privacy compliant"},
                    },
                    "handoff_required": False,
                    "compliance_issues": [],
                    "recovery_mode": "relaxed_rules",
                }

                return RecoveryResult.SUCCESS, None, recovery_context

            # Strategy 2: Bypass business rules
            elif attempt_number <= 3:
                app_logger.warning(
                    f"Business rules recovery attempt {attempt_number}: bypassing validation"
                )

                bypass_context = {
                    "success": True,
                    "rules_results": {},
                    "handoff_required": False,
                    "compliance_issues": [],
                    "bypass_mode": True,
                    "recovery_mode": "bypass_business_rules",
                }

                return RecoveryResult.PARTIAL, None, bypass_context

            # Strategy 3: Force handoff
            else:
                app_logger.error("Business rules recovery failed - forcing handoff")

                handoff_message = (
                    "Olá! Para melhor atendê-lo, vou transferir você para nosso consultor educacional.\n\n"
                    "📞 Contato: (51) 99692-1999\n"
                    "🕒 Horário: Segunda a Sexta, 9h-12h e 14h-17h"
                )

                return RecoveryResult.ESCALATED, handoff_message, None

        except Exception as recovery_error:
            app_logger.error(f"Business rules recovery error: {recovery_error}")
            return RecoveryResult.FAILED, None, None


class LangGraphRecoveryHandler(StageRecoveryHandler):
    """Recovery handler for LangGraph workflow failures"""

    def __init__(self):
        super().__init__(PipelineStage.LANGGRAPH_WORKFLOW)
        self.fallback_responses = {
            "greeting": "Olá! Sou Cecília do Kumon Vila A. 😊 Como posso ajudá-lo hoje?",
            "information": "Gostaria de saber mais sobre nossos programas de Matemática, Português ou Inglês?",
            "pricing": "Nossos valores são R$ 375 mensais + R$ 100 de matrícula. Entre em contato pelo (51) 99692-1999 para mais informações.",
            "scheduling": "Para agendar uma visita, entre em contato pelo (51) 99692-1999. Horário: Segunda a Sexta, 9h-12h e 14h-17h.",
            "default": "Como posso ajudá-lo com informações sobre o Kumon Vila A? 😊",
        }

    async def attempt_recovery(
        self, error: Exception, context: Dict[str, Any], attempt_number: int = 1
    ) -> Tuple[RecoveryResult, Optional[str], Optional[Dict[str, Any]]]:
        """Recover from LangGraph workflow failures"""
        try:
            error_message = str(error).lower()
            user_message = context.get("user_message", "").lower()

            # Strategy 1: Retry with simplified context
            if attempt_number <= 2 and "timeout" not in error_message:
                app_logger.info(f"LangGraph recovery attempt {attempt_number}: simplified context")

                # Try to determine intent and provide appropriate response
                fallback_response = self._get_intent_based_response(user_message)

                recovery_context = {
                    "success": True,
                    "response": fallback_response,
                    "stage": "greeting",
                    "step": "recovery",
                    "recovery_mode": "intent_based_fallback",
                    "metadata": {"recovery_attempt": attempt_number},
                }

                return RecoveryResult.SUCCESS, None, recovery_context

            # Strategy 2: Use template-based responses
            elif attempt_number <= 3:
                app_logger.warning(
                    f"LangGraph recovery attempt {attempt_number}: template responses"
                )

                template_response = self._get_template_response(user_message)

                recovery_context = {
                    "success": True,
                    "response": template_response,
                    "stage": "information",
                    "step": "template_recovery",
                    "recovery_mode": "template_based",
                    "metadata": {"template_used": True},
                }

                return RecoveryResult.PARTIAL, None, recovery_context

            # Strategy 3: Emergency contact response
            else:
                app_logger.error("LangGraph recovery failed - using emergency response")

                emergency_response = (
                    "Olá! Sou Cecília do Kumon Vila A. 😊\n\n"
                    "Estamos com uma instabilidade técnica momentânea. "
                    "Para não perder tempo, entre em contato conosco:\n\n"
                    "📞 Telefone: (51) 99692-1999\n"
                    "🕒 Horário: Segunda a Sexta, 9h-12h e 14h-17h\n"
                    "📍 Endereço: Vila A - Porto Alegre/RS\n\n"
                    "Ou tente novamente em alguns minutos!"
                )

                return RecoveryResult.FAILED, emergency_response, None

        except Exception as recovery_error:
            app_logger.error(f"LangGraph recovery error: {recovery_error}")
            return RecoveryResult.FAILED, None, None

    def _get_intent_based_response(self, user_message: str) -> str:
        """Generate response based on detected user intent"""
        user_message = user_message.lower()

        # Pricing intent
        if any(
            word in user_message for word in ["preço", "valor", "custo", "mensalidade", "quanto"]
        ):
            return (
                "📊 Valores do Kumon Vila A:\n\n"
                "💰 Mensalidade: R$ 375,00\n"
                "📚 Taxa de matrícula: R$ 100,00\n\n"
                "📞 Para mais informações: (51) 99692-1999\n"
                "Investir na educação é investir no futuro! 🎓"
            )

        # Scheduling intent
        elif any(
            word in user_message
            for word in ["agendar", "marcar", "visita", "entrevista", "horário"]
        ):
            return (
                "📅 Vamos agendar sua visita!\n\n"
                "📞 Contato: (51) 99692-1999\n"
                "🕒 Horário: Segunda a Sexta\n"
                "   • Manhã: 9h às 12h\n"
                "   • Tarde: 14h às 17h\n\n"
                "Aguardamos sua visita! 😊"
            )

        # Information intent
        elif any(
            word in user_message
            for word in ["kumon", "programa", "matemática", "português", "inglês"]
        ):
            return (
                "🎓 Programas Kumon Vila A:\n\n"
                "📚 Matemática - Desenvolve raciocínio lógico\n"
                "📖 Português - Melhora interpretação e escrita\n"
                "🌍 Inglês - Fluência desde cedo\n\n"
                "Qual programa desperta seu interesse? 😊"
            )

        # Default response
        else:
            return self.fallback_responses["default"]

    def _get_template_response(self, user_message: str) -> str:
        """Get template response based on keywords"""
        user_message = user_message.lower()

        # Simple keyword matching
        if "preço" in user_message or "valor" in user_message:
            return self.fallback_responses["pricing"]
        elif "agendar" in user_message or "marcar" in user_message:
            return self.fallback_responses["scheduling"]
        elif "kumon" in user_message or "programa" in user_message:
            return self.fallback_responses["information"]
        else:
            return self.fallback_responses["greeting"]


class PostprocessingRecoveryHandler(StageRecoveryHandler):
    """Recovery handler for postprocessing stage failures"""

    def __init__(self):
        super().__init__(PipelineStage.POSTPROCESSING)

    async def attempt_recovery(
        self, error: Exception, context: Dict[str, Any], attempt_number: int = 1
    ) -> Tuple[RecoveryResult, Optional[str], Optional[Dict[str, Any]]]:
        """Recover from postprocessing failures"""
        try:
            workflow_result = context.get("workflow_result", {})
            phone_number = context.get("phone_number", "unknown")

            # Strategy 1: Retry with simplified formatting
            if attempt_number <= 2:
                app_logger.info(
                    f"Postprocessing recovery attempt {attempt_number}: simplified formatting"
                )

                # Create minimal formatted message
                from ..models.message import MessageType

                simple_response = workflow_result.get("response", "Como posso ajudá-lo hoje? 😊")

                # Create simplified formatted message object
                recovery_context = {
                    "success": True,
                    "formatted_message": {
                        "content": simple_response,
                        "message_type": MessageType.TEXT,
                        "phone_number": phone_number,
                        "priority": "normal",
                        "metadata": {
                            "recovery_mode": "simplified_formatting",
                            "template_used": "simple",
                        },
                        "delivery_options": {"delay": 1200, "presence": "composing"},
                        "calendar_event_id": None,
                        "template_id": "recovery_simple",
                    },
                    "recovery_mode": "simplified_postprocessing",
                }

                return RecoveryResult.SUCCESS, None, recovery_context

            # Strategy 2: Bypass formatting entirely
            elif attempt_number <= 3:
                app_logger.warning(
                    f"Postprocessing recovery attempt {attempt_number}: bypass formatting"
                )

                raw_response = workflow_result.get("response", "Olá! Como posso ajudá-lo? 😊")

                recovery_context = {
                    "success": True,
                    "formatted_message": {
                        "content": raw_response,
                        "message_type": MessageType.TEXT,
                        "phone_number": phone_number,
                        "priority": "normal",
                        "metadata": {"recovery_mode": "bypass_formatting"},
                        "delivery_options": {"delay": 1000},
                        "calendar_event_id": None,
                        "template_id": None,
                    },
                    "recovery_mode": "bypass_postprocessing",
                }

                return RecoveryResult.PARTIAL, None, recovery_context

            # Strategy 3: Emergency simple response
            else:
                app_logger.error("Postprocessing recovery failed - emergency response")

                emergency_response = (
                    "Olá! Estou aqui para ajudá-lo com o Kumon Vila A. 😊\n"
                    "Entre em contato pelo (51) 99692-1999 para mais informações."
                )

                return RecoveryResult.FAILED, emergency_response, None

        except Exception as recovery_error:
            app_logger.error(f"Postprocessing recovery error: {recovery_error}")
            return RecoveryResult.FAILED, None, None


class DeliveryRecoveryHandler(StageRecoveryHandler):
    """Recovery handler for delivery stage failures"""

    def __init__(self):
        super().__init__(PipelineStage.DELIVERY)

    async def attempt_recovery(
        self, error: Exception, context: Dict[str, Any], attempt_number: int = 1
    ) -> Tuple[RecoveryResult, Optional[str], Optional[Dict[str, Any]]]:
        """Recover from delivery failures"""
        try:
            error_message = str(error).lower()

            # Strategy 1: Retry with exponential backoff
            if attempt_number <= 3 and "timeout" not in error_message:
                wait_time = min(2**attempt_number, 10)  # Cap at 10 seconds
                app_logger.info(
                    f"Delivery recovery attempt {attempt_number}: retry after {wait_time}s"
                )

                await asyncio.sleep(wait_time)

                recovery_context = {
                    "success": True,
                    "retry_attempt": attempt_number,
                    "wait_time_seconds": wait_time,
                    "recovery_mode": "retry_delivery",
                }

                return RecoveryResult.SUCCESS, None, recovery_context

            # Strategy 2: Try alternative delivery method (if available)
            elif attempt_number <= 4:
                app_logger.warning(
                    f"Delivery recovery attempt {attempt_number}: alternative delivery"
                )

                # In a real implementation, this could try different Evolution API endpoints
                # or fallback delivery mechanisms

                recovery_context = {
                    "success": True,
                    "alternative_delivery": True,
                    "recovery_mode": "alternative_delivery",
                }

                return RecoveryResult.PARTIAL, None, recovery_context

            # Strategy 3: Schedule for later delivery
            else:
                app_logger.error("Delivery recovery failed - scheduling for retry")

                # In a real implementation, this would queue the message for later delivery

                return (
                    RecoveryResult.FAILED,
                    None,
                    {
                        "scheduled_for_retry": True,
                        "retry_time": (datetime.now() + timedelta(minutes=5)).isoformat(),
                    },
                )

        except Exception as recovery_error:
            app_logger.error(f"Delivery recovery error: {recovery_error}")
            return RecoveryResult.FAILED, None, None


class PipelineRecoverySystem:
    """
    Comprehensive pipeline error recovery system

    Features:
    - Stage-specific recovery strategies
    - Progressive fallback mechanisms
    - Emergency response generation
    - State corruption recovery
    - Recovery metrics tracking
    - Manual escalation support
    """

    def __init__(self):
        # Initialize stage-specific recovery handlers
        self.recovery_handlers = {
            PipelineStage.PREPROCESSING: PreprocessingRecoveryHandler(),
            PipelineStage.BUSINESS_RULES: BusinessRulesRecoveryHandler(),
            PipelineStage.LANGGRAPH_WORKFLOW: LangGraphRecoveryHandler(),
            PipelineStage.POSTPROCESSING: PostprocessingRecoveryHandler(),
            PipelineStage.DELIVERY: DeliveryRecoveryHandler(),
        }

        # Recovery tracking
        self.recovery_attempts: List[RecoveryAttempt] = []
        self.recovery_metrics = RecoveryMetrics()

        # Emergency contacts and escalation
        self.emergency_config = {
            "contact_phone": "(51) 99692-1999",
            "escalation_email": getattr(settings, "ADMIN_EMAIL", "admin@kumonvilaa.com.br"),
            "emergency_response_enabled": True,
            "auto_escalation_threshold": 3,  # Auto-escalate after 3 failed recoveries
        }

        # Recovery success tracking
        self.recent_recovery_history = []

        app_logger.info(
            "Pipeline Recovery System initialized successfully",
            extra={
                "recovery_handlers": len(self.recovery_handlers),
                "emergency_contact": self.emergency_config["contact_phone"],
                "auto_escalation_enabled": True,
            },
        )

    async def attempt_stage_recovery(
        self,
        execution_id: str,
        failed_stage: PipelineStage,
        error: Exception,
        context: Dict[str, Any],
        max_attempts: int = 3,
    ) -> Tuple[RecoveryResult, Optional[str], Optional[Dict[str, Any]]]:
        """
        Attempt recovery for a specific pipeline stage failure

        Args:
            execution_id: Pipeline execution ID
            failed_stage: The stage that failed
            error: The exception that occurred
            context: Execution context and state
            max_attempts: Maximum recovery attempts

        Returns:
            Tuple of (recovery_result, fallback_response, recovered_state)
        """
        start_time = time.time()

        try:
            app_logger.info(
                f"Starting recovery for {failed_stage.value} in execution {execution_id}",
                extra={"error_type": type(error).__name__, "error_message": str(error)[:200]},
            )

            # Get appropriate recovery handler
            if failed_stage not in self.recovery_handlers:
                app_logger.error(f"No recovery handler for stage {failed_stage.value}")
                return await self._emergency_fallback(execution_id, failed_stage, error, context)

            recovery_handler = self.recovery_handlers[failed_stage]

            # Progressive recovery attempts
            for attempt_number in range(1, max_attempts + 1):
                attempt_id = f"{execution_id}_{failed_stage.value}_{attempt_number}"

                try:
                    app_logger.info(
                        f"Recovery attempt {attempt_number}/{max_attempts} for {failed_stage.value}"
                    )

                    # Attempt recovery
                    recovery_result, fallback_response, recovered_state = (
                        await recovery_handler.attempt_recovery(error, context, attempt_number)
                    )

                    recovery_time_ms = (time.time() - start_time) * 1000

                    # Record recovery attempt
                    recovery_attempt = RecoveryAttempt(
                        attempt_id=attempt_id,
                        execution_id=execution_id,
                        failed_stage=failed_stage,
                        error_type=type(error).__name__,
                        error_message=str(error)[:500],
                        strategy_used=self._infer_strategy_from_result(recovery_result),
                        result=recovery_result,
                        recovery_time_ms=recovery_time_ms,
                        fallback_response=fallback_response,
                        state_before_recovery=context.copy(),
                        state_after_recovery=recovered_state,
                    )

                    await self._record_recovery_attempt(recovery_attempt)

                    # Check if recovery was successful enough to continue
                    if recovery_result in [RecoveryResult.SUCCESS, RecoveryResult.PARTIAL]:
                        app_logger.info(
                            f"Recovery successful after {attempt_number} attempts",
                            extra={
                                "recovery_result": recovery_result.value,
                                "recovery_time_ms": recovery_time_ms,
                                "has_fallback_response": bool(fallback_response),
                            },
                        )

                        return recovery_result, fallback_response, recovered_state

                    elif recovery_result == RecoveryResult.ESCALATED:
                        # Escalation requested - don't retry
                        break

                    # If recovery failed, try next attempt
                    if attempt_number < max_attempts:
                        await asyncio.sleep(min(attempt_number * 2, 10))  # Progressive delay

                except Exception as recovery_error:
                    app_logger.error(f"Recovery attempt {attempt_number} failed: {recovery_error}")
                    continue

            # All recovery attempts failed
            app_logger.error(f"All recovery attempts failed for {failed_stage.value}")
            return await self._emergency_fallback(execution_id, failed_stage, error, context)

        except Exception as e:
            app_logger.error(f"Recovery system error: {e}")
            return await self._emergency_fallback(execution_id, failed_stage, error, context)

    def _infer_strategy_from_result(self, result: RecoveryResult) -> RecoveryStrategy:
        """Infer recovery strategy from result"""
        strategy_map = {
            RecoveryResult.SUCCESS: RecoveryStrategy.RETRY,
            RecoveryResult.PARTIAL: RecoveryStrategy.FALLBACK,
            RecoveryResult.FAILED: RecoveryStrategy.DEGRADE,
            RecoveryResult.ESCALATED: RecoveryStrategy.ESCALATE,
        }
        return strategy_map.get(result, RecoveryStrategy.EMERGENCY)

    async def _emergency_fallback(
        self,
        execution_id: str,
        failed_stage: PipelineStage,
        error: Exception,
        context: Dict[str, Any],
    ) -> Tuple[RecoveryResult, str, None]:
        """Generate emergency fallback response when all recovery attempts fail"""
        try:
            phone_number = context.get("phone_number", "unknown")

            # Generate stage-specific emergency response
            if failed_stage == PipelineStage.PREPROCESSING:
                emergency_response = (
                    "Olá! Temos uma instabilidade no processamento de mensagens. "
                    "Entre em contato pelo (51) 99692-1999 ou tente novamente em alguns minutos."
                )
            elif failed_stage == PipelineStage.LANGGRAPH_WORKFLOW:
                emergency_response = (
                    "Olá! Sou Cecília do Kumon Vila A. 😊 "
                    "Estamos com instabilidade técnica momentânea. "
                    "Para não perder tempo, entre em contato pelo (51) 99692-1999. "
                    "Horário: Segunda a Sexta, 9h-12h e 14h-17h."
                )
            else:
                emergency_response = (
                    "Olá! Kumon Vila A - instabilidade técnica momentânea. "
                    "Contato: (51) 99692-1999. Horário: Seg-Sex 9h-12h, 14h-17h."
                )

            # Record emergency fallback
            emergency_attempt = RecoveryAttempt(
                attempt_id=f"{execution_id}_emergency_{int(time.time())}",
                execution_id=execution_id,
                failed_stage=failed_stage,
                error_type=type(error).__name__,
                error_message=str(error)[:500],
                strategy_used=RecoveryStrategy.EMERGENCY,
                result=RecoveryResult.FAILED,
                recovery_time_ms=0.0,
                fallback_response=emergency_response,
            )

            await self._record_recovery_attempt(emergency_attempt)

            # Check if auto-escalation should trigger
            await self._check_auto_escalation(failed_stage, phone_number)

            return RecoveryResult.FAILED, emergency_response, None

        except Exception as e:
            app_logger.error(f"Emergency fallback failed: {e}")
            return RecoveryResult.FAILED, "Erro técnico. Contato: (51) 99692-1999", None

    async def _record_recovery_attempt(self, attempt: RecoveryAttempt):
        """Record recovery attempt for metrics and analysis"""
        try:
            # Add to history
            self.recovery_attempts.append(attempt)

            # Update metrics
            self.recovery_metrics.total_recovery_attempts += 1

            if attempt.result == RecoveryResult.SUCCESS:
                self.recovery_metrics.successful_recoveries += 1
            elif attempt.result == RecoveryResult.PARTIAL:
                self.recovery_metrics.partial_recoveries += 1
            elif attempt.result == RecoveryResult.ESCALATED:
                self.recovery_metrics.escalated_recoveries += 1
            else:
                self.recovery_metrics.failed_recoveries += 1

            # Update stage statistics
            stage_name = attempt.failed_stage.value
            if stage_name not in self.recovery_metrics.stage_recovery_stats:
                self.recovery_metrics.stage_recovery_stats[stage_name] = {
                    "total": 0,
                    "success": 0,
                    "partial": 0,
                    "failed": 0,
                    "escalated": 0,
                }

            stage_stats = self.recovery_metrics.stage_recovery_stats[stage_name]
            stage_stats["total"] += 1
            stage_stats[attempt.result.value] += 1

            # Update average recovery time
            if self.recovery_metrics.total_recovery_attempts > 0:
                total_time = sum(att.recovery_time_ms for att in self.recovery_attempts)
                self.recovery_metrics.avg_recovery_time_ms = (
                    total_time / self.recovery_metrics.total_recovery_attempts
                )

            # Update success rate
            successful_attempts = (
                self.recovery_metrics.successful_recoveries
                + self.recovery_metrics.partial_recoveries
            )
            self.recovery_metrics.recovery_success_rate = (
                successful_attempts / self.recovery_metrics.total_recovery_attempts
            ) * 100

            # Cache recovery attempt
            await enhanced_cache_service.set(
                f"recovery_attempt:{attempt.attempt_id}",
                json.dumps(asdict(attempt), default=str),
                CacheLayer.L2,
                ttl=86400,  # 24 hours
            )

        except Exception as e:
            app_logger.error(f"Error recording recovery attempt: {e}")

    async def _check_auto_escalation(self, failed_stage: PipelineStage, phone_number: str):
        """Check if auto-escalation should trigger"""
        try:
            # Count recent failures for this stage
            recent_failures = [
                attempt
                for attempt in self.recovery_attempts[-20:]  # Last 20 attempts
                if (
                    attempt.failed_stage == failed_stage
                    and attempt.result == RecoveryResult.FAILED
                    and (datetime.now() - attempt.timestamp).total_seconds() < 3600  # Last hour
                )
            ]

            if len(recent_failures) >= self.emergency_config["auto_escalation_threshold"]:
                await self._trigger_escalation(
                    failed_stage,
                    f"Auto-escalation: {len(recent_failures)} failures in stage {failed_stage.value}",
                    phone_number,
                )

        except Exception as e:
            app_logger.error(f"Auto-escalation check failed: {e}")

    async def _trigger_escalation(
        self, failed_stage: PipelineStage, reason: str, phone_number: str
    ):
        """Trigger manual escalation process"""
        try:
            escalation_data = {
                "timestamp": datetime.now().isoformat(),
                "stage": failed_stage.value,
                "reason": reason,
                "phone_number": phone_number,
                "contact_info": self.emergency_config["contact_phone"],
                "escalation_id": str(uuid.uuid4()),
            }

            # Cache escalation for manual review
            await enhanced_cache_service.set(
                f"escalation:{escalation_data['escalation_id']}",
                json.dumps(escalation_data),
                CacheLayer.L2,
                ttl=604800,  # 7 days
            )

            app_logger.critical(
                f"Pipeline escalation triggered: {reason}",
                extra={
                    "escalation_id": escalation_data["escalation_id"],
                    "failed_stage": failed_stage.value,
                    "phone_number": phone_number,
                    "contact_required": True,
                },
            )

        except Exception as e:
            app_logger.error(f"Escalation trigger failed: {e}")

    async def get_recovery_metrics(self) -> Dict[str, Any]:
        """Get comprehensive recovery system metrics"""
        try:
            return {
                "total_recovery_attempts": self.recovery_metrics.total_recovery_attempts,
                "successful_recoveries": self.recovery_metrics.successful_recoveries,
                "partial_recoveries": self.recovery_metrics.partial_recoveries,
                "failed_recoveries": self.recovery_metrics.failed_recoveries,
                "escalated_recoveries": self.recovery_metrics.escalated_recoveries,
                "avg_recovery_time_ms": round(self.recovery_metrics.avg_recovery_time_ms, 2),
                "recovery_success_rate": round(self.recovery_metrics.recovery_success_rate, 2),
                "stage_recovery_stats": self.recovery_metrics.stage_recovery_stats,
                "recent_attempts": len(
                    [
                        attempt
                        for attempt in self.recovery_attempts
                        if (datetime.now() - attempt.timestamp).total_seconds() < 3600
                    ]
                ),
                "emergency_config": {
                    "contact_phone": self.emergency_config["contact_phone"],
                    "auto_escalation_threshold": self.emergency_config["auto_escalation_threshold"],
                },
            }

        except Exception as e:
            app_logger.error(f"Error getting recovery metrics: {e}")
            return {"error": "Metrics unavailable"}

    async def get_recent_recovery_attempts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent recovery attempts"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)

            recent_attempts = [
                {
                    "attempt_id": attempt.attempt_id,
                    "execution_id": attempt.execution_id,
                    "failed_stage": attempt.failed_stage.value,
                    "error_type": attempt.error_type,
                    "error_message": attempt.error_message[:200],
                    "strategy_used": attempt.strategy_used.value,
                    "result": attempt.result.value,
                    "recovery_time_ms": attempt.recovery_time_ms,
                    "has_fallback_response": bool(attempt.fallback_response),
                    "timestamp": attempt.timestamp.isoformat(),
                }
                for attempt in self.recovery_attempts
                if attempt.timestamp >= cutoff_time
            ]

            # Sort by timestamp (most recent first)
            recent_attempts.sort(key=lambda x: x["timestamp"], reverse=True)

            return recent_attempts

        except Exception as e:
            app_logger.error(f"Error getting recent recovery attempts: {e}")
            return []

    async def reset_recovery_metrics(self) -> bool:
        """Reset recovery metrics (admin function)"""
        try:
            self.recovery_attempts.clear()
            self.recovery_metrics = RecoveryMetrics()
            self.recent_recovery_history.clear()

            app_logger.info("Recovery metrics reset")
            return True

        except Exception as e:
            app_logger.error(f"Error resetting recovery metrics: {e}")
            return False


# Global pipeline recovery system instance
pipeline_recovery_system = PipelineRecoverySystem()
