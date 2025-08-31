"""
Intelligent Threshold System with Integrated Fallback Handlers

This module provides sophisticated threshold management with hierarchical fallback
handlers that incorporate intelligent recovery strategies.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..core.logger import app_logger
from ..prompts.manager import prompt_manager
from ..core.state.models import CeciliaState as ConversationState, ConversationStage, ConversationStep
from .contracts import (
    ThresholdDecision, 
    STAGE_PREREQUISITES, 
    STAGE_CONFIDENCE_MULTIPLIERS,
    CONFIDENCE_WEIGHTS,
    check_mandatory_data_requirements,
    get_fallback_stage_for_missing_data
)

from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseMessage


@dataclass
class ThresholdRule:
    """Regra de threshold com ação associada"""
    name: str
    threshold: float
    action: str
    next_penalty: float = 0.0
    description: str = ""


class ConfusionType(Enum):
    """Tipos de confusão detectados"""
    CONCEPTUAL = "conceptual"    # Não entende conceito
    PROCEDURAL = "procedural"    # Não sabe como prosseguir  
    TECHNICAL = "technical"      # Problema técnico
    GENERAL = "general"          # Confusão geral


class IntelligentThresholdSystem:
    """
    Sistema inteligente de thresholds com handlers hierárquicos
    
    Incorpora a lógica de fallback inteligente diretamente nos handlers
    para decisões mais sofisticadas e recovery strategies específicas.
    """
    
    def __init__(self):
        # Configuração de regras hierárquicas
        self.rules = [
            ThresholdRule(
                name="high_confidence", 
                threshold=0.85, 
                action="proceed",
                description="Alta confiança, prosseguir"
            ),
            ThresholdRule(
                name="llm_enhancement", 
                threshold=0.7, 
                action="enhance_with_llm",
                description="Confiança moderada, usar LLM"
            ),
            ThresholdRule(
                name="intelligent_fallback_l1", 
                threshold=0.3, 
                action="fallback_level1",
                next_penalty=0.05,
                description="Fallback inteligente nível 1"
            ),
            ThresholdRule(
                name="intelligent_fallback_l2", 
                threshold=0.25, 
                action="fallback_level2",
                next_penalty=0.05,
                description="Fallback inteligente nível 2"
            ),
            ThresholdRule(
                name="human_handoff", 
                threshold=0.2, 
                action="escalate_human",
                description="Escalação para humano"
            )
        ]
        
        # Registry de handlers
        self.action_handlers = {
            "proceed": self._proceed,
            "enhance_with_llm": self._enhance_with_llm,
            "fallback_level1": self._apply_fallback_level1,
            "fallback_level2": self._apply_fallback_level2,
            "escalate_human": self._escalate_to_human
        }
        
        # Multiplicadores por estágio da conversa - usando enums canônicos
        self.stage_multipliers = STAGE_CONFIDENCE_MULTIPLIERS
        
        # Padrões de confusão (extraído do intelligent_fallback)
        self.confusion_patterns = {
            ConfusionType.CONCEPTUAL: [
                r"\b(não\s+entendo|don't\s+understand|confuso|confusa)\b",
                r"\b(o\s+que\s+é|what\s+is|que\s+significa)\b",
                r"\b(como\s+assim|what\s+do\s+you\s+mean)\b",
                r"\b(não\s+sei\s+o\s+que|don't\s+know\s+what)\b",
            ],
            ConfusionType.PROCEDURAL: [
                r"\b(como\s+faço|how\s+do\s+i|próximo\s+passo|next\s+step)\b",
                r"\b(agora\s+o\s+que|what\s+now|e\s+então)\b",
                r"\b(o\s+que\s+preciso|what\s+do\s+i\s+need)\b",
                r"\b(por\s+onde\s+começo|where\s+do\s+i\s+start)\b",
            ],
            ConfusionType.TECHNICAL: [
                r"\b(erro|error|bug|problema\s+técnico)\b",
                r"\b(não\s+funciona|not\s+working|broken)\b",
                r"\b(site\s+fora|down|offline|carregando|loading)\b",
            ]
        }
        
        # LLM service cache
        self.llm_service_cache = None
        
        app_logger.info("Intelligent Threshold System initialized")

    async def decide(
        self,
        intent_confidence: float,
        pattern_confidence: float, 
        current_stage: ConversationStage,
        collected_data: Dict[str, Any],
        target_intent: str = "unknown"
    ) -> ThresholdDecision:
        """
        Main decision method following orchestration_flow.md spec
        
        PRIORITY 1: Mandatory data collection (overrides everything)
        PRIORITY 2: Confidence model + stage multipliers
        
        Args:
            intent_confidence: From IntentClassifier [0,1]
            pattern_confidence: From PatternScorer [0,1] 
            current_stage: Current conversation stage
            collected_data: Data collected so far
            target_intent: Target intent from classification
            
        Returns:
            ThresholdDecision with action and target_node
        """
        
        # PRIORITY 1: Check mandatory data requirements
        if target_intent in ["scheduling", "information", "confirmation"]:
            # Map intent to stage for prerequisite checking
            target_stage_map = {
                "scheduling": ConversationStage.SCHEDULING,
                "information": ConversationStage.INFORMATION_GATHERING,
                "confirmation": ConversationStage.CONFIRMATION
            }
            
            target_stage = target_stage_map.get(target_intent, current_stage)
            requirements_met, missing_fields = check_mandatory_data_requirements(
                target_stage, collected_data
            )
            
            if not requirements_met:
                fallback_stage = get_fallback_stage_for_missing_data(target_stage)
                
                # Structured telemetry for mandatory data override
                app_logger.info(
                    f"[THRESHOLD_ENGINE] Mandatory data collection override",
                    extra={
                        "component": "threshold_engine",
                        "operation": "mandatory_data_override",
                        "target_intent": target_intent,
                        "missing_fields": missing_fields,
                        "target_stage": target_stage.value,
                        "fallback_stage": fallback_stage.value,
                        "confidence_override": 1.0,
                        "intent_confidence": intent_confidence,
                        "pattern_confidence": pattern_confidence
                    }
                )
                
                return ThresholdDecision(
                    action="proceed",
                    target_node=fallback_stage.value,
                    final_confidence=1.0,  # Maximum confidence override
                    rule_applied="mandatory_data_collection_override",
                    reasoning=f"Missing required data for {target_intent}: {missing_fields}",
                    intent_confidence=intent_confidence,
                    pattern_confidence=pattern_confidence,
                    stage_override=True,
                    mandatory_data_override=True
                )
        
        # PRIORITY 2: Standard confidence model
        # Combine confidences with weights
        combined_confidence = (
            CONFIDENCE_WEIGHTS["intent"] * intent_confidence + 
            CONFIDENCE_WEIGHTS["pattern"] * pattern_confidence
        )
        
        # Apply stage multiplier
        stage_multiplier = self.stage_multipliers.get(current_stage, 1.0)
        
        # Calculate penalties from conversation state
        penalties = self._calculate_accumulated_penalties({"current_stage": current_stage})
        
        # Final effective confidence
        final_confidence = (combined_confidence * stage_multiplier) - penalties
        final_confidence = max(0.0, min(1.0, final_confidence))  # Clamp to [0,1]
        
        # Find applicable rule
        for rule in sorted(self.rules, key=lambda r: r.threshold, reverse=True):
            if final_confidence >= rule.threshold:
                # Map target_intent to target_node
                target_node = self._map_intent_to_node(target_intent, current_stage)
                
                # Structured telemetry for threshold decision
                app_logger.info(
                    f"[THRESHOLD_ENGINE] Threshold decision made",
                    extra={
                        "component": "threshold_engine",
                        "operation": "threshold_decision",
                        "rule_applied": rule.name,
                        "target_node": target_node,
                        "final_confidence": final_confidence,
                        "rule_threshold": rule.threshold,
                        "intent_confidence": intent_confidence,
                        "pattern_confidence": pattern_confidence,
                        "combined_confidence": combined_confidence,
                        "stage_multiplier": stage_multiplier,
                        "penalties_applied": penalties,
                        "current_stage": current_stage.value,
                        "target_intent": target_intent
                    }
                )
                
                return ThresholdDecision(
                    action=rule.action,
                    target_node=target_node,
                    final_confidence=final_confidence,
                    rule_applied=rule.name,
                    reasoning=f"Combined confidence {final_confidence:.2f} >= {rule.threshold:.2f}",
                    intent_confidence=intent_confidence,
                    pattern_confidence=pattern_confidence,
                    stage_override=False,
                    mandatory_data_override=False
                )
        
        # Fallback to human handoff
        return ThresholdDecision(
            action="escalate_human",
            target_node="human_handoff",
            final_confidence=final_confidence,
            rule_applied="confidence_too_low",
            reasoning=f"Final confidence {final_confidence:.2f} below all thresholds",
            intent_confidence=intent_confidence,
            pattern_confidence=pattern_confidence,
            stage_override=False,
            mandatory_data_override=False
        )
        
    def _map_intent_to_node(self, intent: str, current_stage: ConversationStage) -> str:
        """Map intent classification to LangGraph node"""
        intent_to_node = {
            "greeting": "greeting",
            "information": "information", 
            "scheduling": "scheduling",
            "confirmation": "completed",
            "handoff": "human_handoff",
            "fallback": "fallback"
        }
        return intent_to_node.get(intent, "fallback")

    async def determine_action(
        self, 
        confidence: float, 
        conversation_state: ConversationState
    ) -> Tuple[str, ThresholdRule]:
        """
        Determina ação baseada em confidence e estado atual
        Retorna (action, rule_applied)
        """
        
        # Calcular confidence efetiva com multiplicadores e penalidades
        penalties = self._calculate_accumulated_penalties(conversation_state)
        stage_multiplier = self._get_stage_multiplier(conversation_state)
        effective_confidence = (confidence * stage_multiplier) - penalties
        
        # Encontrar regra aplicável (ordenadas por threshold desc)
        for rule in sorted(self.rules, key=lambda r: r.threshold, reverse=True):
            # Usar threshold original da regra (não modificado)
            
            if effective_confidence >= rule.threshold:
                app_logger.info(
                    f"Threshold rule applied: {rule.name} "
                    f"(effective_confidence: {effective_confidence:.2f}, "
                    f"rule_threshold: {rule.threshold:.2f})"
                )
                return rule.action, rule
        
        # Fallback para última regra (human handoff)
        return self.rules[-1].action, self.rules[-1]

    async def execute_action(
        self, 
        action: str, 
        rule: ThresholdRule,
        result, # IntentResult 
        conversation_state: ConversationState
    ):
        """Executa ação determinada através do handler registry"""
        
        handler = self.action_handlers.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}")
        
        # Aplicar penalidade se necessário
        if rule.next_penalty > 0:
            self._apply_penalty(conversation_state, rule.next_penalty)
        
        return await handler(result, conversation_state, rule)

    # ========== HANDLERS INTELIGENTES ==========

    async def _proceed(self, result, conversation_state: ConversationState, rule: ThresholdRule):
        """Handler para alta confiança - prosseguir normalmente"""
        app_logger.info(f"High confidence classification: {result.category.value}")
        return result

    async def _enhance_with_llm(self, result, conversation_state: ConversationState, rule: ThresholdRule):
        """
        Handler para enhancement com LLM usando abordagem context-based
        
        Integra com LLM service existente e aplica confidence boost baseado
        em contexto conversacional específico.
        """
        app_logger.info("Enhancing classification with LLM (context-based approach)")
        
        # Check if LLM service is available
        llm_service = await self._get_llm_service()
        if not llm_service:
            app_logger.debug("LLM service not available, applying minimal boost")
            return self._apply_minimal_boost(result)
        
        try:
            # Build enhanced context for LLM
            context_info = self._extract_conversation_context(conversation_state)
            
            # Create enhancement-focused prompt
            enhancement_prompt = self._build_enhancement_prompt(
                result, context_info, conversation_state
            )
            
            # Get LLM response
            llm_response = await llm_service.ainvoke(enhancement_prompt)
            
            # Parse and analyze LLM result
            llm_enhancement = self._parse_llm_enhancement(llm_response, result)
            
            # Apply context-based confidence calculation
            enhanced_result = self._apply_contextual_confidence_boost(
                result, conversation_state, llm_enhancement
            )
            
            app_logger.info(
                f"LLM enhancement applied: {result.confidence:.2f} -> {enhanced_result.confidence:.2f} "
                f"(strategy: {llm_enhancement.get('strategy', 'standard')})"
            )
            
            return enhanced_result
            
        except Exception as e:
            app_logger.error(f"LLM enhancement failed: {e}")
            return self._apply_minimal_boost(result)

    async def _apply_fallback_level1(self, result, conversation_state: ConversationState, rule: ThresholdRule):
        """
        Fallback inteligente nível 1 - Recuperação suave
        
        Analisa tipo de confusão e aplica estratégia específica de recuperação.
        """
        app_logger.info("Applying intelligent fallback level 1")
        
        # 1. Detectar tipo de confusão
        user_message = conversation_state.get("user_message", "")
        confusion_type = self._detect_confusion_type(user_message)
        
        # 2. Aplicar estratégia específica
        if confusion_type == ConfusionType.CONCEPTUAL:
            # Usuário não entende conceito - explicar de forma simples
            result.requires_clarification = True
            result.suggested_responses = [
                "Deixe-me explicar de forma mais simples sobre o Kumon... 😊",
                "O Kumon é um método de ensino que ajuda crianças e adultos a desenvolverem habilidades em matemática e português.",
                "Posso explicar mais detalhadamente sobre algum ponto específico?"
            ]
            
        elif confusion_type == ConfusionType.PROCEDURAL:
            # Usuário não sabe como prosseguir - dar opções claras
            result.requires_clarification = True
            result.suggested_responses = [
                "Para te ajudar melhor, você gostaria de:",
                "🔢 Saber mais sobre nossos programas",
                "📅 Agendar uma apresentação na unidade",
                "💰 Conhecer nossos valores"
            ]
            
        else:
            # Confusão geral - pedir clarificação gentil
            result.requires_clarification = True
            result.suggested_responses = [
                "Desculpe, não consegui entender bem sua mensagem.",
                "Pode reformular sua pergunta de forma mais específica? 😊"
            ]
        
        # 3. Atualizar confidence para refletir estratégia aplicada
        result.confidence = 0.6  # Confidence moderada após recovery
        
        app_logger.info(f"Applied level 1 fallback for {confusion_type.value} confusion")
        return result

    async def _apply_fallback_level2(self, result, conversation_state: ConversationState, rule: ThresholdRule):
        """
        Fallback inteligente nível 2 - Recuperação mais agressiva
        
        Estratégias mais diretas: opções múltiplas, redirecionamento claro.
        """
        app_logger.info("Applying intelligent fallback level 2")
        
        # Estratégia mais direta - menu de opções
        result.requires_clarification = True
        result.suggested_responses = [
            "Vou apresentar nossas principais opções para você escolher:",
            "",
            "1️⃣ **Programas do Kumon**: Matemática e Português",
            "2️⃣ **Agendar Apresentação**: Conhecer nossa unidade",
            "3️⃣ **Informações sobre Valores**: Investimento mensal",
            "4️⃣ **Localização e Horários**: Como nos encontrar",
            "",
            "Digite o **número** da opção que mais te interessa! 😊"
        ]
        
        # Confidence baixa para indicar que precisamos de input direto
        result.confidence = 0.5
        
        app_logger.info("Applied level 2 fallback with direct options menu")
        return result

    async def _escalate_to_human(self, result, conversation_state: ConversationState, rule: ThresholdRule):
        """Handler para escalação humana"""
        app_logger.info("Escalating to human due to low confidence")
        
        # Marcar para escalação humana
        result.requires_clarification = True
        result.suggested_responses = [
            "Vou conectá-lo com nossa equipe para um atendimento mais personalizado! 📞",
            "",
            "**WhatsApp direto**: (51) 99692-1999",
            "**Horário**: Segunda a sexta, 8h às 18h",
            "",
            "Nossa equipe poderá esclarecer todas suas dúvidas e agendar sua visita! 😊"
        ]
        
        # Sinalizar necessidade de handoff
        conversation_state["requires_human"] = True
        result.confidence = 0.1  # Confidence muito baixa
        
        return result

    # ========== MÉTODOS AUXILIARES ==========

    def _detect_confusion_type(self, message: str) -> ConfusionType:
        """Detecta tipo de confusão na mensagem do usuário"""
        message_lower = message.lower()
        
        # Verificar padrões de cada tipo
        for confusion_type, patterns in self.confusion_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return confusion_type
        
        return ConfusionType.GENERAL

    def _calculate_accumulated_penalties(self, conversation_state: ConversationState) -> float:
        """Calcula penalidades acumuladas do usuário"""
        try:
            metrics = conversation_state.get("metrics")
            if not metrics:
                return 0.0
            
            # Penalidade por confusões consecutivas
            confusion_penalty = getattr(metrics, 'consecutive_confusion', 0) * 0.05
            
            # Penalidade por tentativas falhas de clarificação
            clarification_penalty = getattr(metrics, 'clarification_attempts', 0) * 0.025
            
            total_penalty = -(confusion_penalty + clarification_penalty)
            return max(-0.2, total_penalty)  # Limitar penalidade máxima
            
        except Exception as e:
            app_logger.error(f"Error calculating penalties: {e}")
            return 0.0

    def _apply_penalty(self, conversation_state: ConversationState, penalty: float):
        """Aplicar penalidade ao estado da conversa"""
        try:
            metrics = conversation_state.get("conversation_metrics", {})
            if metrics:
                # Incrementar contador de confusão para aplicar penalidade na próxima
                current_confusion = metrics.get("consecutive_confusion", 0)
                metrics["consecutive_confusion"] = current_confusion + 1
                app_logger.info(f"Applied penalty: {penalty}, confusion count: {metrics['consecutive_confusion']}")
        except Exception as e:
            app_logger.error(f"Error applying penalty: {e}")

    def _get_stage_multiplier(self, conversation_state: ConversationState) -> float:
        """Obter multiplicador baseado no estágio da conversa"""
        try:
            stage = conversation_state.get("current_stage")
            if isinstance(stage, ConversationStage):
                return self.stage_multipliers.get(stage, 1.0)
            else:
                app_logger.warning(f"Invalid stage type: {type(stage)}, using default multiplier")
                return 1.0
            
        except Exception as e:
            app_logger.error(f"Error getting stage multiplier: {e}")
            return 1.0

    # ========== MÉTODOS AUXILIARES PARA LLM ENHANCEMENT ==========

    async def _get_llm_service(self):
        """Get LLM service with lazy loading and caching"""
        if self.llm_service_cache:
            return self.llm_service_cache
        
        try:
            from ..core.unified_service_resolver import unified_service_resolver
            self.llm_service_cache = await unified_service_resolver.get_service("llm_service")
            
            if self.llm_service_cache:
                app_logger.info("LLM service acquired for threshold enhancement")
            return self.llm_service_cache
            
        except Exception as e:
            app_logger.debug(f"LLM service not available: {e}")
            return None

    def _extract_conversation_context(self, conversation_state: ConversationState) -> Dict[str, Any]:
        """Extract relevant context information for LLM enhancement"""
        try:
            # Use CeciliaState structure
            metrics = conversation_state.get("conversation_metrics", {})
            stage = conversation_state.get("current_stage")
            validation = conversation_state.get("data_validation", {})
            
            return {
                "stage": stage.value if hasattr(stage, "value") else str(stage),
                "confusion_count": metrics.get("consecutive_confusion", 0),
                "message_count": metrics.get("message_count", 0),
                "clarification_attempts": len(validation.get("pending_confirmations", [])),
                "user_message": conversation_state.get("last_user_message", ""),
                "phone_number": conversation_state.get("phone_number", "unknown")[-4:]
            }
        except Exception as e:
            app_logger.error(f"Error extracting context: {e}")
            return {"stage": "unknown", "confusion_count": 0}

    def _build_enhancement_prompt(self, result, context_info: Dict[str, Any], conversation_state: ConversationState):
        """Build enhancement-focused prompt for LLM"""
        
        enhancement_prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                """Você está refinando uma classificação de intenção existente do Kumon Assistant.

                IMPORTANTE: Sua tarefa é MELHORAR uma classificação já existente, não classificar do zero.

                Categorias disponíveis:
                - greeting: saudações, apresentação, nomes
                - information_request: dúvidas sobre programas, preços, metodologia  
                - scheduling: agendamentos, horários, visitas
                - clarification: confusão, pedidos de esclarecimento
                - objection: objeções sobre preço, localização
                - decision: decisões positivas, interesse
                - complaint: reclamações, problemas

                Analise se a classificação inicial está correta ou se deve ser ajustada.
                Responda com: CONFIRMA [categoria] ou MUDA [categoria] [motivo_breve]"""
            ),
            (
                "human",
                """CLASSIFICAÇÃO INICIAL:
                Intent: {current_intent}
                Confidence: {current_confidence:.2f}
                
                CONTEXTO DA CONVERSA:
                - Estágio: {stage}
                - Confusões anteriores: {confusion_count}
                - Tentativas de clarificação: {clarification_attempts}
                
                MENSAGEM DO USUÁRIO:
                "{user_message}"
                
                Sua análise:"""
            )
        ])

        return enhancement_prompt.format_messages(
            current_intent=result.category.value,
            current_confidence=result.confidence,
            stage=context_info.get("stage", "unknown"),
            confusion_count=context_info.get("confusion_count", 0),
            clarification_attempts=context_info.get("clarification_attempts", 0),
            user_message=context_info.get("user_message", "")[:100]  # Limit message length
        )

    def _parse_llm_enhancement(self, llm_response, original_result) -> Dict[str, Any]:
        """Parse LLM response and extract enhancement information"""
        try:
            response_text = llm_response.content.strip().lower()
            
            if response_text.startswith("confirma"):
                return {
                    "agrees": True,
                    "new_category": None,
                    "reasoning": "LLM confirmed original classification",
                    "strategy": "confirmation",
                    "provides_clarification": False
                }
            
            elif response_text.startswith("muda"):
                # Extract new category from "MUDA [categoria] [motivo]"
                parts = response_text.split()
                if len(parts) >= 2:
                    new_category_str = parts[1]
                    reasoning = " ".join(parts[2:]) if len(parts) > 2 else "LLM suggested change"
                    
                    return {
                        "agrees": False,
                        "new_category": new_category_str,
                        "reasoning": reasoning,
                        "strategy": "category_change", 
                        "provides_clarification": True,
                        "high_confidence": len(reasoning) > 10  # More detailed reasoning = higher confidence
                    }
            
            # Fallback for unclear responses
            return {
                "agrees": True,
                "new_category": None,
                "reasoning": "LLM response unclear, keeping original",
                "strategy": "fallback",
                "provides_clarification": False
            }
            
        except Exception as e:
            app_logger.error(f"Error parsing LLM response: {e}")
            return {
                "agrees": True,
                "new_category": None,
                "reasoning": "Error parsing LLM response",
                "strategy": "error_fallback",
                "provides_clarification": False
            }

    def _apply_contextual_confidence_boost(
        self, 
        original_result, 
        conversation_state: ConversationState, 
        llm_enhancement: Dict[str, Any]
    ):
        """Apply context-based confidence boost (Approach 3)"""
        
        # Extract context
        context_info = self._extract_conversation_context(conversation_state)
        base_boost = 0.1  # Conservative base boost
        
        # Factors that increase confidence in LLM
        if context_info.get("confusion_count", 0) > 1:
            base_boost += 0.05  # LLM better for confusing cases
            app_logger.debug("Confidence boost: user confusion detected")
        
        if llm_enhancement.get("provides_clarification", False):
            base_boost += 0.05  # LLM provided useful explanation
            app_logger.debug("Confidence boost: LLM provided clarification")
        
        if llm_enhancement.get("high_confidence", False):
            base_boost += 0.05  # LLM was confident in its analysis
            app_logger.debug("Confidence boost: LLM high confidence")
        
        # Factors that decrease confidence in LLM
        if context_info.get("stage") == "greeting":
            base_boost -= 0.05  # Pattern matching better for greetings
            app_logger.debug("Confidence reduction: greeting stage")
        
        if context_info.get("message_count", 0) == 1:
            base_boost -= 0.03  # Pattern matching usually good for first messages
            app_logger.debug("Confidence reduction: first message")
        
        # Apply enhancement
        if llm_enhancement.get("agrees", True):
            # LLM confirms original classification
            new_confidence = min(0.85, original_result.confidence + base_boost)
            app_logger.info(f"LLM confirmed classification with boost: +{base_boost:.2f}")
            
        else:
            # LLM suggests different category
            new_category_str = llm_enhancement.get("new_category", "")
            
            # Try to map to actual IntentCategory
            from .intent_classifier import IntentCategory
            new_category = None
            for cat in IntentCategory:
                if cat.value == new_category_str:
                    new_category = cat
                    break
            
            if new_category:
                # Create new result with LLM suggestion
                original_result.category = new_category
                original_result.subcategory = None  # Reset subcategory
                new_confidence = 0.75 + (base_boost * 0.5)  # Base LLM confidence + context
                app_logger.info(f"LLM changed classification to {new_category.value}")
            else:
                # Invalid category, keep original with small boost
                new_confidence = min(0.65, original_result.confidence + 0.05)
                app_logger.warning(f"LLM suggested invalid category: {new_category_str}")
        
        # Never exceed reasonable limits
        original_result.confidence = max(0.1, min(0.95, new_confidence))
        return original_result

    def _apply_minimal_boost(self, result):
        """Apply minimal confidence boost when LLM not available"""
        result.confidence = min(0.65, result.confidence + 0.05)
        app_logger.info(f"Applied minimal boost: {result.confidence:.2f}")
        return result


# Instância global
intelligent_threshold_system = IntelligentThresholdSystem()