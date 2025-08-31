"""
Conversation State Compliance - Phase 2 Wave 2.2 Business Logic Integration

Enhanced conversation state management with business rule compliance tracking:
- Business rule compliance tracking in conversation state
- Lead qualification progress tracking (8 fields)
- Pricing discussions accuracy monitoring
- Handoff trigger evaluation recording
- Compliance audit trail maintenance
- Integration with CeciliaState for seamless workflow

Extends existing state management with business compliance data structures.
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum

from ...core.state.models import CeciliaState, ConversationStage, ConversationStep
from ...services.business_rules_engine import RuleType, ValidationResult, LeadQualificationData
from ...services.business_compliance_monitor import ComplianceLevel, ComplianceCategory


@dataclass
class BusinessRuleComplianceState:
    """Business rule compliance state within conversation"""
    
    # Overall compliance status
    overall_compliance_level: ComplianceLevel = ComplianceLevel.COMPLIANT
    compliance_score: float = 100.0
    last_compliance_check: Optional[datetime] = None
    
    # Rule-specific compliance tracking
    pricing_compliance: Dict[str, Any] = field(default_factory=lambda: {
        "validated": False,
        "result": ValidationResult.APPROVED.value,
        "standard_pricing": {
            "monthly_fee": "R$ 375,00",
            "enrollment_fee": "R$ 100,00",
            "total_first_month": "R$ 475,00"
        },
        "negotiation_detected": False,
        "violations": [],
        "timestamp": None
    })
    
    qualification_compliance: Dict[str, Any] = field(default_factory=lambda: {
        "completion_percentage": 0.0,
        "is_qualified": False,
        "missing_fields": [
            "Nome do responsável", "Nome do aluno", "Telefone", "Email",
            "Idade do aluno", "Série/Ano escolar", "Programa de interesse", "Horário de preferência"
        ],
        "total_required_fields": 8,
        "completed_fields": 0,
        "last_updated": None,
        "qualification_data": None
    })
    
    scheduling_compliance: Dict[str, Any] = field(default_factory=lambda: {
        "validated": False,
        "result": ValidationResult.APPROVED.value,
        "business_hours": {
            "operating_days": "Segunda a Sexta-feira",
            "morning_hours": "9:00 - 12:00",
            "afternoon_hours": "14:00 - 17:00",
            "lunch_break": "12:00 - 14:00 (fechado)"
        },
        "current_availability": True,
        "violations": [],
        "timestamp": None
    })
    
    handoff_evaluation: Dict[str, Any] = field(default_factory=lambda: {
        "evaluated": False,
        "handoff_score": 0.0,
        "handoff_reasons": [],
        "requires_handoff": False,
        "contact_info": {
            "phone": "(51) 99692-1999",
            "message": "Entre em contato com nosso consultor educacional"
        },
        "monitoring_active": False,
        "timestamp": None
    })
    
    rag_compliance: Dict[str, Any] = field(default_factory=lambda: {
        "validated": False,
        "business_corrections": [],
        "accuracy_score": 1.0,
        "corrections_made": [],
        "last_validation": None
    })
    
    # Compliance history and audit trail
    compliance_history: List[Dict[str, Any]] = field(default_factory=list)
    violation_history: List[Dict[str, Any]] = field(default_factory=list)
    warning_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class QualificationProgressState:
    """Lead qualification progress tracking state"""
    
    # Current qualification data
    qualification_data: Optional[LeadQualificationData] = None
    
    # Progress tracking
    completion_percentage: float = 0.0
    completed_fields_count: int = 0
    missing_fields: List[str] = field(default_factory=lambda: [
        "Nome do responsável", "Nome do aluno", "Telefone", "Email",
        "Idade do aluno", "Série/Ano escolar", "Programa de interesse", "Horário de preferência"
    ])
    
    # Progress milestones
    milestone_25_reached: bool = False
    milestone_50_reached: bool = False
    milestone_75_reached: bool = False
    milestone_100_reached: bool = False
    
    # Progress tracking metadata
    first_info_collected: Optional[datetime] = None
    last_update: Optional[datetime] = None
    qualification_start_time: Optional[datetime] = None
    qualification_complete_time: Optional[datetime] = None
    
    # Field collection history
    field_collection_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def update_progress(self, new_data: LeadQualificationData):
        """Update qualification progress with new data"""
        
        try:
            # Update qualification data
            old_completion = self.completion_percentage
            self.qualification_data = new_data
            self.completion_percentage = new_data.completion_percentage
            self.completed_fields_count = int((self.completion_percentage / 100) * 8)
            self.missing_fields = new_data.missing_fields
            
            # Track milestones
            if self.completion_percentage >= 25 and not self.milestone_25_reached:
                self.milestone_25_reached = True
            if self.completion_percentage >= 50 and not self.milestone_50_reached:
                self.milestone_50_reached = True
            if self.completion_percentage >= 75 and not self.milestone_75_reached:
                self.milestone_75_reached = True
            if self.completion_percentage >= 100 and not self.milestone_100_reached:
                self.milestone_100_reached = True
                self.qualification_complete_time = datetime.now()
            
            # Update timestamps
            if self.first_info_collected is None and self.completion_percentage > 0:
                self.first_info_collected = datetime.now()
                self.qualification_start_time = datetime.now()
            
            self.last_update = datetime.now()
            
            # Track field collection history
            if self.completion_percentage != old_completion:
                self.field_collection_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "completion_change": self.completion_percentage - old_completion,
                    "new_completion": self.completion_percentage,
                    "fields_added": max(0, self.completed_fields_count - int((old_completion / 100) * 8))
                })
            
        except Exception as e:
            # Log error but don't fail
            pass
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """Get progress summary for reporting"""
        
        duration_minutes = 0
        if self.qualification_start_time:
            end_time = self.qualification_complete_time or datetime.now()
            duration_minutes = (end_time - self.qualification_start_time).total_seconds() / 60
        
        return {
            "completion_percentage": self.completion_percentage,
            "completed_fields": self.completed_fields_count,
            "missing_fields": self.missing_fields,
            "milestones_reached": {
                "25%": self.milestone_25_reached,
                "50%": self.milestone_50_reached,
                "75%": self.milestone_75_reached,
                "100%": self.milestone_100_reached
            },
            "duration_minutes": duration_minutes,
            "is_complete": self.completion_percentage >= 100,
            "collection_velocity": len(self.field_collection_history),
            "last_activity": self.last_update.isoformat() if self.last_update else None
        }


@dataclass
class PricingDiscussionState:
    """Pricing discussion tracking state"""
    
    # Pricing discussion status
    pricing_discussed: bool = False
    pricing_accuracy_validated: bool = False
    standard_pricing_provided: bool = False
    
    # Negotiation detection
    negotiation_attempts: List[Dict[str, Any]] = field(default_factory=list)
    negotiation_detected: bool = False
    negotiation_count: int = 0
    
    # Pricing accuracy tracking
    pricing_violations: List[Dict[str, Any]] = field(default_factory=list)
    incorrect_prices_mentioned: List[str] = field(default_factory=list)
    
    # Standard pricing state
    standard_pricing_info: Dict[str, str] = field(default_factory=lambda: {
        "monthly_fee": "R$ 375,00",
        "enrollment_fee": "R$ 100,00",
        "total_first_month": "R$ 475,00",
        "currency": "BRL",
        "policy": "Valores fixos, sem negociação"
    })
    
    # Discussion history
    pricing_discussion_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def record_pricing_discussion(self, message: str, accuracy_validated: bool = True):
        """Record pricing discussion in conversation"""
        
        self.pricing_discussed = True
        self.pricing_accuracy_validated = accuracy_validated
        
        discussion_record = {
            "timestamp": datetime.now().isoformat(),
            "message": message[:200],  # Truncate for privacy
            "accuracy_validated": accuracy_validated,
            "standard_pricing_mentioned": any(
                price in message for price in ["R$ 375", "R$ 100", "R$ 475"]
            )
        }
        
        self.pricing_discussion_history.append(discussion_record)
        
        # Update standard pricing provided flag
        if discussion_record["standard_pricing_mentioned"]:
            self.standard_pricing_provided = True
    
    def record_negotiation_attempt(self, message: str, negotiation_keywords: List[str]):
        """Record negotiation attempt"""
        
        self.negotiation_detected = True
        self.negotiation_count += 1
        
        negotiation_record = {
            "timestamp": datetime.now().isoformat(),
            "message": message[:200],  # Truncate for privacy
            "keywords_detected": negotiation_keywords,
            "attempt_number": self.negotiation_count
        }
        
        self.negotiation_attempts.append(negotiation_record)
    
    def get_pricing_summary(self) -> Dict[str, Any]:
        """Get pricing discussion summary"""
        
        return {
            "pricing_discussed": self.pricing_discussed,
            "standard_pricing_provided": self.standard_pricing_provided,
            "negotiation_attempts": self.negotiation_count,
            "pricing_accuracy_validated": self.pricing_accuracy_validated,
            "violations_count": len(self.pricing_violations),
            "discussion_turns": len(self.pricing_discussion_history),
            "compliance_status": "compliant" if self.pricing_accuracy_validated and not self.pricing_violations else "violation"
        }


@dataclass
class HandoffTrackingState:
    """Handoff tracking and evaluation state"""
    
    # Handoff status
    handoff_evaluated: bool = False
    handoff_required: bool = False
    handoff_executed: bool = False
    
    # Handoff scoring
    current_handoff_score: float = 0.0
    handoff_threshold: float = 0.7
    monitoring_active: bool = False
    
    # Handoff triggers and reasons
    handoff_triggers: List[str] = field(default_factory=list)
    handoff_reasons: List[str] = field(default_factory=list)
    
    # Handoff history
    handoff_evaluations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Contact information
    handoff_contact_info: Dict[str, str] = field(default_factory=lambda: {
        "phone": "(51) 99692-1999",
        "message": "Entre em contato com nosso consultor educacional",
        "availability": "Segunda a Sexta: 9h-12h, 14h-17h"
    })
    
    def update_handoff_evaluation(
        self, 
        handoff_score: float, 
        reasons: List[str], 
        requires_handoff: bool
    ):
        """Update handoff evaluation"""
        
        self.handoff_evaluated = True
        self.current_handoff_score = handoff_score
        self.handoff_required = requires_handoff
        self.handoff_reasons = reasons
        
        # Determine monitoring status
        self.monitoring_active = (handoff_score >= 0.4 and handoff_score < self.handoff_threshold)
        
        # Record evaluation
        evaluation_record = {
            "timestamp": datetime.now().isoformat(),
            "handoff_score": handoff_score,
            "threshold": self.handoff_threshold,
            "reasons": reasons,
            "requires_handoff": requires_handoff,
            "monitoring_active": self.monitoring_active
        }
        
        self.handoff_evaluations.append(evaluation_record)
    
    def execute_handoff(self, handoff_reason: str):
        """Mark handoff as executed"""
        
        self.handoff_executed = True
        self.handoff_triggers.append(f"Executed: {handoff_reason}")
    
    def get_handoff_summary(self) -> Dict[str, Any]:
        """Get handoff tracking summary"""
        
        return {
            "handoff_required": self.handoff_required,
            "handoff_executed": self.handoff_executed,
            "current_score": self.current_handoff_score,
            "threshold": self.handoff_threshold,
            "monitoring_active": self.monitoring_active,
            "evaluation_count": len(self.handoff_evaluations),
            "reasons": self.handoff_reasons,
            "contact_available": bool(self.handoff_contact_info.get("phone"))
        }


def enhance_cecilia_state_with_compliance(state: CeciliaState) -> CeciliaState:
    """
    Enhance existing CeciliaState with business compliance tracking
    
    Args:
        state: Existing CeciliaState instance
        
    Returns:
        Enhanced state with business compliance data
    """
    
    try:
        # Add business compliance state if not present
        if not hasattr(state, 'business_compliance') or state.get('business_compliance') is None:
            state['business_compliance'] = asdict(BusinessRuleComplianceState())
        
        # Add qualification progress state if not present
        if not hasattr(state, 'qualification_progress') or state.get('qualification_progress') is None:
            state['qualification_progress'] = asdict(QualificationProgressState())
        
        # Add pricing discussion state if not present
        if not hasattr(state, 'pricing_discussion') or state.get('pricing_discussion') is None:
            state['pricing_discussion'] = asdict(PricingDiscussionState())
        
        # Add handoff tracking state if not present
        if not hasattr(state, 'handoff_tracking') or state.get('handoff_tracking') is None:
            state['handoff_tracking'] = asdict(HandoffTrackingState())
        
        return state
        
    except Exception as e:
        # Return original state if enhancement fails
        return state


def update_compliance_state(
    state: CeciliaState,
    business_rule_results: Dict[RuleType, Any]
) -> CeciliaState:
    """
    Update conversation state with business rule compliance results
    
    Args:
        state: Current conversation state
        business_rule_results: Results from business rule validation
        
    Returns:
        Updated state with compliance information
    """
    
    try:
        # Ensure compliance structures exist
        state = enhance_cecilia_state_with_compliance(state)
        
        # Update compliance timestamp
        current_time = datetime.now()
        state['business_compliance']['last_compliance_check'] = current_time.isoformat()
        
        # Update rule-specific compliance
        overall_compliance_levels = []
        
        # Process pricing compliance
        if RuleType.PRICING in business_rule_results:
            pricing_result = business_rule_results[RuleType.PRICING]
            if hasattr(pricing_result, 'result') and hasattr(pricing_result, 'data'):
                state['business_compliance']['pricing_compliance'].update({
                    "validated": True,
                    "result": pricing_result.result.value,
                    "negotiation_detected": pricing_result.data.get("negotiation_detected", False),
                    "timestamp": current_time.isoformat()
                })
                
                # Update pricing discussion state
                if pricing_result.data.get("negotiation_detected"):
                    pricing_state = PricingDiscussionState(**state.get('pricing_discussion', {}))
                    pricing_state.record_negotiation_attempt(
                        state.get('user_message', ''),
                        ["pricing_negotiation"]
                    )
                    state['pricing_discussion'] = asdict(pricing_state)
                
                # Determine compliance level
                if pricing_result.result == ValidationResult.APPROVED:
                    overall_compliance_levels.append(ComplianceLevel.COMPLIANT)
                elif pricing_result.result == ValidationResult.WARNING:
                    overall_compliance_levels.append(ComplianceLevel.WARNING)
                else:
                    overall_compliance_levels.append(ComplianceLevel.VIOLATION)
        
        # Process qualification compliance
        if RuleType.QUALIFICATION in business_rule_results:
            qualification_result = business_rule_results[RuleType.QUALIFICATION]
            if hasattr(qualification_result, 'data'):
                qualification_data = qualification_result.data
                
                state['business_compliance']['qualification_compliance'].update({
                    "completion_percentage": qualification_data.get("completion_percentage", 0.0),
                    "is_qualified": qualification_data.get("is_qualified", False),
                    "missing_fields": qualification_data.get("missing_fields", []),
                    "completed_fields": int((qualification_data.get("completion_percentage", 0.0) / 100) * 8),
                    "last_updated": current_time.isoformat()
                })
                
                # Update qualification progress state
                if qualification_data.get("qualification_data"):
                    progress_state = QualificationProgressState(**state.get('qualification_progress', {}))
                    progress_state.update_progress(
                        LeadQualificationData(**qualification_data["qualification_data"])
                    )
                    state['qualification_progress'] = asdict(progress_state)
                
                # Determine compliance level
                completion = qualification_data.get("completion_percentage", 0.0)
                if completion >= 100:
                    overall_compliance_levels.append(ComplianceLevel.COMPLIANT)
                elif completion >= 50:
                    overall_compliance_levels.append(ComplianceLevel.WARNING)
                else:
                    overall_compliance_levels.append(ComplianceLevel.VIOLATION)
        
        # Process handoff compliance
        if RuleType.HANDOFF in business_rule_results:
            handoff_result = business_rule_results[RuleType.HANDOFF]
            if hasattr(handoff_result, 'data'):
                handoff_data = handoff_result.data
                
                state['business_compliance']['handoff_evaluation'].update({
                    "evaluated": True,
                    "handoff_score": handoff_data.get("handoff_score", 0.0),
                    "handoff_reasons": handoff_data.get("handoff_reasons", []),
                    "requires_handoff": handoff_result.result == ValidationResult.REQUIRES_HANDOFF,
                    "monitoring_active": handoff_result.result == ValidationResult.WARNING,
                    "timestamp": current_time.isoformat()
                })
                
                # Update handoff tracking state
                handoff_state = HandoffTrackingState(**state.get('handoff_tracking', {}))
                handoff_state.update_handoff_evaluation(
                    handoff_data.get("handoff_score", 0.0),
                    handoff_data.get("handoff_reasons", []),
                    handoff_result.result == ValidationResult.REQUIRES_HANDOFF
                )
                state['handoff_tracking'] = asdict(handoff_state)
                
                # Determine compliance level
                if handoff_result.result == ValidationResult.APPROVED:
                    overall_compliance_levels.append(ComplianceLevel.COMPLIANT)
                elif handoff_result.result == ValidationResult.WARNING:
                    overall_compliance_levels.append(ComplianceLevel.WARNING)
                else:
                    overall_compliance_levels.append(ComplianceLevel.VIOLATION)
        
        # Calculate overall compliance level
        if overall_compliance_levels:
            if any(level == ComplianceLevel.CRITICAL_VIOLATION for level in overall_compliance_levels):
                state['business_compliance']['overall_compliance_level'] = ComplianceLevel.CRITICAL_VIOLATION.value
                state['business_compliance']['compliance_score'] = 20.0
            elif any(level == ComplianceLevel.VIOLATION for level in overall_compliance_levels):
                state['business_compliance']['overall_compliance_level'] = ComplianceLevel.VIOLATION.value
                state['business_compliance']['compliance_score'] = 60.0
            elif any(level == ComplianceLevel.WARNING for level in overall_compliance_levels):
                state['business_compliance']['overall_compliance_level'] = ComplianceLevel.WARNING.value
                state['business_compliance']['compliance_score'] = 80.0
            else:
                state['business_compliance']['overall_compliance_level'] = ComplianceLevel.COMPLIANT.value
                state['business_compliance']['compliance_score'] = 100.0
        
        # Add to compliance history
        compliance_record = {
            "timestamp": current_time.isoformat(),
            "overall_level": state['business_compliance']['overall_compliance_level'],
            "compliance_score": state['business_compliance']['compliance_score'],
            "rules_evaluated": list(business_rule_results.keys()),
            "message_context": state.get('user_message', '')[:100]  # Truncate for privacy
        }
        
        state['business_compliance']['compliance_history'].append(compliance_record)
        
        # Maintain history size limit
        if len(state['business_compliance']['compliance_history']) > 50:
            state['business_compliance']['compliance_history'] = state['business_compliance']['compliance_history'][-50:]
        
        return state
        
    except Exception as e:
        # Return original state if update fails
        return state


def get_compliance_summary(state: CeciliaState) -> Dict[str, Any]:
    """
    Get comprehensive compliance summary from conversation state
    
    Args:
        state: Current conversation state with compliance data
        
    Returns:
        Comprehensive compliance summary
    """
    
    try:
        compliance_data = state.get('business_compliance', {})
        qualification_data = state.get('qualification_progress', {})
        pricing_data = state.get('pricing_discussion', {})
        handoff_data = state.get('handoff_tracking', {})
        
        summary = {
            "overall_compliance": {
                "level": compliance_data.get('overall_compliance_level', 'compliant'),
                "score": compliance_data.get('compliance_score', 100.0),
                "last_check": compliance_data.get('last_compliance_check'),
                "total_checks": len(compliance_data.get('compliance_history', []))
            },
            "qualification_progress": {
                "completion_percentage": qualification_data.get('completion_percentage', 0.0),
                "is_complete": qualification_data.get('milestone_100_reached', False),
                "missing_fields_count": len(qualification_data.get('missing_fields', [])),
                "collection_velocity": qualification_data.get('collection_velocity', 0)
            },
            "pricing_compliance": {
                "discussed": pricing_data.get('pricing_discussed', False),
                "standard_provided": pricing_data.get('standard_pricing_provided', False),
                "negotiation_attempts": pricing_data.get('negotiation_count', 0),
                "violations": len(pricing_data.get('pricing_violations', []))
            },
            "handoff_status": {
                "required": handoff_data.get('handoff_required', False),
                "executed": handoff_data.get('handoff_executed', False),
                "current_score": handoff_data.get('current_handoff_score', 0.0),
                "monitoring": handoff_data.get('monitoring_active', False)
            },
            "compliance_trends": {
                "total_violations": len(compliance_data.get('violation_history', [])),
                "total_warnings": len(compliance_data.get('warning_history', [])),
                "compliance_stability": _calculate_compliance_stability(compliance_data.get('compliance_history', []))
            }
        }
        
        return summary
        
    except Exception as e:
        return {"error": str(e)}


def _calculate_compliance_stability(compliance_history: List[Dict[str, Any]]) -> float:
    """Calculate compliance stability score based on history"""
    
    if len(compliance_history) < 2:
        return 100.0
    
    try:
        # Calculate score variance
        scores = [record.get('compliance_score', 100.0) for record in compliance_history[-10:]]
        if len(scores) < 2:
            return 100.0
        
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        stability = max(0, 100 - variance)  # Higher variance = lower stability
        
        return round(stability, 2)
        
    except Exception:
        return 100.0


__all__ = [
    'BusinessRuleComplianceState',
    'QualificationProgressState',
    'PricingDiscussionState',
    'HandoffTrackingState',
    'enhance_cecilia_state_with_compliance',
    'update_compliance_state',
    'get_compliance_summary'
]