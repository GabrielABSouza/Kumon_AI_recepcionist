"""
Intelligent Validation Routing System

Sistema híbrido Score-Based + Rule Engine para decidir quando ativar validation_node.
Substitui estruturas if/else primitivas por sistema sofisticado de scoring e regras.

Arquitetura:
- ValidationRoutingEngine: Score-based system similar ao template resolution
- ValidationRuleEngine: Rule composition pattern com priority
- KumonValidationRouter: Híbrido que combina ambas abordagens
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional, Callable
from datetime import datetime

from ..state.models import CeciliaState
from ...core.logger import app_logger


@dataclass
class RuleResult:
    """Resultado da avaliação de uma regra"""
    triggered: bool
    score: float
    reason: str
    priority: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ValidationDecision:
    """Decisão final sobre validação"""
    should_validate: bool
    total_score: float
    triggered_rules: List[RuleResult]
    reasoning: str
    confidence: float
    method: str


class ValidationRule(ABC):
    """Base class para regras de validação"""
    
    @abstractmethod
    def evaluate(self, state: CeciliaState) -> RuleResult:
        """Avalia se esta regra foi triggered"""
        pass
    
    @property
    @abstractmethod
    def priority(self) -> int:
        """Prioridade da regra (0-100, maior = mais prioritária)"""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nome identificador da regra"""
        pass


class FirstMessageRule(ValidationRule):
    """SEMPRE valida primeira mensagem para garantir identidade Cecília"""
    
    def evaluate(self, state: CeciliaState) -> RuleResult:
        message_count = state.get("conversation_metrics", {}).get("message_count", 0)
        is_first = message_count <= 1
        
        return RuleResult(
            triggered=is_first,
            score=100.0 if is_first else 0.0,
            reason="first_message_identity_validation",
            priority="critical",
            metadata={"message_count": message_count}
        )
    
    @property
    def priority(self) -> int:
        return 100
    
    @property 
    def name(self) -> str:
        return "first_message"


class LowConfidenceRule(ValidationRule):
    """Valida quando LLM tem baixa confiança na resposta"""
    
    def evaluate(self, state: CeciliaState) -> RuleResult:
        llm_confidence = state.get("llm_confidence", 1.0)
        is_low_confidence = llm_confidence < 0.6
        
        # Score proporcional à baixa confiança
        score = max(0, (0.6 - llm_confidence) * 133.33) if is_low_confidence else 0
        
        return RuleResult(
            triggered=is_low_confidence,
            score=score,
            reason="llm_low_confidence_detected",
            priority="high",
            metadata={"llm_confidence": llm_confidence, "threshold": 0.6}
        )
    
    @property
    def priority(self) -> int:
        return 80
    
    @property
    def name(self) -> str:
        return "low_confidence"


class SensitiveContentRule(ValidationRule):
    """Valida quando detecta palavras/padrões sensíveis"""
    
    def __init__(self):
        self.sensitive_patterns = {
            "identity_breach": [
                r"ia artificial", r"chatbot", r"sistema", r"simulação",
                r"assistente virtual", r"robô", r"algoritmo"
            ],
            "capability_denial": [
                r"não posso", r"não sou capaz", r"limitações", r"não consigo",
                r"impossível para mim", r"não tenho como"
            ],
            "technical_exposure": [
                r"token", r"prompt", r"modelo", r"treinamento", r"api",
                r"processamento", r"linguagem natural"
            ]
        }
    
    def evaluate(self, state: CeciliaState) -> RuleResult:
        response = state.get("last_bot_response", "")
        response_lower = response.lower()
        
        detected_categories = []
        total_matches = 0
        
        for category, patterns in self.sensitive_patterns.items():
            matches = sum(1 for pattern in patterns if re.search(pattern, response_lower))
            if matches > 0:
                detected_categories.append(category)
                total_matches += matches
        
        is_triggered = len(detected_categories) > 0
        # Score baseado no número de categorias e matches
        score = min(90.0, len(detected_categories) * 30 + total_matches * 10) if is_triggered else 0
        
        return RuleResult(
            triggered=is_triggered,
            score=score,
            reason="sensitive_content_detected",
            priority="high",
            metadata={
                "detected_categories": detected_categories,
                "total_matches": total_matches,
                "response_length": len(response)
            }
        )
    
    @property
    def priority(self) -> int:
        return 85
    
    @property
    def name(self) -> str:
        return "sensitive_content"


class RecoveryContextRule(ValidationRule):
    """Valida após tentativas de recovery ou fallback"""
    
    def evaluate(self, state: CeciliaState) -> RuleResult:
        recovery_attempts = state.get("recovery_attempts", 0)
        fallback_level = state.get("fallback_level", 0)
        validation_failures = len(state.get("data_validation", {}).get("validation_history", []))
        
        # Qualquer sinal de recovery/fallback ativa validação
        is_triggered = recovery_attempts > 0 or fallback_level > 0 or validation_failures >= 2
        
        # Score baseado na severidade da situação
        score = 0
        if is_triggered:
            score += recovery_attempts * 25
            score += fallback_level * 20  
            score += min(validation_failures, 3) * 15
            score = min(score, 70.0)  # Cap no medium priority
        
        return RuleResult(
            triggered=is_triggered,
            score=score,
            reason="recovery_context_validation",
            priority="medium",
            metadata={
                "recovery_attempts": recovery_attempts,
                "fallback_level": fallback_level,
                "validation_failures": validation_failures
            }
        )
    
    @property
    def priority(self) -> int:
        return 60
    
    @property
    def name(self) -> str:
        return "recovery_context"


class ComplexityRule(ValidationRule):
    """Valida conversas com alta complexidade ou muitas interações"""
    
    def evaluate(self, state: CeciliaState) -> RuleResult:
        conversation_metrics = state.get("conversation_metrics", {})
        message_count = conversation_metrics.get("message_count", 0)
        stage_changes = conversation_metrics.get("stage_changes", 0)
        
        # Complexidade baseada em múltiplos fatores
        complexity_score = 0.0
        
        # Mensagens longas indicam complexidade
        if message_count >= 10:
            complexity_score += 0.3
        
        # Muitas mudanças de estágio
        if stage_changes >= 3:
            complexity_score += 0.4
            
        # Conversa muito longa
        if message_count >= 20:
            complexity_score += 0.3
        
        is_triggered = complexity_score >= 0.6
        score = complexity_score * 60 if is_triggered else 0
        
        return RuleResult(
            triggered=is_triggered,
            score=score,
            reason="high_complexity_conversation",
            priority="medium",
            metadata={
                "complexity_score": complexity_score,
                "message_count": message_count,
                "stage_changes": stage_changes
            }
        )
    
    @property
    def priority(self) -> int:
        return 50
    
    @property
    def name(self) -> str:
        return "complexity"


class ValidationRoutingEngine:
    """Score-based validation routing similar ao template resolution system"""
    
    def __init__(self):
        self.validation_conditions = {
            "first_message_critical": {
                "condition": lambda state: state.get("conversation_metrics", {}).get("message_count", 0) <= 1,
                "score": 100,
                "priority": "critical",
                "description": "First message requires identity validation"
            },
            "low_llm_confidence": {
                "condition": lambda state: state.get("llm_confidence", 1.0) < 0.6,
                "score": 80,
                "priority": "high", 
                "description": "LLM confidence below threshold"
            },
            "sensitive_content": {
                "condition": lambda state: self._contains_sensitive_patterns(state.get("last_bot_response", "")),
                "score": 90,
                "priority": "high",
                "description": "Response contains sensitive patterns"
            },
            "recovery_context": {
                "condition": lambda state: (state.get("recovery_attempts", 0) > 0 or 
                                          state.get("fallback_level", 0) > 0),
                "score": 65,
                "priority": "medium",
                "description": "Recovery or fallback context detected"
            },
            "high_complexity": {
                "condition": lambda state: self._calculate_complexity_score(state) > 0.7,
                "score": 55,
                "priority": "medium", 
                "description": "High conversation complexity"
            },
            "validation_failures": {
                "condition": lambda state: len(state.get("data_validation", {}).get("validation_history", [])) >= 2,
                "score": 50,
                "priority": "medium",
                "description": "Multiple previous validation failures"
            }
        }
    
    def _contains_sensitive_patterns(self, response: str) -> bool:
        """Check for sensitive patterns in response"""
        if not response:
            return False
            
        sensitive_words = [
            "ia artificial", "chatbot", "sistema", "simulação",
            "não posso", "não sou capaz", "limitações", "assistente virtual"
        ]
        
        response_lower = response.lower()
        return any(word in response_lower for word in sensitive_words)
    
    def _calculate_complexity_score(self, state: CeciliaState) -> float:
        """Calculate conversation complexity score"""
        metrics = state.get("conversation_metrics", {})
        message_count = metrics.get("message_count", 0)
        stage_changes = metrics.get("stage_changes", 0)
        
        # Normalize complexity factors
        msg_complexity = min(message_count / 20.0, 1.0)
        stage_complexity = min(stage_changes / 5.0, 1.0)
        
        return (msg_complexity + stage_complexity) / 2.0
    
    def calculate_validation_score(self, state: CeciliaState) -> Tuple[float, List[str]]:
        """Calculate total validation score similar to template scoring"""
        total_score = 0.0
        triggered_conditions = []
        
        for condition_name, config in self.validation_conditions.items():
            if config["condition"](state):
                # Apply priority weighting
                weight = {"critical": 1.0, "high": 0.85, "medium": 0.7, "low": 0.5}[config["priority"]]
                weighted_score = config["score"] * weight
                total_score += weighted_score
                triggered_conditions.append(condition_name)
                
                app_logger.debug(f"Validation condition triggered: {condition_name} (score: {weighted_score:.1f})")
        
        # Cap total score at 100
        total_score = min(total_score, 100.0)
        
        return total_score, triggered_conditions
    
    def should_validate(self, state: CeciliaState, threshold: float = 50.0) -> Tuple[bool, Dict[str, Any]]:
        """Determine if validation is needed based on scoring"""
        score, triggered = self.calculate_validation_score(state)
        should_validate = score >= threshold
        
        result = {
            "validation_score": score,
            "threshold": threshold,
            "triggered_conditions": triggered,
            "confidence": min(score / 100.0, 1.0),
            "method": "score_based"
        }
        
        if should_validate:
            app_logger.info(f"Validation required: score={score:.1f} >= threshold={threshold}")
        else:
            app_logger.debug(f"Validation not required: score={score:.1f} < threshold={threshold}")
        
        return should_validate, result


class ValidationRuleEngine:
    """Rule engine with composition pattern for validation decisions"""
    
    def __init__(self):
        self.rules = [
            FirstMessageRule(),
            SensitiveContentRule(), 
            LowConfidenceRule(),
            RecoveryContextRule(),
            ComplexityRule()
        ]
    
    def evaluate(self, state: CeciliaState) -> ValidationDecision:
        """Evaluate all rules and make validation decision"""
        triggered_results = []
        
        # Sort rules by priority and evaluate
        sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)
        
        for rule in sorted_rules:
            try:
                result = rule.evaluate(state)
                if result.triggered:
                    triggered_results.append(result)
                    app_logger.debug(f"Validation rule triggered: {rule.name} (score: {result.score:.1f})")
            except Exception as e:
                app_logger.error(f"Error evaluating rule {rule.name}: {e}")
        
        # Aggregate scores with priority weighting
        total_score = 0.0
        for result in triggered_results:
            weight = {"critical": 1.0, "high": 0.85, "medium": 0.7, "low": 0.5}[result.priority]
            total_score += result.score * weight
        
        # Cap at 100
        total_score = min(total_score, 100.0)
        
        # Decision logic
        should_validate = total_score >= 50.0 or any(r.priority == "critical" for r in triggered_results)
        confidence = min(total_score / 100.0, 1.0)
        
        # Build reasoning
        reasoning = self._build_reasoning(triggered_results, total_score, should_validate)
        
        return ValidationDecision(
            should_validate=should_validate,
            total_score=total_score,
            triggered_rules=triggered_results,
            reasoning=reasoning,
            confidence=confidence,
            method="rule_based"
        )
    
    def _build_reasoning(self, results: List[RuleResult], score: float, decision: bool) -> str:
        """Build human-readable reasoning for the decision"""
        if not results:
            return f"No validation rules triggered (score: {score:.1f})"
        
        triggered_reasons = [r.reason for r in results]
        decision_text = "VALIDATE" if decision else "SKIP"
        
        return f"{decision_text}: {score:.1f} points from {len(results)} rules: {', '.join(triggered_reasons)}"


class KumonValidationRouter:
    """Hybrid validation router combining Score-Based + Rule Engine approaches"""
    
    def __init__(self, score_threshold: float = 40.0):
        self.score_engine = ValidationRoutingEngine()
        self.rule_engine = ValidationRuleEngine() 
        self.score_threshold = score_threshold
        
        app_logger.info(f"KumonValidationRouter initialized with threshold={score_threshold}")
    
    def should_validate_response(self, state: CeciliaState) -> Dict[str, Any]:
        """
        Determine if response needs validation using hybrid approach
        
        Uses both scoring system and rule engine, with final decision
        based on either system recommending validation.
        
        Args:
            state: Current conversation state
            
        Returns:
            Dict with validation decision and analysis details
        """
        try:
            # Score-based analysis
            score_should_validate, score_analysis = self.score_engine.should_validate(
                state, self.score_threshold
            )
            
            # Rule-based analysis  
            rule_decision = self.rule_engine.evaluate(state)
            
            # Hybrid decision: Either system can trigger validation
            final_decision = score_should_validate or rule_decision.should_validate
            
            # Combine confidence scores
            combined_confidence = max(
                score_analysis["confidence"],
                rule_decision.confidence
            )
            
            # Determine primary method based on higher confidence
            primary_method = "score_based" if score_analysis["confidence"] >= rule_decision.confidence else "rule_based"
            
            result = {
                "should_validate": final_decision,
                "primary_method": primary_method,
                "combined_confidence": combined_confidence,
                "score_analysis": score_analysis,
                "rule_analysis": {
                    "should_validate": rule_decision.should_validate,
                    "total_score": rule_decision.total_score,
                    "triggered_rules": [r.reason for r in rule_decision.triggered_rules],
                    "reasoning": rule_decision.reasoning,
                    "confidence": rule_decision.confidence
                },
                "decision_reasoning": self._build_hybrid_reasoning(
                    final_decision, score_should_validate, rule_decision, primary_method
                )
            }
            
            if final_decision:
                app_logger.info(
                    f"🔍 VALIDATION REQUIRED - Method: {primary_method}, "
                    f"Confidence: {combined_confidence:.2f}, "
                    f"Score: {score_analysis['validation_score']:.1f}, "
                    f"Rules: {len(rule_decision.triggered_rules)}"
                )
            else:
                app_logger.debug(
                    f"✅ Validation not needed - Score: {score_analysis['validation_score']:.1f}, "
                    f"Rules triggered: {len(rule_decision.triggered_rules)}"
                )
            
            return result
            
        except Exception as e:
            app_logger.error(f"Error in validation routing: {e}")
            # Fail safe - validate on error
            return {
                "should_validate": True,
                "primary_method": "error_fallback",
                "combined_confidence": 0.5,
                "error": str(e),
                "decision_reasoning": "Validation required due to routing error (fail-safe)"
            }
    
    def _build_hybrid_reasoning(
        self, 
        final_decision: bool, 
        score_decision: bool, 
        rule_decision: ValidationDecision,
        primary_method: str
    ) -> str:
        """Build reasoning for hybrid decision"""
        
        decision_text = "VALIDATE" if final_decision else "SKIP"
        
        if score_decision and rule_decision.should_validate:
            return f"{decision_text}: Both score-based ({primary_method}) and rule-based systems agree"
        elif score_decision:
            return f"{decision_text}: Score-based system triggered (rules: skip)"
        elif rule_decision.should_validate:
            return f"{decision_text}: Rule-based system triggered (score: skip)"
        else:
            return f"{decision_text}: Both systems agree - no validation needed"
    
    def update_threshold(self, new_threshold: float) -> None:
        """Update validation threshold for score-based system"""
        self.score_threshold = new_threshold
        app_logger.info(f"Validation threshold updated to {new_threshold}")
    
    def get_validation_stats(self, state: CeciliaState) -> Dict[str, Any]:
        """Get detailed validation statistics for debugging/monitoring"""
        score_result = self.score_engine.should_validate(state, self.score_threshold)
        rule_result = self.rule_engine.evaluate(state)
        
        return {
            "threshold": self.score_threshold,
            "score_system": {
                "score": score_result[1]["validation_score"],
                "triggered_conditions": score_result[1]["triggered_conditions"],
                "would_validate": score_result[0]
            },
            "rule_system": {
                "total_score": rule_result.total_score,
                "triggered_rules": [(r.reason, r.score) for r in rule_result.triggered_rules],
                "would_validate": rule_result.should_validate
            },
            "conversation_context": {
                "message_count": state.get("conversation_metrics", {}).get("message_count", 0),
                "current_stage": str(state.get("current_stage", "unknown")),
                "llm_confidence": state.get("llm_confidence", 1.0),
                "recovery_attempts": state.get("recovery_attempts", 0)
            }
        }


# Global instance for use across the application
kumon_validation_router = KumonValidationRouter(score_threshold=40.0)