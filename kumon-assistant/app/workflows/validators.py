"""
Enhanced Validation Agent with Integrated Security for Kumon Assistant

Implements multi-layer validation with security integration:
- Response quality validation
- Security threat assessment
- Business scope compliance
- Information disclosure prevention
- Real-time threat correlation
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from ..services.langgraph_llm_adapter import kumon_llm_service
from langchain.prompts import ChatPromptTemplate

from ..core.logger import app_logger
from ..core.config import settings
from ..security.security_manager import security_manager
from .states import AgentState
from ..services.business_metrics_service import track_response_time


class ValidationResult(Enum):
    """Validation result outcomes"""
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVISION = "needs_revision"
    SECURITY_BLOCKED = "security_blocked"
    ESCALATE_HUMAN = "escalate_human"


class ValidationLayer(Enum):
    """Validation layers"""
    SECURITY = "security"
    QUALITY = "quality"
    SCOPE = "scope"
    INFORMATION = "information"
    BUSINESS = "business"


@dataclass
class ValidationReport:
    """Comprehensive validation report"""
    overall_result: ValidationResult
    confidence: float
    issues: List[str]
    suggestions: List[str]
    security_assessment: Dict[str, Any]
    quality_score: float
    scope_compliance: bool
    information_safety: bool
    recommended_actions: List[str]
    layer_results: Dict[ValidationLayer, Dict[str, Any]]


class SecurityValidationAgent:
    """
    Enhanced validation agent with integrated security
    
    Provides comprehensive validation including:
    - Multi-layer security screening
    - Quality assurance validation
    - Business scope compliance
    - Information disclosure prevention
    - Threat correlation and learning
    """
    
    def __init__(self):
        # LLM for quality validation using new service abstraction
        self.llm = kumon_llm_service
        
        # Validation thresholds and configuration
        self.thresholds = {
            # Quality thresholds
            "min_confidence": 0.8,
            "min_quality_score": 0.7,
            "max_confusion_count": 3,
            "min_satisfaction": 0.7,
            
            # Security thresholds
            "max_security_score": 0.6,
            "max_violation_severity": 0.7,
            "max_disclosure_risk": 0.5,
            
            # Escalation thresholds
            "validation_attempts_limit": 3,
            "security_incidents_limit": 2,
            "quality_failures_limit": 3
        }
        
        # Validation history for learning
        self.validation_history: Dict[str, List[Dict]] = {}
        
        # Quality metrics tracking
        self.quality_metrics = QualityMetrics()
        
        app_logger.info("Security Validation Agent initialized with multi-layer protection")
    
    async def validate_response(
        self,
        response: str,
        agent_state: AgentState,
        source_identifier: str,
        request_metadata: Optional[Dict[str, Any]] = None
    ) -> ValidationReport:
        """
        Comprehensive response validation with security integration
        
        Args:
            response: The response to validate
            agent_state: Current conversation state
            source_identifier: User identifier
            request_metadata: Additional request context
            
        Returns:
            Comprehensive validation report
        """
        
        app_logger.info(f"Starting multi-layer validation for {source_identifier}")
        start_time = datetime.now()
        
        # Run all validation layers in parallel
        validation_results = await asyncio.gather(
            self._security_validation_layer(response, source_identifier, request_metadata),
            self._quality_validation_layer(response, agent_state),
            self._scope_validation_layer(response, agent_state),
            self._information_safety_layer(response, request_metadata),
            self._business_compliance_layer(response, agent_state),
            return_exceptions=True
        )
        
        # Process layer results
        layer_results = {}
        security_result, quality_result, scope_result, info_result, business_result = validation_results
        
        # Security layer
        if isinstance(security_result, dict):
            layer_results[ValidationLayer.SECURITY] = security_result
        else:
            layer_results[ValidationLayer.SECURITY] = {
                "passed": False,
                "error": str(security_result),
                "confidence": 0.0
            }
        
        # Quality layer
        if isinstance(quality_result, dict):
            layer_results[ValidationLayer.QUALITY] = quality_result
        else:
            layer_results[ValidationLayer.QUALITY] = {
                "passed": False,
                "error": str(quality_result),
                "confidence": 0.0
            }
        
        # Scope layer
        if isinstance(scope_result, dict):
            layer_results[ValidationLayer.SCOPE] = scope_result
        else:
            layer_results[ValidationLayer.SCOPE] = {
                "passed": False,
                "error": str(scope_result),
                "confidence": 0.0
            }
        
        # Information safety layer
        if isinstance(info_result, dict):
            layer_results[ValidationLayer.INFORMATION] = info_result
        else:
            layer_results[ValidationLayer.INFORMATION] = {
                "passed": False,
                "error": str(info_result),
                "confidence": 0.0
            }
        
        # Business compliance layer
        if isinstance(business_result, dict):
            layer_results[ValidationLayer.BUSINESS] = business_result
        else:
            layer_results[ValidationLayer.BUSINESS] = {
                "passed": False,
                "error": str(business_result),
                "confidence": 0.0
            }
        
        # Aggregate validation results
        validation_report = await self._aggregate_validation_results(
            layer_results, agent_state, source_identifier
        )
        
        # Track validation for learning
        await self._track_validation_result(
            source_identifier, validation_report, response
        )
        
        # Track validation performance metrics
        validation_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        await track_response_time(validation_time_ms, {
            "component": "validation_agent",
            "result": validation_report.overall_result.value,
            "confidence": validation_report.confidence,
            "phone_number": source_identifier[-4:] if len(source_identifier) > 4 else "****",
            "layers_processed": len(validation_report.layer_results)
        })
        
        # Log validation result
        app_logger.info(
            f"Validation completed: {validation_report.overall_result.value} "
            f"(confidence: {validation_report.confidence:.2f})"
        )
        
        return validation_report
    
    async def _security_validation_layer(
        self,
        response: str,
        source_identifier: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Security validation using integrated security manager"""
        
        try:
            # Use security manager for comprehensive threat assessment
            security_action, security_context = await security_manager.evaluate_security_threat(
                source_identifier, response, metadata
            )
            
            # Determine if security validation passes
            security_score = security_context.get("security_score", 0.0)
            passed = security_score < self.thresholds["max_security_score"]
            
            issues = []
            if not passed:
                threats = security_context.get("threats_detected", [])
                issues = [f"Security threat: {threat}" for threat in threats]
            
            return {
                "passed": passed,
                "security_score": security_score,
                "security_action": security_action.value,
                "confidence": 0.9,  # High confidence in security system
                "issues": issues,
                "security_context": security_context
            }
            
        except Exception as e:
            app_logger.error(f"Security validation error: {e}")
            # Fail secure - block if security validation fails
            return {
                "passed": False,
                "security_score": 1.0,
                "confidence": 0.0,
                "issues": [f"Security validation failed: {str(e)}"],
                "error": str(e)
            }
    
    async def _quality_validation_layer(
        self,
        response: str,
        agent_state: AgentState
    ) -> Dict[str, Any]:
        """Quality validation using LLM assessment"""
        
        try:
            # Prepare conversation context
            conversation_context = self._format_conversation_context(agent_state)
            current_stage = agent_state.get("stage", "unknown")
            
            # Create validation prompt
            validation_prompt = ChatPromptTemplate.from_messages([
                ("system", """Você é Cecília, a validadora de qualidade para respostas da assistente do Kumon Vila A.
                
                Analise a resposta e verifique se está adequada para uma assistente educacional profissional:
                
                1. INFORMAÇÕES CORRETAS: Horários, endereço, valores, procedimentos do Kumon
                2. TOM APROPRIADO: Profissional mas caloroso, típico de educadora
                3. COMPLETUDE: Responde adequadamente à pergunta do usuário
                4. COERÊNCIA: Consistente com o contexto da conversa
                5. SEGURANÇA: Não revela informações sensíveis ou inadequadas
                6. FOCO EDUCACIONAL: Mantém foco no método Kumon e educação
                
                IMPORTANTE: A assistente é CECÍLIA, nunca deve se identificar como assistente virtual.
                
                Retorne apenas um JSON válido:
                {
                    "is_valid": boolean,
                    "quality_score": float (0.0-1.0),
                    "issues": [lista de problemas específicos],
                    "suggestions": [sugestões de melhoria],
                    "confidence": float (0.0-1.0),
                    "tone_appropriate": boolean,
                    "information_accurate": boolean,
                    "response_complete": boolean
                }"""),
                ("human", """
                Contexto da conversa:
                {conversation_context}
                
                Estágio atual: {current_stage}
                
                Resposta para validar:
                {response}
                """)
            ])
            
            # Get LLM validation
            result = await self.llm.ainvoke(
                validation_prompt.format_messages(
                    conversation_context=conversation_context,
                    current_stage=current_stage,
                    response=response
                )
            )
            
            # Parse JSON result
            try:
                validation_data = json.loads(result.content)
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                validation_data = {
                    "is_valid": False,
                    "quality_score": 0.5,
                    "issues": ["Failed to parse validation result"],
                    "suggestions": ["Review response format"],
                    "confidence": 0.3,
                    "tone_appropriate": True,
                    "information_accurate": True,
                    "response_complete": False
                }
            
            passed = (
                validation_data.get("is_valid", False) and
                validation_data.get("quality_score", 0.0) >= self.thresholds["min_quality_score"]
            )
            
            return {
                "passed": passed,
                "quality_score": validation_data.get("quality_score", 0.0),
                "confidence": validation_data.get("confidence", 0.5),
                "issues": validation_data.get("issues", []),
                "suggestions": validation_data.get("suggestions", []),
                "validation_details": validation_data
            }
            
        except Exception as e:
            app_logger.error(f"Quality validation error: {e}")
            return {
                "passed": False,
                "quality_score": 0.0,
                "confidence": 0.0,
                "issues": [f"Quality validation failed: {str(e)}"],
                "error": str(e)
            }
    
    async def _scope_validation_layer(
        self,
        response: str,
        agent_state: AgentState
    ) -> Dict[str, Any]:
        """Scope validation to ensure business focus"""
        
        try:
            # Use security manager's scope validator
            scope_result = await security_manager.scope_validator.validate_scope(
                response, {"agent_state": agent_state}
            )
            
            passed = scope_result.get("is_valid_scope", True)
            violation_severity = scope_result.get("violation_severity", 0.0)
            
            issues = []
            if not passed:
                violation_type = scope_result.get("violation_type")
                if violation_type:
                    issues.append(f"Scope violation: {violation_type}")
            
            return {
                "passed": passed,
                "scope_compliance": passed,
                "violation_severity": violation_severity,
                "confidence": scope_result.get("violation_confidence", 0.8),
                "issues": issues,
                "scope_details": scope_result
            }
            
        except Exception as e:
            app_logger.error(f"Scope validation error: {e}")
            return {
                "passed": True,  # Default to pass if scope validation fails
                "scope_compliance": True,
                "confidence": 0.3,
                "issues": [f"Scope validation error: {str(e)}"],
                "error": str(e)
            }
    
    async def _information_safety_layer(
        self,
        response: str,
        metadata: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Information disclosure prevention validation"""
        
        try:
            # Use security manager's information protection
            info_result = await security_manager.info_protection.check_information_request(
                response, metadata
            )
            
            is_sensitive = info_result.get("is_sensitive_request", False)
            sensitivity_score = info_result.get("sensitivity_score", 0.0)
            
            passed = not is_sensitive or sensitivity_score < self.thresholds["max_disclosure_risk"]
            
            issues = []
            if not passed:
                disclosure_type = info_result.get("disclosure_type")
                if disclosure_type:
                    issues.append(f"Information disclosure risk: {disclosure_type}")
            
            return {
                "passed": passed,
                "information_safety": passed,
                "sensitivity_score": sensitivity_score,
                "confidence": info_result.get("confidence", 0.8),
                "issues": issues,
                "information_details": info_result
            }
            
        except Exception as e:
            app_logger.error(f"Information safety validation error: {e}")
            return {
                "passed": True,  # Default to pass if validation fails
                "information_safety": True,
                "confidence": 0.3,
                "issues": [f"Information safety error: {str(e)}"],
                "error": str(e)
            }
    
    async def _business_compliance_layer(
        self,
        response: str,
        agent_state: AgentState
    ) -> Dict[str, Any]:
        """Business compliance validation"""
        
        try:
            # Check for Kumon business compliance
            business_keywords = [
                "kumon", "matemática", "português", "método", "orientador",
                "autodidata", "disciplina", "concentração", "vila a"
            ]
            
            response_lower = response.lower()
            business_relevance = sum(
                1 for keyword in business_keywords if keyword in response_lower
            ) / len(business_keywords)
            
            # Check for inappropriate content
            inappropriate_patterns = [
                r'não sei', r'não posso ajudar', r'desculpe', r'não tenho informação'
            ]
            
            has_inappropriate = any(
                __import__('re').search(pattern, response_lower)
                for pattern in inappropriate_patterns
            )
            
            # Business compliance score
            compliance_score = business_relevance
            if has_inappropriate:
                compliance_score *= 0.5  # Penalty for unhelpful responses
            
            passed = compliance_score > 0.3 or len(response) < 100  # Short responses OK
            
            issues = []
            if not passed:
                if business_relevance < 0.1:
                    issues.append("Response lacks business relevance")
                if has_inappropriate:
                    issues.append("Response contains unhelpful language")
            
            return {
                "passed": passed,
                "business_compliance": passed,
                "compliance_score": compliance_score,
                "business_relevance": business_relevance,
                "confidence": 0.7,
                "issues": issues
            }
            
        except Exception as e:
            app_logger.error(f"Business compliance validation error: {e}")
            return {
                "passed": True,
                "business_compliance": True,
                "confidence": 0.3,
                "issues": [f"Business compliance error: {str(e)}"],
                "error": str(e)
            }
    
    async def _aggregate_validation_results(
        self,
        layer_results: Dict[ValidationLayer, Dict[str, Any]],
        agent_state: AgentState,
        source_identifier: str
    ) -> ValidationReport:
        """Aggregate results from all validation layers"""
        
        # Extract results from each layer
        security_passed = layer_results.get(ValidationLayer.SECURITY, {}).get("passed", False)
        quality_passed = layer_results.get(ValidationLayer.QUALITY, {}).get("passed", False)
        scope_passed = layer_results.get(ValidationLayer.SCOPE, {}).get("passed", True)
        info_passed = layer_results.get(ValidationLayer.INFORMATION, {}).get("passed", True)
        business_passed = layer_results.get(ValidationLayer.BUSINESS, {}).get("passed", True)
        
        # Calculate overall confidence
        confidences = []
        for layer_result in layer_results.values():
            if "confidence" in layer_result:
                confidences.append(layer_result["confidence"])
        
        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.5
        
        # Collect all issues and suggestions
        all_issues = []
        all_suggestions = []
        
        for layer_result in layer_results.values():
            all_issues.extend(layer_result.get("issues", []))
            all_suggestions.extend(layer_result.get("suggestions", []))
        
        # Determine overall validation result
        if not security_passed:
            overall_result = ValidationResult.SECURITY_BLOCKED
        elif not any([quality_passed, scope_passed, info_passed, business_passed]):
            overall_result = ValidationResult.REJECTED
        elif not quality_passed and len(all_issues) > 3:
            overall_result = ValidationResult.NEEDS_REVISION
        elif self.quality_metrics.should_escalate(agent_state):
            overall_result = ValidationResult.ESCALATE_HUMAN
        else:
            overall_result = ValidationResult.APPROVED
        
        # Extract specific scores
        security_assessment = layer_results.get(ValidationLayer.SECURITY, {})
        quality_score = layer_results.get(ValidationLayer.QUALITY, {}).get("quality_score", 0.5)
        
        # Generate recommended actions
        recommended_actions = self._generate_recommended_actions(
            overall_result, layer_results, agent_state
        )
        
        return ValidationReport(
            overall_result=overall_result,
            confidence=overall_confidence,
            issues=all_issues,
            suggestions=all_suggestions,
            security_assessment=security_assessment,
            quality_score=quality_score,
            scope_compliance=scope_passed,
            information_safety=info_passed,
            recommended_actions=recommended_actions,
            layer_results=layer_results
        )
    
    def _generate_recommended_actions(
        self,
        overall_result: ValidationResult,
        layer_results: Dict[ValidationLayer, Dict[str, Any]],
        agent_state: AgentState
    ) -> List[str]:
        """Generate recommended actions based on validation results"""
        
        actions = []
        
        if overall_result == ValidationResult.SECURITY_BLOCKED:
            actions.extend([
                "Block response immediately",
                "Log security incident",
                "Review security protocols",
                "Consider source blocking"
            ])
        elif overall_result == ValidationResult.REJECTED:
            actions.extend([
                "Generate new response",
                "Review conversation context", 
                "Check business guidelines",
                "Improve response quality"
            ])
        elif overall_result == ValidationResult.NEEDS_REVISION:
            actions.extend([
                "Revise response based on suggestions",
                "Improve tone and clarity",
                "Add missing information",
                "Verify business accuracy"
            ])
        elif overall_result == ValidationResult.ESCALATE_HUMAN:
            actions.extend([
                "Escalate to human operator",
                "Provide conversation summary",
                "Flag for quality review",
                "Log escalation reasons"
            ])
        
        # Layer-specific actions
        security_result = layer_results.get(ValidationLayer.SECURITY, {})
        if not security_result.get("passed", True):
            actions.append("Apply security measures")
        
        quality_result = layer_results.get(ValidationLayer.QUALITY, {})
        if not quality_result.get("passed", True):
            actions.append("Improve response quality")
        
        return actions
    
    def _format_conversation_context(self, agent_state: AgentState) -> str:
        """Format conversation context for validation"""
        
        messages = agent_state.get("message_history", [])
        if not messages:
            return "Nova conversa iniciada"
        
        # Format recent messages
        formatted = []
        for msg in messages[-5:]:  # Last 5 messages for context
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role}: {content[:100]}...")  # Truncate long messages
        
        return "\n".join(formatted)
    
    async def _track_validation_result(
        self,
        source_identifier: str,
        validation_report: ValidationReport,
        response: str
    ):
        """Track validation results for learning and improvement"""
        
        validation_entry = {
            "timestamp": datetime.now(),
            "result": validation_report.overall_result.value,
            "confidence": validation_report.confidence,
            "quality_score": validation_report.quality_score,
            "issues_count": len(validation_report.issues),
            "response_length": len(response),
            "security_passed": validation_report.layer_results.get(
                ValidationLayer.SECURITY, {}
            ).get("passed", False)
        }
        
        self.validation_history.setdefault(source_identifier, []).append(validation_entry)
        
        # Keep only recent history (last 100 validations)
        if len(self.validation_history[source_identifier]) > 100:
            self.validation_history[source_identifier] = \
                self.validation_history[source_identifier][-100:]
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get comprehensive validation statistics"""
        
        total_validations = sum(
            len(history) for history in self.validation_history.values()
        )
        
        if total_validations == 0:
            return {"status": "no_validations_performed"}
        
        # Aggregate statistics
        result_counts = {}
        avg_confidence = 0.0
        avg_quality = 0.0
        security_pass_rate = 0.0
        
        all_validations = []
        for history in self.validation_history.values():
            all_validations.extend(history)
        
        for validation in all_validations:
            result = validation["result"]
            result_counts[result] = result_counts.get(result, 0) + 1
            avg_confidence += validation["confidence"]
            avg_quality += validation["quality_score"]
            if validation["security_passed"]:
                security_pass_rate += 1
        
        avg_confidence /= total_validations
        avg_quality /= total_validations
        security_pass_rate /= total_validations
        
        return {
            "total_validations": total_validations,
            "unique_sources": len(self.validation_history),
            "result_distribution": result_counts,
            "average_confidence": avg_confidence,
            "average_quality_score": avg_quality,
            "security_pass_rate": security_pass_rate,
            "validation_layers": [layer.value for layer in ValidationLayer],
            "thresholds": self.thresholds
        }


class QualityMetrics:
    """Quality metrics and escalation logic"""
    
    def __init__(self):
        self.thresholds = {
            "min_confidence": 0.8,
            "max_confusion_count": 3,
            "min_satisfaction": 0.7,
            "max_validation_failures": 3,
            "max_security_incidents": 2
        }
    
    def should_escalate(self, state: AgentState) -> bool:
        """Determine if conversation should be escalated to human"""
        
        # Multiple validation failures
        if state.get("validation_attempts", 0) >= self.thresholds["max_validation_failures"]:
            return True
        
        # User confusion detected
        if state.get("confusion_count", 0) >= self.thresholds["max_confusion_count"]:
            return True
        
        # Low satisfaction score
        if state.get("satisfaction_score", 1.0) < self.thresholds["min_satisfaction"]:
            return True
        
        # Security incidents
        if state.get("security_incidents", 0) >= self.thresholds["max_security_incidents"]:
            return True
        
        # Explicit escalation request
        if state.get("needs_human_handoff", False):
            return True
        
        return False
    
    def update_quality_metrics(
        self, 
        state: AgentState, 
        validation_report: ValidationReport
    ) -> AgentState:
        """Update quality metrics in agent state"""
        
        # Update validation attempts
        if validation_report.overall_result in [
            ValidationResult.REJECTED, 
            ValidationResult.NEEDS_REVISION
        ]:
            state["validation_attempts"] = state.get("validation_attempts", 0) + 1
        elif validation_report.overall_result == ValidationResult.APPROVED:
            state["validation_attempts"] = 0  # Reset on success
        
        # Update security incidents
        if validation_report.overall_result == ValidationResult.SECURITY_BLOCKED:
            state["security_incidents"] = state.get("security_incidents", 0) + 1
        
        # Update satisfaction score based on validation quality
        if validation_report.quality_score < 0.5:
            state["satisfaction_score"] = state.get("satisfaction_score", 1.0) * 0.9
        elif validation_report.quality_score > 0.8:
            state["satisfaction_score"] = min(1.0, state.get("satisfaction_score", 1.0) * 1.1)
        
        return state


# Global validation agent instance (lazy initialization)
validation_agent = None

def get_validation_agent() -> SecurityValidationAgent:
    """Get or create the global validation agent instance."""
    global validation_agent
    if validation_agent is None:
        validation_agent = SecurityValidationAgent()
    return validation_agent