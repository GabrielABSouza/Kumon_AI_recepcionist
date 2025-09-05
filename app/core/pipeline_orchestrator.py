"""
Pipeline Orchestrator - Phase 2 Wave 2.1 Implementation
Complete end-to-end message processing pipeline with enterprise-grade error handling and performance optimization

OBJECTIVE: <3s end-to-end WhatsApp response time with <1% error rate

Pipeline Flow:
Evolution API → Message Preprocessor → LangGraph Orchestrator → Message Postprocessor → Evolution API Response

Performance Targets:
- Pipeline execution: <2s per workflow
- Database operations: <200ms
- Cache hit rate: >80%
- Total response time: <3s
- Error rate: <1%
"""

import asyncio
import time
import json
import uuid
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import hashlib

from ..core.config import settings
from ..core.logger import app_logger
from ..services.message_preprocessor import message_preprocessor, PreprocessorResponse
from ..services.message_postprocessor import message_postprocessor, FormattedMessage
from ..services.business_rules_engine import business_rules_engine, RuleType, ValidationResult
from ..core.workflow import get_cecilia_workflow
from ..services.enhanced_cache_service import enhanced_cache_service, CacheLayer
from ..clients.evolution_api import WhatsAppMessage, EvolutionAPIClient


class PipelineStage(Enum):
    """Pipeline execution stages"""
    PREPROCESSING = "preprocessing"
    BUSINESS_RULES = "business_rules"
    LANGGRAPH_WORKFLOW = "langgraph_workflow"
    POSTPROCESSING = "postprocessing"
    DELIVERY = "delivery"


class PipelineStatus(Enum):
    """Pipeline execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"


@dataclass
class PipelineMetrics:
    """Pipeline performance metrics"""
    execution_id: str
    phone_number: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration_ms: float = 0.0
    stage_durations: Dict[str, float] = None
    cache_hits: int = 0
    cache_misses: int = 0
    errors: List[str] = None
    circuit_breaker_triggers: int = 0
    recovery_attempts: int = 0
    
    def __post_init__(self):
        if self.stage_durations is None:
            self.stage_durations = {}
        if self.errors is None:
            self.errors = []


@dataclass
class PipelineResult:
    """Complete pipeline execution result"""
    execution_id: str
    status: PipelineStatus
    response_message: str
    phone_number: str
    metrics: PipelineMetrics
    stage_results: Dict[str, Any] = None
    error_details: Optional[Dict[str, Any]] = None
    circuit_breaker_triggered: bool = False
    recovery_used: bool = False
    
    def __post_init__(self):
        if self.stage_results is None:
            self.stage_results = {}


class CircuitBreaker:
    """Circuit breaker for pipeline stage protection"""
    
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
        self.state_cache_key = f"circuit_breaker:{name}"
    
    async def can_execute(self) -> bool:
        """Check if circuit breaker allows execution"""
        # Check if circuit breaker is open
        if not self.is_open:
            return True
        
        # Check if recovery timeout has passed
        if self.last_failure_time:
            time_since_failure = time.time() - self.last_failure_time
            if time_since_failure > self.recovery_timeout:
                # Try to close circuit breaker
                self.is_open = False
                self.failure_count = 0
                self.last_failure_time = None
                await self._save_state()
                app_logger.info(f"Circuit breaker {self.name} recovered")
                return True
        
        return False
    
    async def record_success(self):
        """Record successful execution"""
        if self.failure_count > 0:
            self.failure_count = max(0, self.failure_count - 1)
            await self._save_state()
    
    async def record_failure(self):
        """Record failed execution"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            app_logger.warning(f"Circuit breaker {self.name} opened after {self.failure_count} failures")
        
        await self._save_state()
    
    async def _save_state(self):
        """Save circuit breaker state to cache"""
        try:
            state = {
                "failure_count": self.failure_count,
                "last_failure_time": self.last_failure_time,
                "is_open": self.is_open
            }
            await enhanced_cache_service.set(
                self.state_cache_key,
                json.dumps(state),
                CacheLayer.L2,
                ttl=3600
            )
        except Exception as e:
            app_logger.error(f"Failed to save circuit breaker state: {e}")
    
    async def load_state(self):
        """Load circuit breaker state from cache"""
        try:
            cached_state = await enhanced_cache_service.get(self.state_cache_key, CacheLayer.L2)
            if cached_state:
                state = json.loads(cached_state)
                self.failure_count = state.get("failure_count", 0)
                self.last_failure_time = state.get("last_failure_time")
                self.is_open = state.get("is_open", False)
        except Exception as e:
            app_logger.error(f"Failed to load circuit breaker state: {e}")


class PipelineOrchestrator:
    """
    Enterprise-grade message processing pipeline orchestrator
    
    Features:
    - Circuit breaker protection for each stage
    - Performance monitoring and metrics
    - Error recovery and graceful degradation
    - Cache optimization and hit rate tracking
    - Audit trail and compliance logging
    - SLA monitoring (<3s response time)
    """
    
    def __init__(self):
        # Initialize circuit breakers for each pipeline stage
        self.circuit_breakers = {
            PipelineStage.PREPROCESSING: CircuitBreaker("preprocessing", 5, 60),
            PipelineStage.BUSINESS_RULES: CircuitBreaker("business_rules", 3, 30),
            PipelineStage.LANGGRAPH_WORKFLOW: CircuitBreaker("langgraph_workflow", 3, 120),
            PipelineStage.POSTPROCESSING: CircuitBreaker("postprocessing", 5, 60),
            PipelineStage.DELIVERY: CircuitBreaker("delivery", 10, 30)
        }
        
        # Performance tracking
        self.performance_metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "avg_execution_time_ms": 0.0,
            "sla_violations": 0,  # >3s response time
            "cache_hit_rate": 0.0,
            "circuit_breaker_triggers": 0,
            "recovery_success_rate": 0.0
        }
        
        # Active executions tracking
        self.active_executions: Dict[str, PipelineResult] = {}
        
        # Cache for pipeline configurations
        self.pipeline_cache_ttl = 300  # 5 minutes
        
        # Initialize Evolution API client for delivery
        self.evolution_client = EvolutionAPIClient()
        
        app_logger.info("Pipeline Orchestrator initialized successfully", extra={
            "circuit_breakers": len(self.circuit_breakers),
            "sla_target_ms": 3000,
            "cache_enabled": True
        })
    
    async def initialize(self):
        """Initialize pipeline orchestrator and load circuit breaker states"""
        try:
            # Load circuit breaker states from cache
            for breaker in self.circuit_breakers.values():
                await breaker.load_state()
            
            app_logger.info("Pipeline orchestrator initialized successfully")
            return True
            
        except Exception as e:
            app_logger.error(f"Pipeline orchestrator initialization failed: {e}")
            return False
    
    async def execute_pipeline(
        self,
        message: WhatsAppMessage,
        headers: Dict[str, str],
        instance_name: str = "kumonvilaa",
        skip_preprocessing: bool = False
    ) -> PipelineResult:
        """
        Execute complete message processing pipeline
        
        Args:
            message: Incoming WhatsApp message
            headers: Request headers
            instance_name: Evolution API instance name
            skip_preprocessing: Skip preprocessing stage if message already preprocessed
            
        Returns:
            PipelineResult with execution details and response
        """
        execution_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        # Initialize metrics
        metrics = PipelineMetrics(
            execution_id=execution_id,
            phone_number=message.phone,
            start_time=start_time
        )
        
        # Initialize result
        result = PipelineResult(
            execution_id=execution_id,
            status=PipelineStatus.RUNNING,
            response_message="",
            phone_number=message.phone,
            metrics=metrics
        )
        
        # Track active execution
        self.active_executions[execution_id] = result
        self.performance_metrics["total_executions"] += 1
        
        try:
            app_logger.info(f"Starting pipeline execution {execution_id}", extra={
                "phone_number": message.phone,
                "message_length": len(message.message),
                "instance": instance_name
            })
            
            # Stage 1: Message Preprocessing
            preprocessing_result = await self._execute_preprocessing_stage(message, headers, metrics, skip_preprocessing)
            result.stage_results["preprocessing"] = preprocessing_result
            
            if not preprocessing_result.get("success", False):
                return await self._handle_pipeline_failure(
                    result, PipelineStage.PREPROCESSING, 
                    preprocessing_result.get("error", "Preprocessing failed")
                )
            
            # Check for business hours response (special case)
            if preprocessing_result.get("business_hours_response"):
                return await self._handle_business_hours_response(result, preprocessing_result)
            
            # Stage 2: Business Rules Validation
            business_rules_result = await self._execute_business_rules_stage(
                preprocessing_result["prepared_context"], metrics
            )
            result.stage_results["business_rules"] = business_rules_result
            
            # Handle business rule violations
            handoff_required = await self._check_handoff_requirements(business_rules_result)
            if handoff_required:
                return await self._handle_human_handoff(result, business_rules_result)
            
            # Stage 3: LangGraph Workflow Execution
            langgraph_result = await self._execute_langgraph_stage(
                preprocessing_result["sanitized_message"],
                preprocessing_result["prepared_context"],
                metrics
            )
            result.stage_results["langgraph_workflow"] = langgraph_result
            
            if not langgraph_result.get("success", False):
                return await self._handle_pipeline_failure(
                    result, PipelineStage.LANGGRAPH_WORKFLOW,
                    langgraph_result.get("error", "Workflow execution failed")
                )
            
            # Stage 4: Message Postprocessing
            postprocessing_result = await self._execute_postprocessing_stage(
                langgraph_result, message.phone, preprocessing_result["prepared_context"], metrics
            )
            result.stage_results["postprocessing"] = postprocessing_result
            
            if not postprocessing_result.get("success", False):
                return await self._handle_pipeline_failure(
                    result, PipelineStage.POSTPROCESSING,
                    postprocessing_result.get("error", "Postprocessing failed")
                )
            
            # Stage 5: Message Delivery
            delivery_result = await self._execute_delivery_stage(
                postprocessing_result["formatted_message"], instance_name, metrics
            )
            result.stage_results["delivery"] = delivery_result
            
            # Finalize pipeline result
            return await self._finalize_pipeline_result(result, delivery_result)
            
        except Exception as e:
            app_logger.error(f"Pipeline execution error {execution_id}: {e}", exc_info=True)
            return await self._handle_pipeline_failure(
                result, None, f"Unexpected pipeline error: {str(e)}"
            )
        finally:
            # Clean up active execution tracking
            if execution_id in self.active_executions:
                del self.active_executions[execution_id]
    
    async def _execute_preprocessing_stage(
        self,
        message: WhatsAppMessage,
        headers: Dict[str, str],
        metrics: PipelineMetrics,
        skip_preprocessing: bool = False
    ) -> Dict[str, Any]:
        """Execute message preprocessing stage with circuit breaker protection"""
        stage_start = time.time()
        stage_name = PipelineStage.PREPROCESSING
        circuit_breaker = self.circuit_breakers[stage_name]
        
        try:
            # Check circuit breaker
            if not await circuit_breaker.can_execute():
                metrics.circuit_breaker_triggers += 1
                return {
                    "success": False,
                    "error": "Preprocessing circuit breaker open",
                    "circuit_breaker_open": True
                }
            
            app_logger.debug(f"Executing preprocessing stage for {message.phone}")
            
            if skip_preprocessing:
                app_logger.debug("Skipping preprocessing stage - message already preprocessed by webhook")
                # Skip preprocessing stage entirely - message already processed by MessagePreprocessor
                result = {
                    "success": True,
                    "sanitized_message": message,
                    "prepared_context": {"last_user_message": message.message, "phone_number": message.phone},
                    "error_code": None,
                    "error_message": None,
                    "rate_limited": False,
                    "processing_time_ms": 0.0,
                    "business_hours_response": False
                }
            else:
                # Check cache for similar preprocessing
                cache_key = f"preprocessing:{hashlib.md5(f'{message.phone}:{message.message}'.encode()).hexdigest()}"
                cached_result = await enhanced_cache_service.get(cache_key, CacheLayer.L1)
                
                if cached_result:
                    metrics.cache_hits += 1
                    app_logger.debug("Preprocessing cache hit")
                    result = json.loads(cached_result)
                else:
                    metrics.cache_misses += 1
                    
                    # Execute full preprocessing pipeline
                    preprocessor_response = await message_preprocessor.process_message(message, headers)
                    result = {
                        "success": preprocessor_response.success,
                        "sanitized_message": preprocessor_response.message,
                        "prepared_context": preprocessor_response.prepared_context.__dict__ if preprocessor_response.prepared_context else {"last_user_message": message.message, "phone_number": message.phone},
                        "error_code": preprocessor_response.error_code,
                        "error_message": preprocessor_response.error_message,
                        "rate_limited": preprocessor_response.rate_limited,
                        "processing_time_ms": preprocessor_response.processing_time_ms,
                        "business_hours_response": preprocessor_response.business_hours_response
                    }
                    
                    # Cache successful preprocessing results
                    if result["success"] or result["business_hours_response"]:
                        await enhanced_cache_service.set(
                            cache_key, json.dumps(result, default=str), 
                            CacheLayer.L1, ttl=300
                        )
            
            # Record success
            await circuit_breaker.record_success()
            
            return result
            
        except Exception as e:
            await circuit_breaker.record_failure()
            metrics.errors.append(f"Preprocessing: {str(e)}")
            app_logger.error(f"Preprocessing stage failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "stage": "preprocessing"
            }
        finally:
            stage_duration = (time.time() - stage_start) * 1000
            metrics.stage_durations["preprocessing"] = stage_duration
    
    async def _execute_business_rules_stage(
        self,
        context: Dict[str, Any],
        metrics: PipelineMetrics
    ) -> Dict[str, Any]:
        """Execute business rules validation stage"""
        stage_start = time.time()
        stage_name = PipelineStage.BUSINESS_RULES
        circuit_breaker = self.circuit_breakers[stage_name]
        
        try:
            # Check circuit breaker
            if not await circuit_breaker.can_execute():
                metrics.circuit_breaker_triggers += 1
                return {
                    "success": False,
                    "error": "Business rules circuit breaker open",
                    "circuit_breaker_open": True
                }
            
            app_logger.debug("Executing business rules validation stage")
            
            # Extract message and context
            user_message = context.get("last_user_message", "")
            
            # Execute business rules evaluation
            rules_results = await business_rules_engine.evaluate_comprehensive_rules(
                message=user_message,
                context=context,
                rules_to_evaluate=[
                    RuleType.PRICING,
                    RuleType.QUALIFICATION,
                    RuleType.HANDOFF,
                    RuleType.LGPD
                ]
            )
            
            # Process results
            result = {
                "success": True,
                "rules_results": {},
                "handoff_required": False,
                "compliance_issues": []
            }
            
            for rule_type, rule_result in rules_results.items():
                result["rules_results"][rule_type.value] = {
                    "result": rule_result.result.value,
                    "message": rule_result.message,
                    "data": rule_result.data,
                    "processing_time_ms": rule_result.processing_time_ms
                }
                
                # Check for handoff requirement
                if rule_result.result == ValidationResult.REQUIRES_HANDOFF:
                    result["handoff_required"] = True
                
                # Check for compliance issues
                if rule_result.result == ValidationResult.REJECTED:
                    result["compliance_issues"].append({
                        "rule_type": rule_type.value,
                        "issue": rule_result.message,
                        "error_code": rule_result.error_code
                    })
            
            await circuit_breaker.record_success()
            return result
            
        except Exception as e:
            await circuit_breaker.record_failure()
            metrics.errors.append(f"Business rules: {str(e)}")
            app_logger.error(f"Business rules stage failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "stage": "business_rules"
            }
        finally:
            stage_duration = (time.time() - stage_start) * 1000
            metrics.stage_durations["business_rules"] = stage_duration
    
    async def _execute_langgraph_stage(
        self,
        message: WhatsAppMessage,
        context: Dict[str, Any],
        metrics: PipelineMetrics
    ) -> Dict[str, Any]:
        """Execute LangGraph workflow stage"""
        stage_start = time.time()
        stage_name = PipelineStage.LANGGRAPH_WORKFLOW
        circuit_breaker = self.circuit_breakers[stage_name]
        
        try:
            # Check circuit breaker
            if not await circuit_breaker.can_execute():
                metrics.circuit_breaker_triggers += 1
                return {
                    "success": False,
                    "error": "LangGraph workflow circuit breaker open",
                    "circuit_breaker_open": True
                }
            
            app_logger.debug(f"Executing LangGraph workflow for {message.phone}")
            
            # Execute workflow with timeout (pass instance)
            workflow_result = await asyncio.wait_for(
                get_cecilia_workflow().process_message(
                    phone_number=message.phone,
                    user_message=message.message,
                    instance="kumon_assistant",  # Pass valid instance explicitly
                    use_orchestrator=False  # Direct execution to avoid circular dependency
                ),
                timeout=30.0  # 30 second timeout
            )
            
            result = {
                "success": workflow_result.get("success", True),
                "response": workflow_result.get("response", ""),
                "stage": workflow_result.get("stage", "greeting"),
                "step": workflow_result.get("step", ""),
                "thread_id": workflow_result.get("thread_id", ""),
                "processing_time_ms": workflow_result.get("processing_time_ms", 0),
                "metadata": workflow_result.get("metadata", {})
            }
            
            await circuit_breaker.record_success()
            return result
            
        except asyncio.TimeoutError:
            await circuit_breaker.record_failure()
            metrics.errors.append("LangGraph workflow timeout")
            app_logger.error("LangGraph workflow timeout")
            
            return {
                "success": False,
                "error": "Workflow execution timeout",
                "timeout": True
            }
        except Exception as e:
            await circuit_breaker.record_failure()
            metrics.errors.append(f"LangGraph workflow: {str(e)}")
            app_logger.error(f"LangGraph workflow stage failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "stage": "langgraph_workflow"
            }
        finally:
            stage_duration = (time.time() - stage_start) * 1000
            metrics.stage_durations["langgraph_workflow"] = stage_duration
    
    async def _execute_postprocessing_stage(
        self,
        workflow_result: Dict[str, Any],
        phone_number: str,
        context: Dict[str, Any],
        metrics: PipelineMetrics
    ) -> Dict[str, Any]:
        """Execute message postprocessing stage"""
        stage_start = time.time()
        stage_name = PipelineStage.POSTPROCESSING
        circuit_breaker = self.circuit_breakers[stage_name]
        
        try:
            # Check circuit breaker
            if not await circuit_breaker.can_execute():
                metrics.circuit_breaker_triggers += 1
                return {
                    "success": False,
                    "error": "Postprocessing circuit breaker open",
                    "circuit_breaker_open": True
                }
            
            app_logger.debug(f"Executing postprocessing stage for {phone_number}")
            
            # Create MessageResponse object
            from ..models.message import MessageResponse, MessageType
            
            message_response = MessageResponse(
                content=workflow_result.get("response", ""),
                message_id=str(uuid.uuid4()),
                success=workflow_result.get("success", True),
                metadata=workflow_result.get("metadata", {}),
                message_type=MessageType.TEXT
            )
            
            # Execute postprocessing
            formatted_message = await message_postprocessor.process_message(
                response=message_response,
                phone_number=phone_number,
                context=context
            )
            
            result = {
                "success": True,
                "formatted_message": formatted_message,
                "processing_time_ms": formatted_message.formatting_time_ms,
                "template_used": formatted_message.template_id,
                "calendar_integrated": bool(formatted_message.calendar_event_id)
            }
            
            await circuit_breaker.record_success()
            return result
            
        except Exception as e:
            await circuit_breaker.record_failure()
            metrics.errors.append(f"Postprocessing: {str(e)}")
            app_logger.error(f"Postprocessing stage failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "stage": "postprocessing"
            }
        finally:
            stage_duration = (time.time() - stage_start) * 1000
            metrics.stage_durations["postprocessing"] = stage_duration
    
    async def _execute_delivery_stage(
        self,
        formatted_message: FormattedMessage,
        instance_name: str,
        metrics: PipelineMetrics
    ) -> Dict[str, Any]:
        """Execute message delivery stage"""
        stage_start = time.time()
        stage_name = PipelineStage.DELIVERY
        circuit_breaker = self.circuit_breakers[stage_name]
        
        try:
            # Check circuit breaker
            if not await circuit_breaker.can_execute():
                metrics.circuit_breaker_triggers += 1
                return {
                    "success": False,
                    "error": "Delivery circuit breaker open",
                    "circuit_breaker_open": True
                }
            
            app_logger.debug(f"Executing delivery stage for {formatted_message.phone_number}")
            
            # Execute delivery
            delivery_result = await message_postprocessor.deliver_message(
                formatted_message, instance_name
            )
            
            result = {
                "success": delivery_result.get("success", False),
                "message_id": delivery_result.get("message_id"),
                "delivery_time_ms": delivery_result.get("delivery_time_ms", 0),
                "evolution_message_id": delivery_result.get("evolution_message_id"),
                "status": delivery_result.get("status", "unknown"),
                "error": delivery_result.get("error")
            }
            
            if result["success"]:
                await circuit_breaker.record_success()
            else:
                await circuit_breaker.record_failure()
            
            return result
            
        except Exception as e:
            await circuit_breaker.record_failure()
            metrics.errors.append(f"Delivery: {str(e)}")
            app_logger.error(f"Delivery stage failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "stage": "delivery"
            }
        finally:
            stage_duration = (time.time() - stage_start) * 1000
            metrics.stage_durations["delivery"] = stage_duration
    
    async def _check_handoff_requirements(self, business_rules_result: Dict[str, Any]) -> bool:
        """Check if human handoff is required based on business rules"""
        if not business_rules_result.get("success", False):
            return False
        
        return business_rules_result.get("handoff_required", False)
    
    async def _handle_human_handoff(
        self,
        result: PipelineResult,
        business_rules_result: Dict[str, Any]
    ) -> PipelineResult:
        """Handle human handoff scenario"""
        handoff_info = await business_rules_engine.get_handoff_contact()
        
        handoff_message = (
            f"Olá! Sou Cecília do Kumon Vila A. 😊\n\n"
            f"Para melhor atendê-lo, vou transferir você para nosso consultor educacional.\n\n"
            f"📞 Contato direto: {handoff_info['phone']}\n"
            f"🕒 Horário: {handoff_info['availability']}\n\n"
            f"Ou aguarde que entraremos em contato em breve!"
        )
        
        result.status = PipelineStatus.COMPLETED
        result.response_message = handoff_message
        result.stage_results["handoff"] = {
            "handoff_triggered": True,
            "reason": business_rules_result.get("rules_results", {}),
            "contact_info": handoff_info
        }
        
        return await self._finalize_pipeline_result(result, {"success": True, "handoff": True})
    
    async def _handle_business_hours_response(
        self,
        result: PipelineResult,
        preprocessing_result: Dict[str, Any]
    ) -> PipelineResult:
        """Handle business hours auto-response"""
        business_hours_message = preprocessing_result["prepared_context"].get("last_bot_response", "")
        
        result.status = PipelineStatus.COMPLETED
        result.response_message = business_hours_message
        result.stage_results["business_hours"] = {
            "auto_response": True,
            "message": business_hours_message,
            "next_business_time": preprocessing_result.get("error_message", "")
        }
        
        return await self._finalize_pipeline_result(result, {"success": True, "business_hours": True})
    
    async def _handle_pipeline_failure(
        self,
        result: PipelineResult,
        failed_stage: Optional[PipelineStage],
        error_message: str
    ) -> PipelineResult:
        """Handle pipeline execution failure with recovery attempts"""
        result.status = PipelineStatus.FAILED
        result.error_details = {
            "failed_stage": failed_stage.value if failed_stage else "unknown",
            "error_message": error_message,
            "timestamp": datetime.now().isoformat()
        }
        
        # Attempt recovery based on failed stage
        recovery_attempted = False
        recovery_success = False
        
        if failed_stage and failed_stage != PipelineStage.DELIVERY:
            recovery_attempted = True
            result.metrics.recovery_attempts += 1
            
            # Try graceful degradation
            fallback_message = await self._get_fallback_message(failed_stage, error_message)
            if fallback_message:
                result.response_message = fallback_message
                result.recovery_used = True
                recovery_success = True
            
        if not recovery_success:
            # Ultimate fallback
            result.response_message = (
                "Olá! Sou Cecília do Kumon Vila A. 😊 "
                "Estamos com uma instabilidade técnica momentânea. "
                "Por favor, entre em contato pelo telefone (51) 99692-1999 "
                "ou tente novamente em alguns minutos."
            )
        
        return await self._finalize_pipeline_result(
            result, 
            {"success": False, "error": error_message, "recovery_attempted": recovery_attempted}
        )
    
    async def _get_fallback_message(self, failed_stage: PipelineStage, error: str) -> str:
        """Get appropriate fallback message based on failed stage"""
        fallback_messages = {
            PipelineStage.PREPROCESSING: (
                "Olá! Sou Cecília do Kumon Vila A. 😊 "
                "Houve um problema no processamento da sua mensagem. "
                "Por favor, reformule sua pergunta ou entre em contato pelo (51) 99692-1999."
            ),
            PipelineStage.BUSINESS_RULES: (
                "Olá! Sou Cecília do Kumon Vila A. 😊 "
                "Para melhor atendê-lo, entre em contato conosco pelo (51) 99692-1999. "
                "Horário: Segunda a Sexta, 9h-12h e 14h-17h."
            ),
            PipelineStage.LANGGRAPH_WORKFLOW: (
                "Olá! Sou Cecília do Kumon Vila A. 😊 "
                "Como posso ajudá-lo hoje? Se preferir, entre em contato pelo (51) 99692-1999."
            ),
            PipelineStage.POSTPROCESSING: (
                "Olá! Estou aqui para ajudá-lo com informações sobre o Kumon Vila A. 😊 "
                "Entre em contato pelo (51) 99692-1999 para mais detalhes."
            )
        }
        
        return fallback_messages.get(failed_stage, "")
    
    async def _finalize_pipeline_result(
        self,
        result: PipelineResult,
        final_stage_result: Dict[str, Any]
    ) -> PipelineResult:
        """Finalize pipeline execution result and update metrics"""
        # Update metrics
        result.metrics.end_time = datetime.now()
        result.metrics.total_duration_ms = (
            (result.metrics.end_time - result.metrics.start_time).total_seconds() * 1000
        )
        
        # Update status if not already set
        if result.status == PipelineStatus.RUNNING:
            result.status = PipelineStatus.COMPLETED if final_stage_result.get("success", False) else PipelineStatus.FAILED
        
        # Calculate cache hit rate for this execution
        total_cache_operations = result.metrics.cache_hits + result.metrics.cache_misses
        if total_cache_operations > 0:
            execution_cache_hit_rate = (result.metrics.cache_hits / total_cache_operations) * 100
        else:
            execution_cache_hit_rate = 0.0
        
        # Update global performance metrics
        await self._update_performance_metrics(result, execution_cache_hit_rate)
        
        # Log completion
        app_logger.info(f"Pipeline execution {result.execution_id} completed", extra={
            "phone_number": result.phone_number,
            "status": result.status.value,
            "duration_ms": result.metrics.total_duration_ms,
            "cache_hit_rate": execution_cache_hit_rate,
            "sla_violated": result.metrics.total_duration_ms > 3000,
            "errors_count": len(result.metrics.errors),
            "circuit_breaker_triggers": result.metrics.circuit_breaker_triggers
        })
        
        return result
    
    async def _update_performance_metrics(self, result: PipelineResult, cache_hit_rate: float):
        """Update global performance metrics"""
        # Update execution counts
        if result.status == PipelineStatus.COMPLETED:
            self.performance_metrics["successful_executions"] += 1
        else:
            self.performance_metrics["failed_executions"] += 1
        
        # Update average execution time
        total_executions = self.performance_metrics["total_executions"]
        current_avg = self.performance_metrics["avg_execution_time_ms"]
        self.performance_metrics["avg_execution_time_ms"] = (
            (current_avg * (total_executions - 1) + result.metrics.total_duration_ms) / total_executions
        )
        
        # Update SLA violations (>3s response time)
        if result.metrics.total_duration_ms > 3000:
            self.performance_metrics["sla_violations"] += 1
        
        # Update cache hit rate (rolling average)
        current_cache_rate = self.performance_metrics["cache_hit_rate"]
        self.performance_metrics["cache_hit_rate"] = (
            (current_cache_rate * 0.9) + (cache_hit_rate * 0.1)
        )
        
        # Update circuit breaker triggers
        self.performance_metrics["circuit_breaker_triggers"] += result.metrics.circuit_breaker_triggers
        
        # Update recovery success rate
        if result.metrics.recovery_attempts > 0:
            recovery_success = 1 if result.recovery_used else 0
            current_recovery_rate = self.performance_metrics["recovery_success_rate"]
            self.performance_metrics["recovery_success_rate"] = (
                (current_recovery_rate * 0.9) + (recovery_success * 0.1)
            )
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        total_executions = self.performance_metrics["total_executions"]
        if total_executions == 0:
            return self.performance_metrics.copy()
        
        success_rate = (self.performance_metrics["successful_executions"] / total_executions) * 100
        sla_compliance_rate = (
            ((total_executions - self.performance_metrics["sla_violations"]) / total_executions) * 100
        )
        
        # Circuit breaker status
        circuit_breaker_status = {}
        for stage, breaker in self.circuit_breakers.items():
            circuit_breaker_status[stage.value] = {
                "is_open": breaker.is_open,
                "failure_count": breaker.failure_count,
                "last_failure_time": breaker.last_failure_time
            }
        
        return {
            **self.performance_metrics,
            "success_rate_percentage": round(success_rate, 2),
            "sla_compliance_rate_percentage": round(sla_compliance_rate, 2),
            "avg_execution_time_ms": round(self.performance_metrics["avg_execution_time_ms"], 2),
            "cache_hit_rate_percentage": round(self.performance_metrics["cache_hit_rate"], 2),
            "circuit_breaker_status": circuit_breaker_status,
            "active_executions": len(self.active_executions),
            "pipeline_health": "healthy" if success_rate > 95 and sla_compliance_rate > 90 else "degraded"
        }
    
    async def get_active_executions(self) -> List[Dict[str, Any]]:
        """Get currently active pipeline executions"""
        active = []
        for execution_id, result in self.active_executions.items():
            active.append({
                "execution_id": execution_id,
                "phone_number": result.phone_number,
                "status": result.status.value,
                "start_time": result.metrics.start_time.isoformat(),
                "duration_so_far_ms": (
                    (datetime.now() - result.metrics.start_time).total_seconds() * 1000
                ),
                "current_stage": self._get_current_stage(result)
            })
        return active
    
    def _get_current_stage(self, result: PipelineResult) -> str:
        """Determine current stage of pipeline execution"""
        stages = ["preprocessing", "business_rules", "langgraph_workflow", "postprocessing", "delivery"]
        for stage in stages:
            if stage not in result.stage_results:
                return stage
        return "completed"
    
    async def reset_circuit_breakers(self) -> bool:
        """Reset all circuit breakers (admin function)"""
        try:
            for breaker in self.circuit_breakers.values():
                breaker.failure_count = 0
                breaker.is_open = False
                breaker.last_failure_time = None
                await breaker._save_state()
            
            app_logger.info("All circuit breakers reset")
            return True
            
        except Exception as e:
            app_logger.error(f"Failed to reset circuit breakers: {e}")
            return False


# Global pipeline orchestrator instance
pipeline_orchestrator = PipelineOrchestrator()