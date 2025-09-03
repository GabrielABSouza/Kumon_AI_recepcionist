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
from ..core.state.models import CeciliaState as ConversationState, ConversationStage, ConversationStep
from .contracts import IntentResult, DeliveryPayload
from ..core.telemetry import TelemetryTracer, emit_intent_classification_event, generate_trace_id
from .pattern_scorer import PatternScorer
# Removed: intelligent_threshold_system - centralized in SmartRouter


class IntentCategory(Enum):
    """Main intent categories"""

    GREETING = "greeting"
    INFORMATION_REQUEST = "information_request"
    QUALIFICATION = "qualification"  # Data collection responses (names, ages, etc.)
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


# IntentResult now imported from contracts.py - using standardized contract


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

        # Entity extraction patterns moved to PatternScorer for centralization

        # Context tracking
        self.active_contexts: Dict[str, ConversationContext] = {}

        if llm_service_instance:
            app_logger.info("Advanced Intent Classifier initialized with LLM support")
        else:
            app_logger.info("Advanced Intent Classifier initialized (pattern matching only)")

    def _get_enum_value(self, enum_obj):
        """Safely extract value from enum (handle both Enum and string)"""
        if hasattr(enum_obj, 'value'):
            return enum_obj.value
        return str(enum_obj) if enum_obj else "unknown"

    def _build_delivery_payload(
        self, 
        category: str, 
        message: str, 
        conversation_state: ConversationState,
        slots: Dict[str, Any] = None
    ) -> DeliveryPayload:
        """Build delivery payload based on intent category and channel"""
        slots = slots or {}
        
        # Extract channel from state or default to whatsapp
        channel = conversation_state.get("channel", "whatsapp")
        
        # Build content based on category
        if category == "qualification":
            content = {
                "text": f"Obrigado pela informação! Vamos continuar com a qualificação.",
                "type": "qualification_response"
            }
        elif category == "information_request":
            content = {
                "text": f"Entendi sua solicitação de informações. Vou te explicar sobre o Kumon.",
                "type": "information_response"
            }
        elif category == "greeting":
            parent_name = slots.get("parent_name", "")
            if parent_name:
                content = {
                    "text": f"Olá, {parent_name}! Bem-vindo ao Kumon.",
                    "type": "personalized_greeting"
                }
            else:
                content = {
                    "text": "Olá! Bem-vindo ao Kumon. Como posso te ajudar?",
                    "type": "standard_greeting"
                }
        elif category == "scheduling":
            content = {
                "text": "Vamos agendar sua aula experimental. Que dia e horário seria melhor para você?",
                "type": "scheduling_request"
            }
        else:
            # Default fallback content
            content = {
                "text": "Entendi. Como posso te ajudar com mais informações sobre o Kumon?",
                "type": "default_response"
            }
            
        return DeliveryPayload(
            channel=channel,
            content=content,
            attachments=[],
            meta={
                "intent_category": category,
                "extracted_slots": slots,
                "timestamp": datetime.now().isoformat()
            }
        )

    def _build_intent_patterns(self) -> Dict[IntentCategory, Dict]:
        """Build comprehensive intent patterns with context"""
        return {
            IntentCategory.GREETING: {
                "patterns": [
                    r"\b(oi|olá|hello|hi|bom\s+dia|boa\s+tarde|boa\s+noite)\b",
                    r"\b(buenos\s+dias|buenas\s+tardes|buenas\s+noches|hola)\b",
                    r"\b(me\s+chamo|meu\s+nome\s+[éeE]|sou\s+o?a?)\s+([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})",
                    r"\b(primeira\s+vez|primeiro\s+contato)\b",
                    r"\b(meu\s+filho|minha\s+filha|tem\s+\d+\s+anos|está\s+no|nome\s+é|estuda|escola)\b",
                ],
                "context_indicators": ["new_conversation", "name_exchange"],
                "confidence_boost": 0.2,
            },
            IntentCategory.INFORMATION_REQUEST: {
                "patterns": [
                    r"\b(gostaria\s+de\s+saber|quero\s+informações|quero\s+conhecer)\b",
                    r"\b(conhecer\s+o\s+kumon|saber\s+mais|informações\s+sobre)\b",
                    r"\b(matemática|math|cálculo|números?|conta)\b",
                    r"\b(português|port|leitura|escrita|redação|texto)\b",
                    r"\b(inglês|english|idioma)\b",
                    r"\b(preço|valor|custa|quanto|investimento|mensalidade|quanto\s+custa)\b",
                    r"\b(como\s+funciona|metodologia|método|ensino|o\s+que\s+é|qual)\b",
                    r"\b(onde\s+fica|endereço|localização|unidade|telefone|horário\s+de\s+funcionamento)\b",
                    r"\b(resultado|melhora|progresso|funciona\s+mesmo)\b",
                    r"\b(dúvida|informação|explicar)\b",
                ],
                "subcategory_mapping": {
                    "matemática": IntentSubcategory.PROGRAM_MATHEMATICS,
                    "português": IntentSubcategory.PROGRAM_PORTUGUESE,
                    "preço": IntentSubcategory.PRICING_GENERAL,
                    "metodologia": IntentSubcategory.METHODOLOGY_GENERAL,
                },
                "context_continuation": True,
            },
            IntentCategory.QUALIFICATION: {
                "patterns": [
                    # Names (most common qualification response)
                    r"^[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*$",
                    # Ages
                    r"\b(\d{1,2})\s+(anos?|meses?)\b",
                    r"\b(idade\s+)?\d{1,2}\b",
                    # School grades/years
                    r"\b\d+[°ºª]?\s*(ano|série|grau)\b",
                    r"\b(fundamental|médio|ensino\s+médio)\b",
                    # Yes/No responses for qualification questions
                    r"^(sim|não|yes|no)$",
                    # Child information responses
                    r"\b(meu\s+filho|minha\s+filha|ele\s+tem|ela\s+tem)\b",
                ],
                "context_indicators": ["parent_name_collection", "child_name_collection", "age_collection", "grade_collection"],
                "confidence_boost": 0.3,
                "stage_specific": True,  # Only applies in QUALIFICATION stage
            },
            IntentCategory.SCHEDULING: {
                "patterns": [
                    r"\b(agendar|marcar|schedule|appointment)\b",
                    r"\b(visita|apresentação|conhecer\s+a\s+unidade|consulta)\b",
                    r"\b(quando|horário|disponível|livre|disponibilidade)\b",
                    r"\b(manhã|tarde|morning|afternoon)\b",
                    r"\b(segunda|terça|quarta|quinta|sexta)\b",
                    r"\b(cancelar|remarcar|mudar\s+horário)\b",
                    r"\b(quero\s+agendar|posso\s+marcar|tem\s+vaga)\b",
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
            IntentCategory.COMPLAINT: {
                "patterns": [
                    r"\b(reclamação|problema|insatisfeito|ruim|péssimo)\b",
                ],
                "severity_levels": {
                    "high": ["péssimo", "horrível", "terrível"],
                    "medium": ["ruim", "problema", "insatisfeito"],
                    "low": ["reclamação", "questão"],
                },
            },
        }

    # Entity patterns moved to PatternScorer for centralized management

    async def classify_intent(
        self, message: str, conversation_state: ConversationState
    ) -> IntentResult:
        """
        Classify intent with intelligent threshold system

        Args:
            message: User's message
            conversation_state: Current conversation state

        Returns:
            IntentResult: Comprehensive intent analysis with intelligent fallback
        """
        try:
            app_logger.info(f"Classifying intent for message: {message[:50]}...")
            start_time = datetime.now()

            # Get or create conversation context with safe access
            phone_number = conversation_state.get("phone_number", "unknown")
            context = self._get_conversation_context(phone_number, conversation_state)
            
            # Generate trace_id for telemetry
            trace_id = generate_trace_id()
            
            # Extract telemetry context
            current_stage = conversation_state.get("current_stage", "unknown")
            current_step = conversation_state.get("current_step", "unknown") 
            channel = conversation_state.get("channel", "whatsapp")

            # Step 1: Rule-based classification
            rule_based_result = self._classify_with_rules(message, context, conversation_state)

            # Step 2: Context integration (threshold processing moved to SmartRouter)
            final_result = self._integrate_context(rule_based_result, context, conversation_state)

            # Step 4: Update context
            self._update_context(phone_number, context, final_result, message)

            # Step 5: Track performance metrics
            response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            await track_response_time(
                response_time_ms,
                {
                    "component": "intent_classifier",
                    "category": final_result.category,
                    "confidence": final_result.confidence,
                    "phone_number": phone_number[-4:] if len(phone_number) > 4 else "****",
                },
            )

            app_logger.info(
                f"[INTENT_CLASSIFIER] Raw classification complete: {final_result.category} "
                f"(confidence: {final_result.confidence:.2f}) → sending to SmartRouter for threshold processing"
            )
            
            # Emit intent classification telemetry
            response_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            emit_intent_classification_event(
                trace_id=trace_id,
                node_id="intent_classifier",
                stage=str(current_stage),
                step=str(current_step),
                channel=channel,
                duration_ms=response_time_ms,
                intent_id=final_result.category,
                confidence=final_result.confidence,
                winning_rule=final_result.policy_action
            )

            return final_result

        except Exception as e:
            app_logger.error(f"Error in intent classification: {e}")
            # Return fallback classification with delivery payload
            delivery_payload = self._build_delivery_payload(
                "clarification", message, conversation_state, {"error": str(e)}
            )
            return IntentResult(
                category="clarification",
                subcategory="technical_confusion", 
                confidence=0.5,
                context_entities={"error": str(e)},
                delivery_payload=delivery_payload,
                slots={"error": str(e)}
            )

    # REMOVED: _classify_with_intelligent_thresholds()
    # Threshold processing centralized in SmartRouter to eliminate duplicate decisions
    # IntentClassifier now returns "raw" classification for SmartRouter to process

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

        from ..core.state.utils import safe_enum_value
        context.current_topic = safe_enum_value(current_stage) if current_stage else "unknown"
        context.last_agent_action = safe_enum_value(current_step) if current_step else "unknown"

        return context

    def _classify_with_rules(self, message: str, context: ConversationContext, state: ConversationState) -> IntentResult:
        """Rule-based intent classification with stage-aware logic"""
        message_lower = message.lower().strip()
        best_match = None
        best_confidence = 0.0

        # Extract entities using centralized PatternScorer
        from .pattern_scorer import PatternScorer
        pattern_scorer = PatternScorer()
        entities = pattern_scorer.extract_entities(message)

        # Get current stage from state (safely)
        current_stage = state.get("current_stage")
        from ..core.state.utils import safe_enum_value
        
        # Check each intent category
        for category, config in self.intent_patterns.items():
            confidence = 0.0
            matched_patterns = []
            
            # Use PatternScorer for pattern matching
            pattern_scorer = PatternScorer()
            route_patterns = pattern_scorer.route_patterns
            
            # Match against route patterns if available
            category_value = self._get_enum_value(category)
            
            # Map IntentCategory values to PatternScorer route_pattern keys
            category_mapping = {
                "information_request": "information",
                "qualification": "qualification",  # New category for data collection responses
                "greeting": "greeting",
                "scheduling": "scheduling", 
                "clarification": "clarification",
                "objection": "handoff",  # Map objection to handoff in PatternScorer
                "decision": "confirmation",  # Map decision to confirmation in PatternScorer
            }
            
            # Use mapped category name for route_patterns lookup
            route_category = category_mapping.get(category_value, category_value)
            if route_category in route_patterns:
                route_config = route_patterns[route_category]
                
                # STAGE-AWARE LOGIC: Prevent incorrect classification based on conversation stage
                if category_value == "greeting":
                    # Suppress greeting classification in non-greeting stages
                    current_stage_str = safe_enum_value(current_stage) if current_stage else "unknown"
                    
                    # CRITICAL FIX: Detect name pattern early to prevent greeting misclassification
                    name_pattern = r"^[A-ZÁÊÉÔÕÂÎÇÜ][a.záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*$"
                    is_name_response = re.match(name_pattern, message.strip())
                    
                    if current_stage and "greeting" not in current_stage_str.lower():
                        # User is NOT in greeting stage - reduce greeting score significantly
                        confidence += 0.05  # Very low score
                        matched_patterns = []
                        if is_name_response and "qualification" in current_stage_str.lower():
                            app_logger.info(f"[FIX] Name '{message}' in QUALIFICATION - suppressing greeting classification")
                    elif current_stage and "greeting" in current_stage_str.lower():
                        # Check if this looks like a name response
                        if is_name_response:
                            # This is a name response - very low greeting score
                            confidence += 0.1
                            matched_patterns = []
                        else:
                            base_score = pattern_scorer._calculate_base_pattern_score(
                                message_lower, route_config["patterns"], route_config["base_score"]
                            )
                            confidence += base_score
                            matched_patterns = [p for p in route_config["patterns"] if re.search(p, message_lower)]
                    else:
                        # No stage info or initial greeting - normal processing
                        base_score = pattern_scorer._calculate_base_pattern_score(
                            message_lower, route_config["patterns"], route_config["base_score"]
                        )
                        confidence += base_score
                        matched_patterns = [p for p in route_config["patterns"] if re.search(p, message_lower)]
                else:
                    base_score = pattern_scorer._calculate_base_pattern_score(
                        message_lower, route_config["patterns"], route_config["base_score"]
                    )
                    confidence += base_score
                    matched_patterns = [p for p in route_config["patterns"] if re.search(p, message_lower)]
                    
                    # STAGE-AWARE BOOSTS based on expected responses per stage
                    if current_stage:
                        stage_str = safe_enum_value(current_stage) if current_stage else "unknown"
                        app_logger.debug(f"[STAGE DEBUG] current_stage={current_stage}, stage_str={stage_str}, category={category_value}")
                        
                        # GREETING stage: Name responses boost information
                        if (route_category == "information" and 
                            "greeting" in stage_str.lower()):
                            name_pattern = r"^[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*$"
                            if re.match(name_pattern, message.strip()):
                                confidence += 0.6  # Strong boost for name responses
                                app_logger.info(f"[GREETING] Name '{message}' boosted information to {confidence}")
                        
                        # QUALIFICATION stage: Data collection responses should be classified as qualification
                        elif (route_category == "qualification" and 
                              "qualification" in stage_str.lower()):
                            # Check for name pattern (single name or full name)
                            name_pattern = r"^[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*$"
                            age_pattern = r"\b\d{1,2}\s*(anos?|meses)?\b"
                            grade_pattern = r"\b\d+[°ºª]?\s*(ano|série|grau)\b"
                            
                            # CRITICAL FIX: Recognize qualification responses in QUALIFICATION stage
                            if re.match(name_pattern, message.strip()):
                                confidence += 0.9  # VERY STRONG boost for name responses in QUALIFICATION
                                app_logger.info(f"[QUALIFICATION] Detected name response: {message} - boosting qualification to {confidence}")
                            elif re.search(age_pattern, message_lower) or re.search(grade_pattern, message_lower):
                                confidence += 0.7  # Strong boost for age/grade responses
                                app_logger.info(f"[QUALIFICATION] Age/grade response boosted to {confidence}")
                        
                        # QUALIFICATION stage: Name/Age/grade responses boost information (FALLBACK)
                        elif (route_category == "information" and 
                              "qualification" in stage_str.lower()):
                            # Check for name pattern (single name or full name)
                            name_pattern = r"^[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*$"
                            age_pattern = r"\b\d{1,2}\s*(anos?|meses)?\b"
                            grade_pattern = r"\b\d+[°ºª]?\s*(ano|série|grau)\b"
                            
                            # FALLBACK FIX: If qualification category doesn't work, boost information
                            if re.match(name_pattern, message.strip()):
                                confidence += 0.8  # STRONG boost for name responses in QUALIFICATION
                                app_logger.info(f"[QUALIFICATION FALLBACK] Detected name response: {message} - boosting information to {confidence}")
                            elif re.search(age_pattern, message_lower) or re.search(age_pattern, message_lower):
                                confidence += 0.5  # Boost for age/grade responses
                                app_logger.info(f"[QUALIFICATION FALLBACK] Age/grade response boosted to {confidence}")
                        
                        # SCHEDULING stage: Time/date responses boost scheduling
                        elif (route_category == "scheduling" and 
                              "SCHEDULING" in stage_str):
                            time_pattern = r"\b\d{1,2}[h:]\d{0,2}\b|\b(manhã|tarde|noite)\b"
                            date_pattern = r"\b(segunda|terça|quarta|quinta|sexta|sábado|domingo)\b"
                            availability_pattern = r"\b(sim|não|posso|disponível|livre)\b"
                            if (re.search(time_pattern, message_lower) or 
                                re.search(date_pattern, message_lower) or
                                re.search(availability_pattern, message_lower)):
                                confidence += 0.5  # Boost for scheduling responses
            else:
                # Fallback to original pattern matching for categories not in PatternScorer
                for pattern in config["patterns"]:
                    match = re.search(pattern, message_lower)
                    if match:
                        confidence += 0.6  # Base confidence for pattern match
                        matched_patterns.append(pattern)

            # Context boost
            if config.get("context_continuation") and context.current_topic:
                if self._get_enum_value(category) in context.current_topic:
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
                delivery_payload = self._build_delivery_payload(
                    self._get_enum_value(category), message, conversation_state, entities
                )
                best_match = IntentResult(
                    category=self._get_enum_value(category),
                    subcategory=self._get_enum_value(subcategory) if subcategory else None,
                    confidence=confidence,
                    context_entities=entities,
                    delivery_payload=delivery_payload,
                    slots=entities
                )

        # Default fallback - only if really no good match found
        if not best_match or best_confidence < 0.2:
            delivery_payload = self._build_delivery_payload(
                "clarification", message, conversation_state, {"fallback_reason": "low_confidence"}
            )
            best_match = IntentResult(
                category="clarification",
                subcategory="general_confusion",
                confidence=0.5,
                context_entities={"fallback_reason": "low_confidence"},
                delivery_payload=delivery_payload,
                slots={"fallback_reason": "low_confidence"}
            )

        return best_match

    # Pattern confidence calculation now handled by PatternScorer class

    # Entity extraction method moved to PatternScorer for centralized management

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
                    initial_category=rule_result.category,
                    confidence=rule_result.confidence,
                    message=message,
                )
            )

            # Parse LLM response
            llm_category_str = llm_response.content.strip().lower()

            # Try to match to known categories
            for category in IntentCategory:
                if self._get_enum_value(category) == llm_category_str:
                    # Enhance confidence if LLM agrees
                    if category == rule_result.category:
                        rule_result.confidence = min(0.95, rule_result.confidence + 0.2)
                    else:
                        # LLM disagrees, create new result with moderate confidence
                        delivery_payload = self._build_delivery_payload(
                            self._get_enum_value(category), message, conversation_state, rule_result.context_entities
                        )
                        rule_result = IntentResult(
                            category=self._get_enum_value(category),
                            subcategory=self._determine_subcategory(
                                category, message.lower(), rule_result.context_entities
                            ),
                            confidence=0.7,
                            context_entities=rule_result.context_entities,
                            delivery_payload=delivery_payload,
                            slots=rule_result.context_entities
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
            if current_stage == ConversationStage.GREETING:
                result.routing_decision = "greeting"
            else:
                # User greeting in middle of conversation - acknowledge and continue
                from ..core.state.utils import safe_enum_value
                stage_value = safe_enum_value(current_stage)
                result.routing_decision = stage_value

        elif result.category == IntentCategory.CLARIFICATION:
            result.routing_decision = "fallback"
            result.requires_clarification = True

        else:
            # Default to current stage
            current_stage = state.get("stage") or state.get("current_stage", "unknown")
            from ..core.state.utils import safe_enum_value
            stage_value = safe_enum_value(current_stage)
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
            context.current_topic = result.subcategory

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
