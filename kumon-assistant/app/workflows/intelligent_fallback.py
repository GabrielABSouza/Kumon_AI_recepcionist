"""
Intelligent Fallback System for Kumon Assistant

This module provides sophisticated fallback handling with confusion classification,
recovery strategies, and intelligent escalation decisions based on conversation context.
"""

import re
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from ..core.logger import app_logger
from ..prompts.manager import prompt_manager
from .states import ConversationState, WorkflowStage, ConversationStep


class ConfusionType(Enum):
    """Types of confusion that can occur in conversation"""
    TECHNICAL = "technical"           # System/technical issues
    CONCEPTUAL = "conceptual"         # User doesn't understand concept
    PROCEDURAL = "procedural"         # User doesn't know how to proceed
    REFERENTIAL = "referential"       # User refers to unclear context
    LINGUISTIC = "linguistic"         # Language/communication barriers
    EXPECTATIONAL = "expectational"   # User expects different response
    SCOPE = "scope"                  # Question outside system capabilities


class RecoveryStrategy(Enum):
    """Recovery strategies for different confusion types"""
    CLARIFICATION = "clarification"        # Ask for clarification
    EXPLANATION = "explanation"            # Provide detailed explanation
    REDIRECT = "redirect"                  # Redirect to simpler path
    ACKNOWLEDGE_AND_CONTINUE = "acknowledge_continue"  # Acknowledge and move on
    PROVIDE_OPTIONS = "provide_options"    # Give user multiple choices
    ESCALATE = "escalate"                 # Escalate to human
    RESTART = "restart"                   # Start conversation over


class EscalationTrigger(Enum):
    """Triggers for human escalation"""
    MULTIPLE_CONFUSIONS = "multiple_confusions"
    COMPLEX_QUESTION = "complex_question"
    EXPLICIT_REQUEST = "explicit_request"
    TECHNICAL_ISSUE = "technical_issue"
    DISSATISFACTION = "dissatisfaction"
    HIGH_VALUE_LEAD = "high_value_lead"
    TIMEOUT = "timeout"


@dataclass
class ConfusionAnalysis:
    """Analysis of user confusion"""
    confusion_type: ConfusionType
    confidence: float
    indicators: List[str] = field(default_factory=list)
    user_message: str = ""
    context_factors: Dict[str, Any] = field(default_factory=dict)
    severity: float = 0.5  # 0-1 scale
    is_recurring: bool = False


@dataclass
class RecoveryAction:
    """Recovery action to take"""
    strategy: RecoveryStrategy
    response: str
    next_step: ConversationStep
    confidence: float
    reasoning: str
    fallback_strategy: Optional[RecoveryStrategy] = None
    requires_context_reset: bool = False


@dataclass
class EscalationDecision:
    """Decision about escalating to human"""
    should_escalate: bool
    triggers: List[EscalationTrigger] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""
    escalation_message: str = ""
    urgency_level: str = "normal"  # low, normal, high, urgent


class IntelligentFallbackSystem:
    """
    Advanced fallback system with intelligent recovery and escalation
    
    This system analyzes confusion, applies appropriate recovery strategies,
    and makes smart escalation decisions based on conversation context.
    """
    
    def __init__(self):
        # Confusion detection patterns
        self.confusion_patterns = self._build_confusion_patterns()
        
        # Recovery strategy mapping
        self.recovery_strategies = self._build_recovery_strategies()
        
        # Escalation rules
        self.escalation_rules = self._build_escalation_rules()
        
        # Tracking confusion patterns per user
        self.user_confusion_history: Dict[str, List[ConfusionAnalysis]] = {}
        
        # Performance metrics
        self.fallback_stats = {
            "total_confusions": 0,
            "successful_recoveries": 0,
            "escalations": 0,
            "confusion_types": {ct.value: 0 for ct in ConfusionType}
        }
        
        app_logger.info("Intelligent Fallback System initialized")
    
    def _build_confusion_patterns(self) -> Dict[ConfusionType, Dict[str, Any]]:
        """Build patterns for detecting different types of confusion"""
        return {
            ConfusionType.TECHNICAL: {
                "patterns": [
                    r"\b(erro|error|bug|problema\s+técnico)\b",
                    r"\b(não\s+funciona|not\s+working|broken)\b",
                    r"\b(site\s+fora|down|offline)\b",
                    r"\b(carregando|loading|lento|slow)\b"
                ],
                "indicators": ["system_error", "loading_issue", "broken_functionality"],
                "severity_base": 0.8
            },
            
            ConfusionType.CONCEPTUAL: {
                "patterns": [
                    r"\b(não\s+entendo|don't\s+understand|confuso)\b",
                    r"\b(o\s+que\s+é|what\s+is|que\s+significa)\b",
                    r"\b(como\s+assim|what\s+do\s+you\s+mean)\b",
                    r"\b(não\s+sei\s+o\s+que|don't\s+know\s+what)\b"
                ],
                "indicators": ["understanding_gap", "concept_unclear", "definition_needed"],
                "severity_base": 0.6
            },
            
            ConfusionType.PROCEDURAL: {
                "patterns": [
                    r"\b(como\s+faço|how\s+do\s+i|what\s+should\s+i\s+do)\b",
                    r"\b(próximo\s+passo|next\s+step|agora\s+o\s+que)\b",
                    r"\b(como\s+proceder|how\s+to\s+proceed)\b",
                    r"\b(não\s+sei\s+como|don't\s+know\s+how)\b"
                ],
                "indicators": ["process_unclear", "next_step_unknown", "procedure_needed"],
                "severity_base": 0.5
            },
            
            ConfusionType.REFERENTIAL: {
                "patterns": [
                    r"\b(que\s+isso|what\s+is\s+that|isso\s+o\s+que)\b",
                    r"\b(do\s+que\s+você\s+está\s+falando|what\s+are\s+you\s+talking\s+about)\b",
                    r"\b(qual\s+programa|which\s+program|que\s+curso)\b",
                    r"\b(não\s+lembro|don't\s+remember|esqueci)\b"
                ],
                "indicators": ["unclear_reference", "context_lost", "memory_gap"],
                "severity_base": 0.4
            },
            
            ConfusionType.LINGUISTIC: {
                "patterns": [
                    r"\b(não\s+falo\s+português|don't\s+speak\s+portuguese)\b",
                    r"\b(english\s+please|em\s+inglês)\b",
                    r"\b(não\s+entendi\s+a\s+palavra|don't\s+understand\s+the\s+word)\b",
                    r"[^\x00-\x7F]{5,}"  # Non-ASCII characters (potentially other languages)
                ],
                "indicators": ["language_barrier", "translation_needed", "communication_difficulty"],
                "severity_base": 0.7
            },
            
            ConfusionType.EXPECTATIONAL: {
                "patterns": [
                    r"\b(esperava|expected|achei\s+que\s+seria)\b",
                    r"\b(pensei\s+que|thought\s+that|imagino\s+que)\b",
                    r"\b(não\s+é\s+isso|that's\s+not\s+it|diferente)\b",
                    r"\b(queria\s+falar\s+sobre|wanted\s+to\s+talk\s+about)\b"
                ],
                "indicators": ["expectation_mismatch", "different_intent", "topic_deviation"],
                "severity_base": 0.3
            },
            
            ConfusionType.SCOPE: {
                "patterns": [
                    r"\b(você\s+sabe\s+sobre|do\s+you\s+know\s+about)\b.*(?!kumon|matemática|português)",
                    r"\b(outras\s+escolas|other\s+schools|concorrente)\b",
                    r"\b(preço\s+em\s+outra|price\s+at\s+other)\b",
                    r"\b(problema\s+pessoal|personal\s+problem)\b"
                ],
                "indicators": ["out_of_scope", "competitor_question", "personal_issue"],
                "severity_base": 0.6
            }
        }
    
    def _build_recovery_strategies(self) -> Dict[ConfusionType, Dict[str, Any]]:
        """Build recovery strategies for each confusion type"""
        return {
            ConfusionType.TECHNICAL: {
                "primary_strategy": RecoveryStrategy.ESCALATE,
                "fallback_strategy": RecoveryStrategy.ACKNOWLEDGE_AND_CONTINUE,
                "prompt_key": "kumon:fallback:technical_issue",
                "requires_immediate_attention": True
            },
            
            ConfusionType.CONCEPTUAL: {
                "primary_strategy": RecoveryStrategy.EXPLANATION,
                "fallback_strategy": RecoveryStrategy.PROVIDE_OPTIONS,
                "prompt_key": "kumon:fallback:conceptual_help",
                "requires_immediate_attention": False
            },
            
            ConfusionType.PROCEDURAL: {
                "primary_strategy": RecoveryStrategy.PROVIDE_OPTIONS,
                "fallback_strategy": RecoveryStrategy.REDIRECT,
                "prompt_key": "kumon:fallback:procedural_guide",
                "requires_immediate_attention": False
            },
            
            ConfusionType.REFERENTIAL: {
                "primary_strategy": RecoveryStrategy.CLARIFICATION,
                "fallback_strategy": RecoveryStrategy.RESTART,
                "prompt_key": "kumon:fallback:reference_clarification",
                "requires_immediate_attention": False
            },
            
            ConfusionType.LINGUISTIC: {
                "primary_strategy": RecoveryStrategy.ESCALATE,
                "fallback_strategy": RecoveryStrategy.PROVIDE_OPTIONS,
                "prompt_key": "kumon:fallback:language_support",
                "requires_immediate_attention": True
            },
            
            ConfusionType.EXPECTATIONAL: {
                "primary_strategy": RecoveryStrategy.ACKNOWLEDGE_AND_CONTINUE,
                "fallback_strategy": RecoveryStrategy.REDIRECT,
                "prompt_key": "kumon:fallback:expectation_reset",
                "requires_immediate_attention": False
            },
            
            ConfusionType.SCOPE: {
                "primary_strategy": RecoveryStrategy.REDIRECT,
                "fallback_strategy": RecoveryStrategy.ESCALATE,
                "prompt_key": "kumon:fallback:scope_redirect",
                "requires_immediate_attention": False
            }
        }
    
    def _build_escalation_rules(self) -> List[Dict[str, Any]]:
        """Build rules for escalation decisions"""
        return [
            {
                "trigger": EscalationTrigger.EXPLICIT_REQUEST,
                "condition": lambda state: any(phrase in state["user_message"].lower() 
                                             for phrase in ["falar com pessoa", "atendente humano", "human"]),
                "confidence": 0.95,
                "urgency": "normal"
            },
            {
                "trigger": EscalationTrigger.MULTIPLE_CONFUSIONS,
                "condition": lambda state: state["metrics"].consecutive_confusion >= 3,
                "confidence": 0.9,
                "urgency": "normal"
            },
            {
                "trigger": EscalationTrigger.TECHNICAL_ISSUE,
                "condition": lambda state: "technical" in getattr(state, "last_confusion_type", ""),
                "confidence": 0.85,
                "urgency": "high"
            },
            {
                "trigger": EscalationTrigger.HIGH_VALUE_LEAD,
                "condition": lambda state: (
                    state["user_context"].programs_interested and
                    len(state["message_history"]) > 5 and
                    state["metrics"].consecutive_confusion >= 2
                ),
                "confidence": 0.8,
                "urgency": "high"
            },
            {
                "trigger": EscalationTrigger.DISSATISFACTION,
                "condition": lambda state: any(phrase in state["user_message"].lower() 
                                             for phrase in ["frustrado", "chateado", "irritado", "disappointed"]),
                "confidence": 0.85,
                "urgency": "high"
            },
            {
                "trigger": EscalationTrigger.TIMEOUT,
                "condition": lambda state: (
                    datetime.now() - state["metrics"].start_time > timedelta(minutes=15) and
                    state["metrics"].consecutive_confusion >= 1
                ),
                "confidence": 0.7,
                "urgency": "normal"
            }
        ]
    
    async def analyze_confusion(
        self, 
        conversation_state: ConversationState
    ) -> ConfusionAnalysis:
        """
        Analyze user confusion and classify its type
        
        Args:
            conversation_state: Current conversation state
            
        Returns:
            ConfusionAnalysis: Detailed analysis of the confusion
        """
        try:
            self.fallback_stats["total_confusions"] += 1
            
            user_message = conversation_state["user_message"].lower().strip()
            phone_number = conversation_state["phone_number"]
            
            app_logger.info(f"Analyzing confusion for {phone_number}")
            
            # Initialize analysis
            best_match = None
            best_confidence = 0.0
            
            # Check each confusion type
            for confusion_type, config in self.confusion_patterns.items():
                confidence = 0.0
                matched_indicators = []
                
                # Check patterns
                for pattern in config["patterns"]:
                    if re.search(pattern, user_message):
                        confidence += 0.3
                        matched_indicators.append(pattern)
                
                # Context factors
                context_factors = self._extract_context_factors(confusion_type, conversation_state)
                if context_factors:
                    confidence += 0.2
                
                # Recurrence check
                is_recurring = self._check_recurrence(phone_number, confusion_type)
                if is_recurring:
                    confidence += 0.1
                
                # Calculate severity
                severity = config["severity_base"]
                if is_recurring:
                    severity = min(1.0, severity + 0.2)
                if context_factors.get("multiple_attempts", 0) > 1:
                    severity = min(1.0, severity + 0.1)
                
                # Update best match
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = ConfusionAnalysis(
                        confusion_type=confusion_type,
                        confidence=confidence,
                        indicators=matched_indicators,
                        user_message=conversation_state["user_message"],
                        context_factors=context_factors,
                        severity=severity,
                        is_recurring=is_recurring
                    )
            
            # Default to general confusion if no strong match
            if not best_match or best_confidence < 0.3:
                best_match = ConfusionAnalysis(
                    confusion_type=ConfusionType.CONCEPTUAL,
                    confidence=0.5,
                    indicators=["general_confusion"],
                    user_message=conversation_state["user_message"],
                    context_factors={"default_classification": True},
                    severity=0.4,
                    is_recurring=False
                )
            
            # Track confusion history
            self._track_confusion_history(phone_number, best_match)
            
            # Update stats
            self.fallback_stats["confusion_types"][best_match.confusion_type.value] += 1
            
            app_logger.info(f"Confusion classified: {best_match.confusion_type.value} "
                          f"(confidence: {best_match.confidence:.2f})")
            
            return best_match
            
        except Exception as e:
            app_logger.error(f"Error analyzing confusion: {e}")
            # Return safe default
            return ConfusionAnalysis(
                confusion_type=ConfusionType.TECHNICAL,
                confidence=0.5,
                indicators=["error_in_analysis"],
                user_message=conversation_state["user_message"],
                context_factors={"analysis_error": str(e)},
                severity=0.8,
                is_recurring=False
            )
    
    def _extract_context_factors(
        self, 
        confusion_type: ConfusionType, 
        conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """Extract context factors relevant to confusion type"""
        factors = {}
        
        metrics = conversation_state["metrics"]
        user_message = conversation_state["user_message"]
        
        # General factors
        factors["message_count"] = metrics.message_count
        factors["clarification_attempts"] = metrics.clarification_attempts
        factors["consecutive_confusion"] = metrics.consecutive_confusion
        factors["conversation_duration"] = (datetime.now() - metrics.start_time).total_seconds() / 60
        
        # Type-specific factors
        if confusion_type == ConfusionType.TECHNICAL:
            factors["contains_error_keywords"] = any(word in user_message.lower() 
                                                   for word in ["erro", "bug", "problema"])
            factors["system_response_time"] = getattr(conversation_state, "last_response_time", 0)
        
        elif confusion_type == ConfusionType.CONCEPTUAL:
            factors["question_marks"] = user_message.count("?")
            factors["explanation_requests"] = len(re.findall(r"explain|explique|como", user_message.lower()))
        
        elif confusion_type == ConfusionType.REFERENTIAL:
            factors["pronouns_count"] = len(re.findall(r"\b(isso|isto|aquilo|ele|ela)\b", user_message.lower()))
            factors["context_gap"] = len(conversation_state["message_history"]) - metrics.clarification_attempts
        
        return factors
    
    def _check_recurrence(self, phone_number: str, confusion_type: ConfusionType) -> bool:
        """Check if this confusion type is recurring for this user"""
        if phone_number not in self.user_confusion_history:
            return False
        
        recent_confusions = self.user_confusion_history[phone_number][-3:]  # Last 3 confusions
        return sum(1 for c in recent_confusions if c.confusion_type == confusion_type) >= 2
    
    def _track_confusion_history(self, phone_number: str, analysis: ConfusionAnalysis) -> None:
        """Track confusion history for pattern analysis"""
        if phone_number not in self.user_confusion_history:
            self.user_confusion_history[phone_number] = []
        
        self.user_confusion_history[phone_number].append(analysis)
        
        # Keep only last 10 confusions per user
        self.user_confusion_history[phone_number] = self.user_confusion_history[phone_number][-10:]
    
    async def determine_recovery_action(
        self, 
        confusion_analysis: ConfusionAnalysis,
        conversation_state: ConversationState
    ) -> RecoveryAction:
        """
        Determine the best recovery action based on confusion analysis
        
        Args:
            confusion_analysis: Result of confusion analysis
            conversation_state: Current conversation state
            
        Returns:
            RecoveryAction: Recommended recovery action
        """
        try:
            confusion_type = confusion_analysis.confusion_type
            strategy_config = self.recovery_strategies[confusion_type]
            
            # Determine strategy based on severity and recurrence
            if confusion_analysis.severity > 0.7 or confusion_analysis.is_recurring:
                strategy = strategy_config.get("fallback_strategy", strategy_config["primary_strategy"])
            else:
                strategy = strategy_config["primary_strategy"]
            
            # Generate recovery response
            response = await self._generate_recovery_response(
                strategy, 
                confusion_analysis, 
                conversation_state,
                strategy_config
            )
            
            # Determine next step
            next_step = self._determine_recovery_next_step(strategy, conversation_state)
            
            # Calculate confidence
            confidence = self._calculate_recovery_confidence(
                strategy, confusion_analysis, conversation_state
            )
            
            # Build reasoning
            reasoning = f"Confusion: {confusion_type.value}, Strategy: {strategy.value}"
            if confusion_analysis.is_recurring:
                reasoning += " (recurring)"
            if confusion_analysis.severity > 0.7:
                reasoning += " (high severity)"
            
            recovery_action = RecoveryAction(
                strategy=strategy,
                response=response,
                next_step=next_step,
                confidence=confidence,
                reasoning=reasoning,
                fallback_strategy=strategy_config.get("fallback_strategy"),
                requires_context_reset=strategy in [RecoveryStrategy.RESTART, RecoveryStrategy.REDIRECT]
            )
            
            app_logger.info(f"Recovery action determined: {strategy.value} "
                          f"(confidence: {confidence:.2f})")
            
            return recovery_action
            
        except Exception as e:
            app_logger.error(f"Error determining recovery action: {e}")
            # Return safe fallback action
            return RecoveryAction(
                strategy=RecoveryStrategy.CLARIFICATION,
                response="Desculpe, pode me explicar melhor o que você precisa? 😊",
                next_step=ConversationStep.CLARIFICATION_ATTEMPT,
                confidence=0.5,
                reasoning=f"Error in recovery determination: {str(e)}"
            )
    
    async def _generate_recovery_response(
        self,
        strategy: RecoveryStrategy,
        confusion_analysis: ConfusionAnalysis,
        conversation_state: ConversationState,
        strategy_config: Dict[str, Any]
    ) -> str:
        """Generate appropriate recovery response"""
        try:
            # Try to get response from LangSmith prompt
            prompt_key = strategy_config.get("prompt_key")
            if prompt_key:
                try:
                    response = await prompt_manager.get_prompt(
                        prompt_key,
                        variables={
                            "user_message": confusion_analysis.user_message,
                            "confusion_type": confusion_analysis.confusion_type.value,
                            "user_name": conversation_state["user_context"].parent_name or "cliente"
                        }
                    )
                    if response:
                        return response
                except Exception as e:
                    app_logger.warning(f"Failed to get recovery prompt {prompt_key}: {e}")
            
            # Fallback to hardcoded responses based on strategy
            if strategy == RecoveryStrategy.CLARIFICATION:
                return "Desculpe, não entendi completamente. Pode me explicar de outra forma? 🤔"
            
            elif strategy == RecoveryStrategy.EXPLANATION:
                return "Deixe-me explicar melhor! O Kumon é uma metodologia que desenvolve o aprendizado de forma gradual e personalizada. Sobre qual aspecto você gostaria de saber mais? 📚"
            
            elif strategy == RecoveryStrategy.PROVIDE_OPTIONS:
                return """Posso ajudá-lo com:

🔢 **Programa de Matemática** - Desenvolvimento do cálculo mental
📖 **Programa de Português** - Melhora na leitura e escrita  
💰 **Valores e investimento** - Informações sobre mensalidades
📅 **Agendamento** - Marcar uma apresentação

Sobre qual dessas opções você gostaria de saber mais?"""
            
            elif strategy == RecoveryStrategy.REDIRECT:
                return "Vamos focar no que é mais importante para você! Me conte: você está interessado no Kumon para qual idade e em que programa? 🎯"
            
            elif strategy == RecoveryStrategy.ACKNOWLEDGE_AND_CONTINUE:
                return "Entendo! Vamos seguir em frente. Como posso ajudá-lo com informações sobre o Kumon? 😊"
            
            elif strategy == RecoveryStrategy.RESTART:
                return "Vamos começar de novo! Olá! Sou a Cecília do Kumon Vila A. Para começar, qual é o seu nome? 😊"
            
            elif strategy == RecoveryStrategy.ESCALATE:
                return await prompt_manager.get_prompt(
                    "kumon:fallback:handoff:explicit_request",
                    fallback_enabled=True
                )
            
            # Default fallback
            return "Desculpe pela confusão! Como posso ajudá-lo melhor? 😊"
            
        except Exception as e:
            app_logger.error(f"Error generating recovery response: {e}")
            return "Desculpe, tive um problema. Como posso ajudá-lo? 😊"
    
    def _determine_recovery_next_step(
        self, 
        strategy: RecoveryStrategy, 
        conversation_state: ConversationState
    ) -> ConversationStep:
        """Determine next conversation step based on recovery strategy"""
        if strategy == RecoveryStrategy.ESCALATE:
            return ConversationStep.CONVERSATION_ENDED
        elif strategy == RecoveryStrategy.RESTART:
            return ConversationStep.WELCOME
        elif strategy in [RecoveryStrategy.REDIRECT, RecoveryStrategy.PROVIDE_OPTIONS]:
            return ConversationStep.PROVIDE_PROGRAM_INFO
        else:
            return ConversationStep.CLARIFICATION_ATTEMPT
    
    def _calculate_recovery_confidence(
        self,
        strategy: RecoveryStrategy,
        confusion_analysis: ConfusionAnalysis,
        conversation_state: ConversationState
    ) -> float:
        """Calculate confidence in recovery strategy"""
        base_confidence = 0.7
        
        # Adjust based on confusion analysis confidence
        base_confidence *= confusion_analysis.confidence
        
        # Adjust based on strategy appropriateness
        if strategy == RecoveryStrategy.ESCALATE and confusion_analysis.severity > 0.7:
            base_confidence += 0.2
        elif strategy == RecoveryStrategy.EXPLANATION and confusion_analysis.confusion_type == ConfusionType.CONCEPTUAL:
            base_confidence += 0.15
        elif strategy == RecoveryStrategy.PROVIDE_OPTIONS and conversation_state["metrics"].clarification_attempts <= 1:
            base_confidence += 0.1
        
        # Penalize for recurring confusions
        if confusion_analysis.is_recurring:
            base_confidence *= 0.8
        
        return min(0.95, max(0.3, base_confidence))
    
    async def should_escalate_to_human(
        self, 
        conversation_state: ConversationState,
        confusion_analysis: Optional[ConfusionAnalysis] = None
    ) -> EscalationDecision:
        """
        Determine if conversation should be escalated to human
        
        Args:
            conversation_state: Current conversation state
            confusion_analysis: Optional confusion analysis
            
        Returns:
            EscalationDecision: Decision about escalation
        """
        try:
            triggers = []
            total_confidence = 0.0
            reasoning_parts = []
            
            # Check each escalation rule
            for rule in self.escalation_rules:
                try:
                    if rule["condition"](conversation_state):
                        triggers.append(rule["trigger"])
                        total_confidence += rule["confidence"]
                        reasoning_parts.append(f"{rule['trigger'].value} (confidence: {rule['confidence']})")
                except Exception as e:
                    app_logger.warning(f"Error evaluating escalation rule {rule['trigger']}: {e}")
            
            # Additional checks based on confusion analysis
            if confusion_analysis:
                if (confusion_analysis.confusion_type in [ConfusionType.TECHNICAL, ConfusionType.LINGUISTIC] and
                    confusion_analysis.severity > 0.7):
                    triggers.append(EscalationTrigger.COMPLEX_QUESTION)
                    total_confidence += 0.8
                    reasoning_parts.append("Complex/Technical confusion detected")
            
            # Calculate final decision
            should_escalate = len(triggers) > 0 and (total_confidence / max(1, len(triggers))) > 0.7
            final_confidence = min(0.95, total_confidence / max(1, len(triggers))) if triggers else 0.0
            
            # Determine urgency
            urgency = "normal"
            if any(trigger in [EscalationTrigger.TECHNICAL_ISSUE, EscalationTrigger.DISSATISFACTION] 
                   for trigger in triggers):
                urgency = "high"
            elif EscalationTrigger.EXPLICIT_REQUEST in triggers:
                urgency = "urgent"
            
            # Generate escalation message
            escalation_message = ""
            if should_escalate:
                escalation_message = await prompt_manager.get_prompt(
                    "kumon:fallback:handoff:explicit_request" if urgency == "urgent" 
                    else "kumon:fallback:handoff:repeated_confusion",
                    fallback_enabled=True
                )
            
            decision = EscalationDecision(
                should_escalate=should_escalate,
                triggers=triggers,
                confidence=final_confidence,
                reasoning="; ".join(reasoning_parts),
                escalation_message=escalation_message,
                urgency_level=urgency
            )
            
            if should_escalate:
                self.fallback_stats["escalations"] += 1
                app_logger.info(f"Escalation decision: {should_escalate} "
                              f"(triggers: {[t.value for t in triggers]})")
            
            return decision
            
        except Exception as e:
            app_logger.error(f"Error in escalation decision: {e}")
            # Safe default - escalate on error
            return EscalationDecision(
                should_escalate=True,
                triggers=[EscalationTrigger.TECHNICAL_ISSUE],
                confidence=0.8,
                reasoning=f"Error in escalation logic: {str(e)}",
                escalation_message="Vou conectá-lo com nossa equipe! 📞 WhatsApp: (51) 99692-1999",
                urgency_level="high"
            )
    
    def get_fallback_stats(self) -> Dict[str, Any]:
        """Get fallback system performance statistics"""
        recovery_rate = (self.fallback_stats["successful_recoveries"] / 
                        max(1, self.fallback_stats["total_confusions"]))
        
        escalation_rate = (self.fallback_stats["escalations"] / 
                          max(1, self.fallback_stats["total_confusions"]))
        
        return {
            **self.fallback_stats,
            "recovery_rate": recovery_rate,
            "escalation_rate": escalation_rate,
            "active_users": len(self.user_confusion_history)
        }
    
    def mark_recovery_successful(self, phone_number: str) -> None:
        """Mark a recovery as successful for statistics"""
        self.fallback_stats["successful_recoveries"] += 1
        app_logger.info(f"Recovery marked successful for {phone_number}")


# Global instance
intelligent_fallback = IntelligentFallbackSystem()