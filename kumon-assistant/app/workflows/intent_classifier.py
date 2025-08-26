"""
Advanced Intent Classification Engine for Kumon Assistant

This module provides sophisticated intent classification with context awareness,
multi-turn conversation understanding, and intelligent routing decisions.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.dependencies import llm_service
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseMessage

from ..core.config import settings
from ..core.logger import app_logger
from ..services.business_metrics_service import track_response_time
from .states import ConversationState, ConversationStep, WorkflowStage


class IntentCategory(Enum):
    """Main intent categories"""

    GREETING = "greeting"
    INFORMATION_REQUEST = "information_request"
    SCHEDULING = "scheduling"
    CLARIFICATION = "clarification"
    OBJECTION = "objection"
    DECISION = "decision"
    SMALL_TALK = "small_talk"
    COMPLAINT = "complaint"
    PRICE_NEGOTIATION = "price_negotiation"
    TECHNICAL_ISSUE = "technical_issue"


class IntentSubcategory(Enum):
    """Detailed intent subcategories"""

    # Greeting subcategories
    INITIAL_GREETING = "initial_greeting"
    NAME_PROVIDING = "name_providing"
    INTEREST_DECLARATION = "interest_declaration"

    # Information subcategories
    PROGRAM_MATHEMATICS = "program_mathematics"
    PROGRAM_PORTUGUESE = "program_portuguese"
    PROGRAM_ENGLISH = "program_english"
    PRICING_GENERAL = "pricing_general"
    PRICING_SPECIFIC = "pricing_specific"
    METHODOLOGY_GENERAL = "methodology_general"
    UNIT_INFO = "unit_info"
    SUCCESS_STORIES = "success_stories"

    # Scheduling subcategories
    DIRECT_BOOKING = "direct_booking"
    AVAILABILITY_CHECK = "availability_check"
    TIME_PREFERENCE = "time_preference"
    RESCHEDULE_REQUEST = "reschedule_request"
    CANCEL_REQUEST = "cancel_request"

    # Clarification subcategories
    GENERAL_CONFUSION = "general_confusion"
    CONCEPTUAL_CONFUSION = "conceptual_confusion"
    PROCEDURAL_CONFUSION = "procedural_confusion"
    TECHNICAL_CONFUSION = "technical_confusion"


@dataclass
class IntentResult:
    """Result of intent classification"""

    category: IntentCategory
    subcategory: Optional[IntentSubcategory]
    confidence: float
    context_entities: Dict[str, Any] = field(default_factory=dict)
    requires_clarification: bool = False
    suggested_responses: List[str] = field(default_factory=list)
    routing_decision: Optional[str] = None
    context_continuation: bool = False


@dataclass
class ConversationContext:
    """Enhanced conversation context tracking"""

    mentioned_programs: Set[str] = field(default_factory=set)
    mentioned_prices: Set[str] = field(default_factory=set)
    mentioned_names: Set[str] = field(default_factory=set)
    current_topic: Optional[str] = None
    last_agent_action: Optional[str] = None
    user_interest_level: float = 0.5  # 0-1 scale
    confusion_indicators: List[str] = field(default_factory=list)
    decision_indicators: List[str] = field(default_factory=list)


class AdvancedIntentClassifier:
    """
    Advanced intent classifier with contextual understanding

    This classifier goes beyond simple keyword matching to understand
    user intent in the context of the ongoing conversation.
    """

    def __init__(self, llm_service_instance=None):
        # LLM service is optional - classifier works with pattern matching even without LLM
        self.llm_service_instance = llm_service_instance
        self.llm = llm_service_instance

        # Intent patterns with context awareness
        self.intent_patterns = self._build_intent_patterns()

        # Entity extraction patterns
        self.entity_patterns = self._build_entity_patterns()

        # Context tracking
        self.active_contexts: Dict[str, ConversationContext] = {}

        if llm_service_instance:
            app_logger.info("Advanced Intent Classifier initialized with LLM support")
        else:
            app_logger.info("Advanced Intent Classifier initialized (pattern matching only)")

    def _build_intent_patterns(self) -> Dict[IntentCategory, Dict]:
        """Build comprehensive intent patterns with context"""
        return {
            IntentCategory.GREETING: {
                "patterns": [
                    r"\b(oi|olá|hello|hi|bom\s+dia|boa\s+tarde|boa\s+noite)\b",
                    r"\b(me\s+chamo|meu\s+nome\s+[éeE]|sou\s+o?a?)\s+([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})",
                    r"\b(primeira\s+vez|primeiro\s+contato|conhecer\s+o\s+kumon)\b",
                    r"\b(gostaria\s+de\s+saber|quero\s+informações)\b",
                ],
                "context_indicators": ["new_conversation", "name_exchange"],
                "confidence_boost": 0.2,
            },
            IntentCategory.INFORMATION_REQUEST: {
                "patterns": [
                    r"\b(matemática|math|cálculo|números?|conta)\b",
                    r"\b(português|port|leitura|escrita|redação|texto)\b",
                    r"\b(inglês|english|idioma)\b",
                    r"\b(preço|valor|custa|quanto|investimento|mensalidade)\b",
                    r"\b(como\s+funciona|metodologia|método|ensino)\b",
                    r"\b(onde\s+fica|endereço|localização|unidade)\b",
                    r"\b(resultado|melhora|progresso|funciona\s+mesmo)\b",
                ],
                "subcategory_mapping": {
                    "matemática": IntentSubcategory.PROGRAM_MATHEMATICS,
                    "português": IntentSubcategory.PROGRAM_PORTUGUESE,
                    "preço": IntentSubcategory.PRICING_GENERAL,
                    "metodologia": IntentSubcategory.METHODOLOGY_GENERAL,
                },
                "context_continuation": True,
            },
            IntentCategory.SCHEDULING: {
                "patterns": [
                    r"\b(agendar|marcar|schedule|appointment)\b",
                    r"\b(visita|apresentação|conhecer\s+a\s+unidade)\b",
                    r"\b(quando|horário|disponível|livre)\b",
                    r"\b(manhã|tarde|morning|afternoon)\b",
                    r"\b(segunda|terça|quarta|quinta|sexta)\b",
                    r"\b(cancelar|remarcar|mudar\s+horário)\b",
                ],
                "urgency_indicators": ["hoje", "amanhã", r"essa\s+semana", "urgente"],
                "time_indicators": ["manhã", "tarde", "horário", "disponível"],
            },
            IntentCategory.CLARIFICATION: {
                "patterns": [
                    r"\b(não\s+entendi|confuso|confusa|what|huh)\b",
                    r"\b(pode\s+repetir|de\s+novo|again)\b",
                    r"\b(como\s+assim|o\s+que\s+significa)\b",
                    r"\?{2,}",  # Multiple question marks
                    r"\b(explica\s+melhor|mais\s+detalhes)\b",
                ],
                "confusion_levels": {
                    "high": [r"muito\s+confuso", r"não\s+entendo\s+nada"],
                    "medium": ["confuso", r"não\s+entendi"],
                    "low": [r"pode\s+repetir", r"como\s+assim"],
                },
            },
            IntentCategory.OBJECTION: {
                "patterns": [
                    r"\b(caro|expensive|muito\s+dinheiro)\b",
                    r"\b(longe|distante|far)\b",
                    r"\b(não\s+posso|can't|cannot)\b",
                    r"\b(difícil|complicado|hard|difficult)\b",
                    r"\b(não\s+tenho\s+tempo|busy)\b",
                ],
                "objection_types": {
                    "price": ["caro", "dinheiro", "expensive"],
                    "location": ["longe", "distante", "far"],
                    "capability": ["difícil", "complicado", "hard"],
                    "time": ["tempo", "busy", "ocupado"],
                },
            },
            IntentCategory.DECISION: {
                "patterns": [
                    r"\b(quero|want|vou\s+fazer)\b",
                    r"\b(interessado|interested|gostei)\b",
                    r"\b(vamos\s+em\s+frente|let's\s+go)\b",
                    r"\b(concordo|aceito|topo)\b",
                    r"\b(fechado|combinado|deal)\b",
                ],
                "commitment_levels": {
                    "high": ["quero", r"vou\s+fazer", "fechado"],
                    "medium": ["interessado", "gostei"],
                    "low": ["talvez", r"vou\s+pensar"],
                },
            },
        }

    def _build_entity_patterns(self) -> Dict[str, List[str]]:
        """Build entity extraction patterns"""
        return {
            "person_names": [
                r"\b([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*)\b"
            ],
            "ages": [r"\b(\d{1,2})\s+anos?\b", r"\bidade\s+(\d{1,2})\b"],
            "times": [r"\b(manhã|tarde|morning|afternoon)\b", r"\b(\d{1,2}h?\d{0,2})\b"],
            "programs": [r"\b(matemática|português|inglês|math|portuguese|english)\b"],
            "prices": [r"\b(r\$?\s*\d+(?:,\d{2})?)\b", r"\b(\d+\s+reais?)\b"],
        }

    async def classify_intent(
        self, message: str, conversation_state: ConversationState
    ) -> IntentResult:
        """
        Classify intent with full contextual understanding

        Args:
            message: User's message
            conversation_state: Current conversation state

        Returns:
            IntentResult: Comprehensive intent analysis
        """
        try:
            app_logger.info(f"Classifying intent for message: {message[:50]}...")
            start_time = datetime.now()

            # Get or create conversation context with safe access
            phone_number = conversation_state.get("phone_number", "unknown")
            context = self._get_conversation_context(phone_number, conversation_state)

            # Step 1: Rule-based classification
            rule_based_result = self._classify_with_rules(message, context)

            # Step 2: LLM-enhanced classification
            llm_enhanced_result = await self._enhance_with_llm(
                message, context, rule_based_result, conversation_state
            )

            # Step 3: Context integration
            final_result = self._integrate_context(llm_enhanced_result, context, conversation_state)

            # Step 4: Update context
            self._update_context(phone_number, context, final_result, message)

            # Step 5: Track performance metrics
            response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            await track_response_time(
                response_time_ms,
                {
                    "component": "intent_classifier",
                    "category": final_result.category.value,
                    "confidence": final_result.confidence,
                    "phone_number": phone_number[-4:] if len(phone_number) > 4 else "****",
                },
            )

            app_logger.info(
                f"Intent classified: {final_result.category.value} "
                f"({final_result.confidence:.2f})"
            )

            return final_result

        except Exception as e:
            app_logger.error(f"Error in intent classification: {e}")
            # Return fallback classification
            return IntentResult(
                category=IntentCategory.CLARIFICATION,
                subcategory=IntentSubcategory.TECHNICAL_CONFUSION,
                confidence=0.5,
                requires_clarification=True,
            )

    def _get_conversation_context(
        self, phone_number: str, state: ConversationState
    ) -> ConversationContext:
        """Get or create conversation context"""
        if phone_number not in self.active_contexts:
            self.active_contexts[phone_number] = ConversationContext()

        context = self.active_contexts[phone_number]

        # Update context from state - direct access to avoid property issues
        collected_data = state.get("collected_data", {})

        # Add names if available
        parent_name = collected_data.get("parent_name")
        if parent_name:
            context.mentioned_names.add(parent_name)

        child_name = collected_data.get("child_name")
        if child_name:
            context.mentioned_names.add(child_name)

        # Add programs if available
        programs = (
            collected_data.get("programs_of_interest")
            or collected_data.get("programs_interested")
            or []
        )
        if programs:
            context.mentioned_programs.update(programs)

        # Get stage safely from state
        current_stage = state.get("stage") or state.get("current_stage")
        current_step = state.get("step") or state.get("current_step", ConversationStep.WELCOME)

        context.current_topic = (
            current_stage.value
            if hasattr(current_stage, "value")
            else str(current_stage) if current_stage else "unknown"
        )
        context.last_agent_action = (
            current_step.value if hasattr(current_step, "value") else str(current_step)
        )

        return context

    def _classify_with_rules(self, message: str, context: ConversationContext) -> IntentResult:
        """Rule-based intent classification"""
        message_lower = message.lower().strip()
        best_match = None
        best_confidence = 0.0

        # Extract entities first
        entities = self._extract_entities(message)

        # Check each intent category
        for category, config in self.intent_patterns.items():
            confidence = 0.0
            matched_patterns = []

            # Check patterns
            for pattern in config["patterns"]:
                if re.search(pattern, message_lower):
                    confidence += 0.3
                    matched_patterns.append(pattern)

            # Context boost
            if config.get("context_continuation") and context.current_topic:
                if category.value in context.current_topic:
                    confidence += config.get("confidence_boost", 0.1)

            # Entity boost
            if entities:
                if category == IntentCategory.GREETING and "person_names" in entities:
                    confidence += 0.2
                elif category == IntentCategory.INFORMATION_REQUEST and "programs" in entities:
                    confidence += 0.2
                elif category == IntentCategory.SCHEDULING and "times" in entities:
                    confidence += 0.2

            # Update best match
            if confidence > best_confidence:
                best_confidence = confidence
                subcategory = self._determine_subcategory(category, message_lower, entities)
                best_match = IntentResult(
                    category=category,
                    subcategory=subcategory,
                    confidence=confidence,
                    context_entities=entities,
                    context_continuation=config.get("context_continuation", False),
                )

        # Default fallback
        if not best_match or best_confidence < 0.3:
            best_match = IntentResult(
                category=IntentCategory.CLARIFICATION,
                subcategory=IntentSubcategory.GENERAL_CONFUSION,
                confidence=0.5,
                requires_clarification=True,
            )

        return best_match

    def _extract_entities(self, message: str) -> Dict[str, List[str]]:
        """Extract entities from message"""
        entities = {}

        for entity_type, patterns in self.entity_patterns.items():
            matches = []
            for pattern in patterns:
                found = re.findall(pattern, message, re.IGNORECASE)
                matches.extend(found)

            if matches:
                entities[entity_type] = list(set(matches))  # Remove duplicates

        return entities

    def _determine_subcategory(
        self, category: IntentCategory, message: str, entities: Dict[str, List[str]]
    ) -> Optional[IntentSubcategory]:
        """Determine subcategory based on category and content"""
        if category == IntentCategory.GREETING:
            if "person_names" in entities:
                return IntentSubcategory.NAME_PROVIDING
            elif any(word in message for word in ["kumon", "informação", "saber"]):
                return IntentSubcategory.INTEREST_DECLARATION
            else:
                return IntentSubcategory.INITIAL_GREETING

        elif category == IntentCategory.INFORMATION_REQUEST:
            if "matemática" in message or "math" in message:
                return IntentSubcategory.PROGRAM_MATHEMATICS
            elif "português" in message or "port" in message:
                return IntentSubcategory.PROGRAM_PORTUGUESE
            elif "preço" in message or "valor" in message:
                return IntentSubcategory.PRICING_GENERAL
            elif "metodologia" in message or "como funciona" in message:
                return IntentSubcategory.METHODOLOGY_GENERAL
            else:
                return None

        elif category == IntentCategory.SCHEDULING:
            if "times" in entities or any(word in message for word in ["manhã", "tarde"]):
                return IntentSubcategory.TIME_PREFERENCE
            elif "agendar" in message or "marcar" in message:
                return IntentSubcategory.DIRECT_BOOKING
            elif "disponível" in message or "quando" in message:
                return IntentSubcategory.AVAILABILITY_CHECK
            else:
                return None

        return None

    async def _enhance_with_llm(
        self,
        message: str,
        context: ConversationContext,
        rule_result: IntentResult,
        conversation_state: ConversationState,
    ) -> IntentResult:
        """Enhance classification using LLM for complex cases"""
        # Only use LLM for ambiguous cases or low confidence
        if rule_result.confidence >= 0.7:
            return rule_result

        # Check if LLM service is available
        if not self.llm:
            # Try to get LLM service lazily if not initialized
            try:
                from ..core.unified_service_resolver import unified_service_resolver

                self.llm = await unified_service_resolver.get_service("llm_service")
                self.llm_service_instance = self.llm
                if self.llm:
                    app_logger.info("LLM service acquired dynamically for intent enhancement")
            except Exception as e:
                app_logger.debug(f"LLM service not available for enhancement: {e}")

        # If still no LLM, return pattern matching result
        if not self.llm:
            app_logger.debug(
                f"Returning pattern-based classification (confidence: {rule_result.confidence})"
            )
            return rule_result

        try:
            # Build context for LLM
            context_str = self._build_context_string(context, conversation_state)

            classification_prompt = ChatPromptTemplate.from_messages(
                [
                    (
                        "system",
                        """Você é um classificador de intenções para o Kumon Assistant.

                Analise a mensagem do usuário e classifique a intenção considerando:
                1. O contexto da conversa
                2. O estágio atual
                3. O histórico de mensagens

                Categorias principais:
                - greeting: saudações, apresentação
                - information_request: pedidos de informação sobre programas, preços, metodologia
                - scheduling: agendamentos, horários, disponibilidade
                - clarification: confusão, pedidos de esclarecimento
                - objection: objeções sobre preço, localização, dificuldade
                - decision: decisões positivas, interesse em prosseguir

                Retorne apenas o nome da categoria em lowercase.""",
                    ),
                    (
                        "human",
                        """
                Contexto da conversa:
                {context}

                Classificação inicial: {initial_category} (confiança: {confidence})

                Mensagem do usuário: "{message}"

                Qual é a intenção principal?
                """,
                    ),
                ]
            )

            llm_response = await self.llm.ainvoke(
                classification_prompt.format_messages(
                    context=context_str,
                    initial_category=rule_result.category.value,
                    confidence=rule_result.confidence,
                    message=message,
                )
            )

            # Parse LLM response
            llm_category_str = llm_response.content.strip().lower()

            # Try to match to known categories
            for category in IntentCategory:
                if category.value == llm_category_str:
                    # Enhance confidence if LLM agrees
                    if category == rule_result.category:
                        rule_result.confidence = min(0.95, rule_result.confidence + 0.2)
                    else:
                        # LLM disagrees, create new result with moderate confidence
                        rule_result = IntentResult(
                            category=category,
                            subcategory=self._determine_subcategory(
                                category, message.lower(), rule_result.context_entities
                            ),
                            confidence=0.7,
                            context_entities=rule_result.context_entities,
                            context_continuation=rule_result.context_continuation,
                        )
                    break

            return rule_result

        except Exception as e:
            app_logger.error(f"LLM enhancement failed: {e}")
            return rule_result

    def _build_context_string(self, context: ConversationContext, state: ConversationState) -> str:
        """Build context string for LLM"""
        context_parts = []

        if context.mentioned_programs:
            context_parts.append(f"Programas mencionados: {', '.join(context.mentioned_programs)}")

        if context.mentioned_names:
            context_parts.append(f"Nomes mencionados: {', '.join(context.mentioned_names)}")

        if context.current_topic:
            context_parts.append(f"Tópico atual: {context.current_topic}")

        context_parts.append(
            f"Estágio: {state.get('stage', state.get('current_stage', 'unknown')).value if hasattr(state.get('stage', state.get('current_stage', 'unknown')), 'value') else state.get('stage', state.get('current_stage', 'unknown'))}"
        )
        context_parts.append(
            f"Passo: {state.get('step', state.get('current_step', 'unknown')).value if hasattr(state.get('step', state.get('current_step', 'unknown')), 'value') else state.get('step', state.get('current_step', 'unknown'))}"
        )

        # Add recent message history
        if state["messages"]:
            recent_messages = state["messages"][-3:]  # Last 3 messages
            context_parts.append("Últimas mensagens:")
            for msg in recent_messages:
                context_parts.append(f"- {msg['role']}: {msg['content'][:50]}...")

        return "\n".join(context_parts)

    def _integrate_context(
        self, result: IntentResult, context: ConversationContext, state: ConversationState
    ) -> IntentResult:
        """Integrate conversation context into the result"""
        # Add routing decision based on intent and context
        if result.category == IntentCategory.INFORMATION_REQUEST:
            if result.subcategory == IntentSubcategory.PROGRAM_MATHEMATICS:
                result.routing_decision = "information"
            elif result.subcategory == IntentSubcategory.PRICING_GENERAL:
                result.routing_decision = "information"
            else:
                result.routing_decision = "information"

        elif result.category == IntentCategory.SCHEDULING:
            result.routing_decision = "scheduling"

        elif result.category == IntentCategory.GREETING:
            current_stage = state.get("stage") or state.get("current_stage")
            if current_stage == WorkflowStage.GREETING:
                result.routing_decision = "greeting"
            else:
                # User greeting in middle of conversation - acknowledge and continue
                stage_value = (
                    current_stage.value if hasattr(current_stage, "value") else str(current_stage)
                )
                result.routing_decision = stage_value

        elif result.category == IntentCategory.CLARIFICATION:
            result.routing_decision = "fallback"
            result.requires_clarification = True

        else:
            # Default to current stage
            current_stage = state.get("stage") or state.get("current_stage", "unknown")
            stage_value = (
                current_stage.value if hasattr(current_stage, "value") else str(current_stage)
            )
            result.routing_decision = stage_value

        return result

    def _update_context(
        self, phone_number: str, context: ConversationContext, result: IntentResult, message: str
    ) -> None:
        """Update conversation context based on classification result"""
        # Update entities mentioned
        if result.context_entities:
            if "person_names" in result.context_entities:
                context.mentioned_names.update(result.context_entities["person_names"])
            if "programs" in result.context_entities:
                context.mentioned_programs.update(result.context_entities["programs"])

        # Update interest level based on intent
        if result.category == IntentCategory.DECISION:
            context.user_interest_level = min(1.0, context.user_interest_level + 0.2)
        elif result.category == IntentCategory.OBJECTION:
            context.user_interest_level = max(0.0, context.user_interest_level - 0.1)
        elif result.category == IntentCategory.INFORMATION_REQUEST:
            context.user_interest_level = min(1.0, context.user_interest_level + 0.1)

        # Track confusion indicators
        if result.category == IntentCategory.CLARIFICATION:
            context.confusion_indicators.append(message[:50])
            # Keep only last 3 confusion indicators
            context.confusion_indicators = context.confusion_indicators[-3:]

        # Update current topic
        if result.subcategory:
            context.current_topic = result.subcategory.value

    def get_context_summary(self, phone_number: str) -> Dict[str, Any]:
        """Get summary of conversation context for debugging"""
        if phone_number not in self.active_contexts:
            return {"status": "no_context"}

        context = self.active_contexts[phone_number]
        return {
            "mentioned_programs": list(context.mentioned_programs),
            "mentioned_names": list(context.mentioned_names),
            "current_topic": context.current_topic,
            "user_interest_level": context.user_interest_level,
            "confusion_count": len(context.confusion_indicators),
            "last_agent_action": context.last_agent_action,
        }


# Global instance removed, will be initialized on startup
