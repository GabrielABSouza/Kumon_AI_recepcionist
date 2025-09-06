"""
Stage-Aware Variable Policy System

Implements strict variable access control based on conversation stage and step.
Prevents premature disclosure of personal information and maintains neutral messaging.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Set, Optional, Any

from ...core.logger import app_logger


class VariableCategory(Enum):
    """Categories of template variables by sensitivity"""
    PUBLIC = "public"           # Always safe to use
    PERSONAL = "personal"       # Names, personal identifiers  
    SENSITIVE = "sensitive"     # Age, school info, private details
    CONTEXTUAL = "contextual"   # Conversation context, preferences
    SYSTEM = "system"          # Internal system variables


class ConversationStage(Enum):
    """Conversation stages for variable policy"""
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    INFORMATION = "information"
    SCHEDULING = "scheduling"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"
    FALLBACK = "fallback"


class ConversationStep(Enum):
    """Specific steps within conversation stages"""
    # Greeting steps
    WELCOME = "welcome"
    NAME_COLLECTION = "name_collection"
    INTRODUCTION = "introduction"
    
    # Qualification steps
    TARGET_IDENTIFICATION = "target_identification"
    INTEREST_DISCOVERY = "interest_discovery"
    NEEDS_ASSESSMENT = "needs_assessment"
    
    # Information steps
    PROGRAM_EXPLANATION = "program_explanation"
    METHODOLOGY_DETAIL = "methodology_detail"
    BENEFITS_PRESENTATION = "benefits_presentation"
    
    # Scheduling steps
    AVAILABILITY_CHECK = "availability_check"
    SLOT_SELECTION = "slot_selection"
    BOOKING_CONFIRMATION = "booking_confirmation"


class VariablePolicyEngine:
    """
    Enforces stage-aware variable access policies
    """
    
    def __init__(self):
        self.variables_blocked_count = 0
        self.policy_violations_count = 0
        
        # Variable categorization
        self.variable_categories = {
            # Public variables - always safe
            VariableCategory.PUBLIC: {
                'business_name', 'location', 'programs', 'schedule', 'method_name'
            },
            
            # Personal identifiers
            VariableCategory.PERSONAL: {
                'first_name', 'last_name', 'parent_name', 'child_name', 'full_name'
            },
            
            # Sensitive personal information
            VariableCategory.SENSITIVE: {
                'age', 'school_grade', 'phone_number', 'email', 'address',
                'child_age', 'student_level', 'academic_performance'
            },
            
            # Contextual conversation variables
            VariableCategory.CONTEXTUAL: {
                'interest_area', 'program_preference', 'availability_preference',
                'previous_experience', 'learning_goals', 'concerns'
            },
            
            # System variables (internal use only)
            VariableCategory.SYSTEM: {
                'session_id', 'timestamp', 'conversation_history', 'system_prompt',
                'debug_info', 'internal_state'
            }
        }
        
        # Stage-specific variable policies
        self.stage_policies = self._define_stage_policies()
    
    def _define_stage_policies(self) -> Dict[ConversationStage, Dict[ConversationStep, Set[VariableCategory]]]:
        """Define allowed variable categories by stage and step"""
        
        return {
            ConversationStage.GREETING: {
                ConversationStep.WELCOME: {
                    # Initial greeting: NO personal variables
                    VariableCategory.PUBLIC
                },
                ConversationStep.NAME_COLLECTION: {
                    VariableCategory.PUBLIC
                    # Name collection step still doesn't use collected name
                },
                ConversationStep.INTRODUCTION: {
                    VariableCategory.PUBLIC,
                    VariableCategory.PERSONAL  # Can use name after collection confirmed
                }
            },
            
            ConversationStage.QUALIFICATION: {
                ConversationStep.TARGET_IDENTIFICATION: {
                    VariableCategory.PUBLIC,
                    VariableCategory.PERSONAL
                },
                ConversationStep.INTEREST_DISCOVERY: {
                    VariableCategory.PUBLIC,
                    VariableCategory.PERSONAL,
                    VariableCategory.CONTEXTUAL
                },
                ConversationStep.NEEDS_ASSESSMENT: {
                    VariableCategory.PUBLIC,
                    VariableCategory.PERSONAL,
                    VariableCategory.CONTEXTUAL,
                    VariableCategory.SENSITIVE  # Age, grade after qualification
                }
            },
            
            ConversationStage.INFORMATION: {
                ConversationStep.PROGRAM_EXPLANATION: {
                    VariableCategory.PUBLIC,
                    VariableCategory.PERSONAL,
                    VariableCategory.CONTEXTUAL
                },
                ConversationStep.METHODOLOGY_DETAIL: {
                    VariableCategory.PUBLIC,
                    VariableCategory.PERSONAL,
                    VariableCategory.CONTEXTUAL,
                    VariableCategory.SENSITIVE  # Can reference age/grade in explanations
                },
                ConversationStep.BENEFITS_PRESENTATION: {
                    VariableCategory.PUBLIC,
                    VariableCategory.PERSONAL,
                    VariableCategory.CONTEXTUAL
                }
            },
            
            ConversationStage.SCHEDULING: {
                ConversationStep.AVAILABILITY_CHECK: {
                    VariableCategory.PUBLIC,
                    VariableCategory.PERSONAL,
                    VariableCategory.CONTEXTUAL
                },
                ConversationStep.SLOT_SELECTION: {
                    VariableCategory.PUBLIC,
                    VariableCategory.PERSONAL,
                    VariableCategory.CONTEXTUAL,
                    VariableCategory.SENSITIVE  # May need contact info for booking
                },
                ConversationStep.BOOKING_CONFIRMATION: {
                    VariableCategory.PUBLIC,
                    VariableCategory.PERSONAL,
                    VariableCategory.CONTEXTUAL,
                    VariableCategory.SENSITIVE  # All info needed for confirmation
                }
            },
            
            ConversationStage.CONFIRMATION: {
                # All steps in confirmation allow full variable access
                None: {  # Default for all steps
                    VariableCategory.PUBLIC,
                    VariableCategory.PERSONAL,
                    VariableCategory.CONTEXTUAL,
                    VariableCategory.SENSITIVE
                }
            },
            
            ConversationStage.FALLBACK: {
                # Fallback scenarios are restrictive by default
                None: {
                    VariableCategory.PUBLIC
                }
            }
        }
    
    def filter_variables(self, variables: Dict[str, Any], stage: str, step: str = None) -> Dict[str, Any]:
        """
        Filter variables based on stage and step policies
        
        Args:
            variables: Dictionary of all available variables
            stage: Current conversation stage
            step: Current conversation step (optional)
            
        Returns:
            Filtered dictionary containing only allowed variables
        """
        try:
            stage_enum = ConversationStage(stage.lower())
        except ValueError:
            app_logger.warning(f"Unknown conversation stage: {stage}")
            stage_enum = ConversationStage.FALLBACK
        
        try:
            step_enum = ConversationStep(step.lower()) if step else None
        except ValueError:
            app_logger.warning(f"Unknown conversation step: {step}")
            step_enum = None
        
        # Get allowed categories for this stage/step
        allowed_categories = self._get_allowed_categories(stage_enum, step_enum)
        
        # Filter variables
        filtered_variables = {}
        blocked_variables = []
        
        for var_name, var_value in variables.items():
            var_category = self._get_variable_category(var_name)
            
            if var_category in allowed_categories:
                filtered_variables[var_name] = var_value
            else:
                blocked_variables.append(var_name)
                self.variables_blocked_count += 1
        
        # Log policy enforcement
        if blocked_variables:
            app_logger.info(f"Variable policy: blocked {len(blocked_variables)} variables for "
                           f"stage={stage}, step={step}: {blocked_variables}")
            app_logger.debug(f"Allowed categories: {[c.value for c in allowed_categories]}")
        
        app_logger.debug(f"Variable policy: {len(filtered_variables)}/{len(variables)} variables allowed")
        
        return filtered_variables
    
    def _get_allowed_categories(self, stage: ConversationStage, step: Optional[ConversationStep]) -> Set[VariableCategory]:
        """Get allowed variable categories for stage/step combination"""
        
        stage_policy = self.stage_policies.get(stage, {})
        
        # Try exact step match first
        if step and step in stage_policy:
            return stage_policy[step]
        
        # Try generic step policy (None key)
        if None in stage_policy:
            return stage_policy[None]
        
        # Default fallback - most restrictive
        return {VariableCategory.PUBLIC}
    
    def _get_variable_category(self, var_name: str) -> VariableCategory:
        """Determine the category of a variable"""
        
        for category, variables in self.variable_categories.items():
            if var_name in variables:
                return category
        
        # Unknown variables are treated as contextual by default
        # This is safer than treating them as public
        return VariableCategory.CONTEXTUAL
    
    def validate_template_variables(self, template_content: str, stage: str, step: str = None) -> Dict[str, Any]:
        """
        Validate that template variables are appropriate for stage/step
        
        Returns:
            Validation report with violations and recommendations
        """
        import re
        
        # Extract variables from template
        template_variables = set(re.findall(r'\{([^}|?!:]+)(?:\|[^}]*)?\}', template_content))
        
        # Get allowed categories
        try:
            stage_enum = ConversationStage(stage.lower())
            step_enum = ConversationStep(step.lower()) if step else None
        except ValueError:
            stage_enum = ConversationStage.FALLBACK
            step_enum = None
        
        allowed_categories = self._get_allowed_categories(stage_enum, step_enum)
        
        # Check each variable
        violations = []
        warnings = []
        
        for var_name in template_variables:
            var_category = self._get_variable_category(var_name.strip())
            
            if var_category not in allowed_categories:
                violations.append({
                    'variable': var_name,
                    'category': var_category.value,
                    'reason': f'Variable category {var_category.value} not allowed in stage {stage}, step {step}'
                })
                self.policy_violations_count += 1
            
            elif var_category == VariableCategory.SENSITIVE and stage_enum == ConversationStage.GREETING:
                warnings.append({
                    'variable': var_name,
                    'category': var_category.value,
                    'reason': 'Sensitive variable in greeting stage - use with caution'
                })
        
        return {
            'valid': len(violations) == 0,
            'stage': stage,
            'step': step,
            'template_variables': list(template_variables),
            'allowed_categories': [c.value for c in allowed_categories],
            'violations': violations,
            'warnings': warnings
        }
    
    def get_policy_metrics(self) -> Dict[str, int]:
        """Get variable policy metrics for observability"""
        return {
            'variables_blocked': self.variables_blocked_count,
            'policy_violations': self.policy_violations_count
        }
    
    def reset_metrics(self) -> None:
        """Reset policy metrics"""
        self.variables_blocked_count = 0
        self.policy_violations_count = 0
    
    def get_stage_recommendations(self, stage: str, step: str = None) -> Dict[str, Any]:
        """Get recommendations for appropriate variables for a stage/step"""
        try:
            stage_enum = ConversationStage(stage.lower())
            step_enum = ConversationStep(step.lower()) if step else None
        except ValueError:
            return {'error': 'Invalid stage or step'}
        
        allowed_categories = self._get_allowed_categories(stage_enum, step_enum)
        
        # Get example variables for each allowed category
        recommended_variables = {}
        for category in allowed_categories:
            recommended_variables[category.value] = list(self.variable_categories[category])
        
        return {
            'stage': stage,
            'step': step,
            'allowed_categories': [c.value for c in allowed_categories],
            'recommended_variables': recommended_variables,
            'restrictions': self._get_stage_restrictions(stage_enum)
        }
    
    def _get_stage_restrictions(self, stage: ConversationStage) -> List[str]:
        """Get human-readable restrictions for a stage"""
        restrictions = {
            ConversationStage.GREETING: [
                "No personal information in initial welcome",
                "Names only after collection confirmed",
                "Keep messaging neutral and inclusive"
            ],
            ConversationStage.QUALIFICATION: [
                "Personal names allowed after introduction",
                "Sensitive info only after needs assessment",
                "Respect information collection flow"
            ],
            ConversationStage.INFORMATION: [
                "All contextual information available",
                "Use personal details to customize explanations",
                "Reference collected preferences"
            ],
            ConversationStage.SCHEDULING: [
                "All information available for booking",
                "Contact details required for confirmation",
                "Personalize scheduling communication"
            ]
        }
        
        return restrictions.get(stage, ["No specific restrictions"])


# Global policy engine instance
variable_policy = VariablePolicyEngine()


def filter_variables_by_stage(variables: Dict[str, Any], stage: str, step: str = None) -> Dict[str, Any]:
    """Convenience function for variable filtering"""
    return variable_policy.filter_variables(variables, stage, step)


def validate_template_variables(template_content: str, stage: str, step: str = None) -> Dict[str, Any]:
    """Convenience function for template variable validation"""
    return variable_policy.validate_template_variables(template_content, stage, step)


__all__ = [
    'VariablePolicyEngine',
    'VariableCategory',
    'ConversationStage',
    'ConversationStep',
    'variable_policy',
    'filter_variables_by_stage',
    'validate_template_variables'
]