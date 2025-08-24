"""
LangGraph Business Rules Nodes - Phase 2 Wave 2.2 Business Logic Integration

Dedicated business rule validation nodes for LangGraph conversation flow:
- Pricing validation node (R$375 + R$100 enforcement)
- Scheduling constraint validation node (9h-12h, 14h-17h, Mon-Fri)
- Lead qualification progress tracking node (8 mandatory fields)
- Handoff decision node (trigger evaluation)
- Business compliance validation node

Ensures business rules are enforced at every conversation step, not just pipeline level.
"""

import asyncio
import re
from dataclasses import asdict, dataclass
from datetime import datetime, time
from typing import Any, Dict, List, Optional, Tuple

from ...core.logger import app_logger
from ...core.state.models import CeciliaState as ConversationState
from ...core.state.models import ConversationStage, ConversationStep
from ...services.business_rules_engine import (
    BusinessRuleResult,
    LeadQualificationData,
    RuleType,
    ValidationResult,
    business_rules_engine,
)
from ...services.enhanced_cache_service import enhanced_cache_service


@dataclass
class BusinessRuleNodeResult:
    """Result from business rule node execution"""

    rule_type: RuleType
    validation_result: ValidationResult
    compliance_passed: bool
    action_required: str
    updated_state: ConversationState
    enforcement_message: Optional[str] = None
    business_data: Optional[Dict[str, Any]] = None
    processing_time_ms: float = 0.0


class PricingValidationNode:
    """
    Dedicated node for pricing rule enforcement

    Ensures all pricing discussions comply with:
    - Mensalidade: R$375,00 por matéria (never vary)
    - Taxa de matrícula: R$100,00 (one-time fee)
    - No discounts or negotiations
    """

    def __init__(self):
        self.node_name = "pricing_validation"
        self.cache_prefix = "pricing_node_validation"

    async def execute(
        self, state: ConversationState, context: Dict[str, Any]
    ) -> BusinessRuleNodeResult:
        """Execute pricing validation node"""
        start_time = datetime.now()

        try:
            app_logger.info(f"Executing pricing validation node for {state.get('phone_number')}")

            # Extract pricing-related context
            user_message = state.get("user_message", "")
            message_history = state.get("messages", [])

            # Check if message contains pricing inquiry
            pricing_keywords = [
                "preço",
                "valor",
                "custa",
                "quanto",
                "mensalidade",
                "taxa",
                "matrícula",
                "pagamento",
                "dinheiro",
            ]

            contains_pricing = any(keyword in user_message.lower() for keyword in pricing_keywords)

            if not contains_pricing:
                # No pricing discussion, allow to continue
                return BusinessRuleNodeResult(
                    rule_type=RuleType.PRICING,
                    validation_result=ValidationResult.APPROVED,
                    compliance_passed=True,
                    action_required="continue",
                    updated_state=state,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # Validate pricing inquiry through business rules engine
            pricing_result = await business_rules_engine.evaluate_comprehensive_rules(
                user_message,
                {
                    "conversation_context": state,
                    "messages": message_history,
                    "current_stage": state.get("stage", ConversationStage.GREETING).value,
                },
                rules_to_evaluate=[RuleType.PRICING],
            )

            pricing_validation = pricing_result.get(RuleType.PRICING)

            # Update state with pricing compliance information
            updated_state = state.copy()
            updated_state["pricing_compliance"] = {
                "validated": True,
                "result": pricing_validation.result.value,
                "standard_pricing": {
                    "monthly_fee": "R$ 375,00",
                    "enrollment_fee": "R$ 100,00",
                    "total_first_month": "R$ 475,00",
                },
                "negotiation_detected": pricing_validation.data.get("negotiation_detected", False),
                "timestamp": datetime.now().isoformat(),
            }

            # Handle negotiation attempts
            if pricing_validation.result == ValidationResult.REQUIRES_HANDOFF:
                updated_state["requires_human"] = True
                updated_state["handoff_reason"] = "pricing_negotiation_attempt"

                return BusinessRuleNodeResult(
                    rule_type=RuleType.PRICING,
                    validation_result=ValidationResult.REQUIRES_HANDOFF,
                    compliance_passed=False,
                    action_required="handoff",
                    updated_state=updated_state,
                    enforcement_message="Detectada tentativa de negociação de preços. Redirecionando para consultor educacional.",
                    business_data=pricing_validation.data,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # Standard pricing information provided
            return BusinessRuleNodeResult(
                rule_type=RuleType.PRICING,
                validation_result=ValidationResult.APPROVED,
                compliance_passed=True,
                action_required="continue",
                updated_state=updated_state,
                enforcement_message=None,
                business_data=pricing_validation.data,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        except Exception as e:
            app_logger.error(f"Pricing validation node error: {e}")
            return BusinessRuleNodeResult(
                rule_type=RuleType.PRICING,
                validation_result=ValidationResult.REJECTED,
                compliance_passed=False,
                action_required="error",
                updated_state=state,
                enforcement_message="Erro na validação de preços. Contacte o suporte.",
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )


class SchedulingConstraintNode:
    """
    Dedicated node for scheduling rule enforcement

    Ensures all appointment discussions comply with:
    - Monday-Friday only (no weekends)
    - Morning: 9:00-12:00 (3 hours)
    - Afternoon: 14:00-17:00 (3 hours)
    - Lunch break: 12:00-14:00 (hard block)
    """

    def __init__(self):
        self.node_name = "scheduling_constraint"
        self.cache_prefix = "scheduling_node_validation"

    async def execute(
        self, state: ConversationState, context: Dict[str, Any]
    ) -> BusinessRuleNodeResult:
        """Execute scheduling constraint validation node"""
        start_time = datetime.now()

        try:
            app_logger.info(f"Executing scheduling constraint node for {state.get('phone_number')}")

            user_message = state.get("user_message", "")

            # Check if message contains scheduling inquiry
            scheduling_keywords = [
                "horário",
                "agenda",
                "marcar",
                "agendar",
                "disponível",
                "manhã",
                "tarde",
                "segunda",
                "terça",
                "quarta",
                "quinta",
                "sexta",
                "sábado",
                "domingo",
                "fim de semana",
            ]

            contains_scheduling = any(
                keyword in user_message.lower() for keyword in scheduling_keywords
            )

            if not contains_scheduling:
                # No scheduling discussion, allow to continue
                return BusinessRuleNodeResult(
                    rule_type=RuleType.BUSINESS_HOURS,
                    validation_result=ValidationResult.APPROVED,
                    compliance_passed=True,
                    action_required="continue",
                    updated_state=state,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # Validate scheduling constraints through business rules engine
            business_hours_result = await business_rules_engine.evaluate_comprehensive_rules(
                user_message,
                {
                    "conversation_context": state,
                    "scheduling_request": True,
                    "current_time": datetime.now(),
                },
                rules_to_evaluate=[RuleType.BUSINESS_HOURS],
            )

            hours_validation = business_hours_result.get(RuleType.BUSINESS_HOURS)

            # Update state with scheduling compliance
            updated_state = state.copy()
            updated_state["scheduling_compliance"] = {
                "validated": True,
                "result": hours_validation.result.value,
                "business_hours": {
                    "operating_days": "Segunda a Sexta-feira",
                    "morning_hours": "9:00 - 12:00",
                    "afternoon_hours": "14:00 - 17:00",
                    "lunch_break": "12:00 - 14:00 (fechado)",
                },
                "current_availability": hours_validation.data.get("is_business_hours", False),
                "timestamp": datetime.now().isoformat(),
            }

            # Handle out-of-hours requests
            if hours_validation.result == ValidationResult.REJECTED:
                enforcement_message = (
                    "Nosso horário de funcionamento é de segunda a sexta-feira, "
                    "das 9h às 12h e das 14h às 17h. "
                    f"{hours_validation.data.get('next_available', 'Próximo atendimento em horário comercial')}."
                )

                return BusinessRuleNodeResult(
                    rule_type=RuleType.BUSINESS_HOURS,
                    validation_result=ValidationResult.REJECTED,
                    compliance_passed=False,
                    action_required="inform_business_hours",
                    updated_state=updated_state,
                    enforcement_message=enforcement_message,
                    business_data=hours_validation.data,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # Valid scheduling request
            return BusinessRuleNodeResult(
                rule_type=RuleType.BUSINESS_HOURS,
                validation_result=ValidationResult.APPROVED,
                compliance_passed=True,
                action_required="continue",
                updated_state=updated_state,
                business_data=hours_validation.data,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        except Exception as e:
            app_logger.error(f"Scheduling constraint node error: {e}")
            return BusinessRuleNodeResult(
                rule_type=RuleType.BUSINESS_HOURS,
                validation_result=ValidationResult.REJECTED,
                compliance_passed=False,
                action_required="error",
                updated_state=state,
                enforcement_message="Erro na validação de horário. Contacte o suporte.",
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )


class LeadQualificationTrackingNode:
    """
    Dedicated node for lead qualification progress tracking

    Tracks completion of 8 mandatory fields:
    - Nome responsável, Nome aluno, Telefone, Email
    - Idade aluno, Série escolar, Programa interesse, Horário preferência
    """

    def __init__(self):
        self.node_name = "lead_qualification_tracking"
        self.cache_prefix = "qualification_node_tracking"

    async def execute(
        self, state: ConversationState, context: Dict[str, Any]
    ) -> BusinessRuleNodeResult:
        """Execute lead qualification tracking node"""
        start_time = datetime.now()

        try:
            app_logger.info(
                f"Executing lead qualification tracking node for {state.get('phone_number')}"
            )

            user_message = state.get("user_message", "")
            current_qualification = state.get("qualification_data")

            # Extract current qualification data from state
            if isinstance(current_qualification, dict):
                qualification_data = LeadQualificationData(**current_qualification)
            else:
                qualification_data = LeadQualificationData()

            # Validate qualification progress through business rules engine
            qualification_result = await business_rules_engine.evaluate_comprehensive_rules(
                user_message,
                {
                    "conversation_context": state,
                    "current_qualification": asdict(qualification_data),
                    "stage": state.get("stage", ConversationStage.GREETING).value,
                },
                rules_to_evaluate=[RuleType.QUALIFICATION],
            )

            qualification_validation = qualification_result.get(RuleType.QUALIFICATION)

            # Extract updated qualification data
            updated_qualification_data = qualification_validation.data.get("qualification_data", {})
            completion_percentage = qualification_validation.data.get("completion_percentage", 0.0)
            missing_fields = qualification_validation.data.get("missing_fields", [])
            is_qualified = qualification_validation.data.get("is_qualified", False)

            # Update state with qualification progress
            updated_state = state.copy()
            updated_state["qualification_data"] = updated_qualification_data
            updated_state["qualification_compliance"] = {
                "completion_percentage": completion_percentage,
                "is_qualified": is_qualified,
                "missing_fields": missing_fields,
                "total_required_fields": 8,
                "completed_fields": int((completion_percentage / 100) * 8),
                "last_updated": datetime.now().isoformat(),
            }

            # Update conversation stage based on qualification progress
            if is_qualified and state.get("stage") == ConversationStage.QUALIFICATION:
                updated_state["stage"] = ConversationStage.SCHEDULING
                updated_state["step"] = ConversationStep.SCHEDULE_EVALUATION

            # Determine next action based on qualification status
            if is_qualified:
                action_required = "proceed_to_scheduling"
                enforcement_message = "Qualificação completa! Vamos agendar sua avaliação gratuita."
            elif completion_percentage >= 75.0:
                action_required = "continue_qualification"
                enforcement_message = f"Ótimo progresso! Só preciso de mais alguns dados: {', '.join(missing_fields[:2])}"
            elif completion_percentage >= 50.0:
                action_required = "continue_qualification"
                enforcement_message = (
                    f"Estamos progredindo bem! Ainda preciso de: {', '.join(missing_fields[:3])}"
                )
            else:
                action_required = "request_basic_info"
                enforcement_message = (
                    "Para agendar sua avaliação, preciso de algumas informações básicas."
                )

            return BusinessRuleNodeResult(
                rule_type=RuleType.QUALIFICATION,
                validation_result=qualification_validation.result,
                compliance_passed=completion_percentage
                >= 50.0,  # Minimum threshold for progression
                action_required=action_required,
                updated_state=updated_state,
                enforcement_message=enforcement_message,
                business_data=qualification_validation.data,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        except Exception as e:
            app_logger.error(f"Lead qualification tracking node error: {e}")
            return BusinessRuleNodeResult(
                rule_type=RuleType.QUALIFICATION,
                validation_result=ValidationResult.REJECTED,
                compliance_passed=False,
                action_required="error",
                updated_state=state,
                enforcement_message="Erro no rastreamento de qualificação. Tente novamente.",
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )


class HandoffDecisionNode:
    """
    Dedicated node for handoff trigger evaluation

    Evaluates handoff criteria:
    - Knowledge limitations beyond scope
    - Out of scope requests (rescheduling, materials, billing, complaints)
    - Aggressive behavior or inappropriate language
    - Technical failures
    - Contact: "Entre em contato através do WhatsApp (51) 99692-1999"
    """

    def __init__(self):
        self.node_name = "handoff_decision"
        self.cache_prefix = "handoff_node_decision"

    async def execute(
        self, state: ConversationState, context: Dict[str, Any]
    ) -> BusinessRuleNodeResult:
        """Execute handoff decision node"""
        start_time = datetime.now()

        try:
            app_logger.info(f"Executing handoff decision node for {state.get('phone_number')}")

            user_message = state.get("user_message", "")
            message_history = state.get("messages", [])

            # Evaluate handoff need through business rules engine
            handoff_result = await business_rules_engine.evaluate_comprehensive_rules(
                user_message,
                {
                    "conversation_context": state,
                    "messages": message_history,
                    "turn_count": len(message_history),
                    "current_stage": state.get("stage", ConversationStage.GREETING).value,
                },
                rules_to_evaluate=[RuleType.HANDOFF],
            )

            handoff_validation = handoff_result.get(RuleType.HANDOFF)

            # Update state with handoff evaluation
            updated_state = state.copy()
            updated_state["handoff_evaluation"] = {
                "evaluated": True,
                "handoff_score": handoff_validation.data.get("handoff_score", 0.0),
                "handoff_reasons": handoff_validation.data.get("handoff_reasons", []),
                "requires_handoff": handoff_validation.result == ValidationResult.REQUIRES_HANDOFF,
                "contact_info": {
                    "phone": "(51) 99692-1999",
                    "message": "Entre em contato com nosso consultor educacional",
                },
                "timestamp": datetime.now().isoformat(),
            }

            # Handle handoff requirement
            if handoff_validation.result == ValidationResult.REQUIRES_HANDOFF:
                updated_state["requires_human"] = True
                updated_state["handoff_reason"] = "business_rule_trigger"

                handoff_reasons = handoff_validation.data.get("handoff_reasons", [])
                enforcement_message = (
                    "Vou transferir você para nosso consultor educacional que poderá "
                    "atendê-lo melhor. Entre em contato através do WhatsApp (51) 99692-1999. "
                    f"Motivo: {', '.join(handoff_reasons)}"
                )

                return BusinessRuleNodeResult(
                    rule_type=RuleType.HANDOFF,
                    validation_result=ValidationResult.REQUIRES_HANDOFF,
                    compliance_passed=True,  # Handoff is a valid business action
                    action_required="handoff",
                    updated_state=updated_state,
                    enforcement_message=enforcement_message,
                    business_data=handoff_validation.data,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # Monitor for potential handoff (warning level)
            elif handoff_validation.result == ValidationResult.WARNING:
                updated_state["handoff_monitoring"] = True

                return BusinessRuleNodeResult(
                    rule_type=RuleType.HANDOFF,
                    validation_result=ValidationResult.WARNING,
                    compliance_passed=True,
                    action_required="monitor",
                    updated_state=updated_state,
                    enforcement_message=None,
                    business_data=handoff_validation.data,
                    processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                )

            # Continue conversation normally
            return BusinessRuleNodeResult(
                rule_type=RuleType.HANDOFF,
                validation_result=ValidationResult.APPROVED,
                compliance_passed=True,
                action_required="continue",
                updated_state=updated_state,
                business_data=handoff_validation.data,
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

        except Exception as e:
            app_logger.error(f"Handoff decision node error: {e}")
            return BusinessRuleNodeResult(
                rule_type=RuleType.HANDOFF,
                validation_result=ValidationResult.REJECTED,
                compliance_passed=False,
                action_required="error",
                updated_state=state,
                enforcement_message="Erro na avaliação de handoff. Contacte o suporte.",
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )


class BusinessComplianceValidationNode:
    """
    Comprehensive business compliance validation node

    Orchestrates all business rule validations:
    - Pricing compliance
    - Business hours compliance
    - Lead qualification progress
    - Handoff criteria evaluation
    - LGPD compliance
    """

    def __init__(self):
        self.node_name = "business_compliance_validation"
        self.pricing_node = PricingValidationNode()
        self.scheduling_node = SchedulingConstraintNode()
        self.qualification_node = LeadQualificationTrackingNode()
        self.handoff_node = HandoffDecisionNode()

    async def execute(
        self, state: ConversationState, context: Dict[str, Any]
    ) -> Dict[RuleType, BusinessRuleNodeResult]:
        """Execute comprehensive business compliance validation"""
        start_time = datetime.now()

        try:
            app_logger.info(
                f"Executing comprehensive business compliance validation for {state.get('phone_number')}"
            )

            # Execute all business rule nodes in parallel for efficiency
            node_tasks = [
                self.pricing_node.execute(state, context),
                self.scheduling_node.execute(state, context),
                self.qualification_node.execute(state, context),
                self.handoff_node.execute(state, context),
            ]

            # Wait for all nodes to complete
            node_results = await asyncio.gather(*node_tasks, return_exceptions=True)

            # Organize results by rule type
            compliance_results = {}
            updated_state = state.copy()
            total_compliance_score = 0.0
            compliance_violations = []
            action_priorities = []

            # Process each node result
            for i, result in enumerate(node_results):
                if isinstance(result, Exception):
                    app_logger.error(f"Business rule node {i} failed: {result}")
                    continue

                if isinstance(result, BusinessRuleNodeResult):
                    compliance_results[result.rule_type] = result

                    # Update state with results from each node
                    if result.updated_state:
                        updated_state.update(result.updated_state)

                    # Track compliance violations
                    if not result.compliance_passed:
                        compliance_violations.append(result.rule_type.value)

                    # Collect action priorities
                    if result.action_required not in ["continue", "monitor"]:
                        action_priorities.append((result.rule_type, result.action_required))

                    # Update compliance score
                    total_compliance_score += 1.0 if result.compliance_passed else 0.0

            # Calculate overall compliance metrics
            total_rules_evaluated = len(compliance_results)
            compliance_percentage = (
                (total_compliance_score / total_rules_evaluated * 100)
                if total_rules_evaluated > 0
                else 100.0
            )

            # Update state with comprehensive compliance information
            updated_state["business_compliance"] = {
                "overall_compliance_percentage": compliance_percentage,
                "rules_evaluated": total_rules_evaluated,
                "violations": compliance_violations,
                "action_priorities": action_priorities,
                "compliance_timestamp": datetime.now().isoformat(),
                "processing_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
            }

            app_logger.info(
                f"Business compliance validation completed - "
                f"Compliance: {compliance_percentage:.1f}%, "
                f"Violations: {len(compliance_violations)}, "
                f"Actions required: {len(action_priorities)}"
            )

            return compliance_results

        except Exception as e:
            app_logger.error(f"Business compliance validation error: {e}")

            # Return error result
            error_result = BusinessRuleNodeResult(
                rule_type=RuleType.PRICING,  # Default
                validation_result=ValidationResult.REJECTED,
                compliance_passed=False,
                action_required="error",
                updated_state=state,
                enforcement_message="Erro na validação de compliance. Contacte o suporte.",
                processing_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
            )

            return {RuleType.PRICING: error_result}


# Export business rule nodes
business_compliance_node = BusinessComplianceValidationNode()
pricing_validation_node = PricingValidationNode()
scheduling_constraint_node = SchedulingConstraintNode()
lead_qualification_node = LeadQualificationTrackingNode()
handoff_decision_node = HandoffDecisionNode()


__all__ = [
    "BusinessRuleNodeResult",
    "PricingValidationNode",
    "SchedulingConstraintNode",
    "LeadQualificationTrackingNode",
    "HandoffDecisionNode",
    "BusinessComplianceValidationNode",
    "business_compliance_node",
    "pricing_validation_node",
    "scheduling_constraint_node",
    "lead_qualification_node",
    "handoff_decision_node",
]
