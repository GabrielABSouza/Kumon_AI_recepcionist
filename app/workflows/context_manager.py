"""
Context Memory Manager for Kumon Assistant

This module manages conversation context, resolves references, maintains topic threads,
and provides intelligent context-aware conversation continuity.
"""

import re
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from ..core.logger import app_logger
from .states import ConversationState, WorkflowStage, ConversationStep


class ReferenceType(Enum):
    """Types of references that can appear in conversation"""
    ANAPHORIC = "anaphoric"  # "isso", "aquilo", "ele"
    CATAPHORIC = "cataphoric"  # forward references
    DEICTIC = "deictic"  # "este", "esse", "aquele"
    ELLIPTICAL = "elliptical"  # implicit references


class TopicTransition(Enum):
    """Types of topic transitions"""
    CONTINUATION = "continuation"  # Same topic
    ELABORATION = "elaboration"  # Expanding on topic
    DIGRESSION = "digression"  # Side topic
    RETURN = "return"  # Back to previous topic
    NEW_TOPIC = "new_topic"  # Completely new topic


@dataclass
class Reference:
    """A reference found in conversation"""
    text: str
    type: ReferenceType
    resolved_entity: Optional[str] = None
    confidence: float = 0.0
    position: int = 0


@dataclass
class ConversationTopic:
    """A topic in the conversation"""
    name: str
    entities: Set[str] = field(default_factory=set)
    keywords: Set[str] = field(default_factory=set)
    first_mentioned: datetime = field(default_factory=datetime.now)
    last_mentioned: datetime = field(default_factory=datetime.now)
    mention_count: int = 0
    importance_score: float = 0.0


@dataclass
class ContextMemory:
    """Memory structure for conversation context"""
    phone_number: str
    topics: Dict[str, ConversationTopic] = field(default_factory=dict)
    entities: Dict[str, Any] = field(default_factory=dict)
    recent_mentions: List[Tuple[str, datetime]] = field(default_factory=list)
    topic_stack: List[str] = field(default_factory=list)  # Topic history
    current_focus: Optional[str] = None
    conversation_flow: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class ConversationContextManager:
    """
    Manages conversation context and reference resolution
    
    This class provides sophisticated context management including:
    - Reference resolution ("isso" -> "programa de matemática")  
    - Topic tracking and transitions
    - Entity persistence across messages
    - Context-aware response generation
    """
    
    def __init__(self):
        # Active conversation contexts
        self.contexts: Dict[str, ContextMemory] = {}
        
        # Reference patterns for Portuguese
        self.reference_patterns = self._build_reference_patterns()
        
        # Topic keywords for classification
        self.topic_keywords = self._build_topic_keywords()
        
        # Entity patterns
        self.entity_patterns = self._build_entity_patterns()
        
        # Cleanup interval (remove old contexts)
        self.context_ttl = timedelta(hours=24)
        
        app_logger.info("Context Memory Manager initialized")
    
    def _build_reference_patterns(self) -> Dict[ReferenceType, List[str]]:
        """Build reference resolution patterns"""
        return {
            ReferenceType.ANAPHORIC: [
                r"\b(isso|isto|aquilo)\b",
                r"\b(ele|ela|eles|elas)\b", 
                r"\b(o\s+que|aquele\s+que|essa\s+que)\b",
                r"\b(lá|ali|aí)\b"
            ],
            ReferenceType.DEICTIC: [
                r"\b(este|esta|estes|estas)\b",
                r"\b(esse|essa|esses|essas)\b",
                r"\b(aquele|aquela|aqueles|aquelas)\b"
            ],
            ReferenceType.ELLIPTICAL: [
                r"^\s*(quanto\s+custa)\??\s*$",  # "Quanto custa?" without object
                r"^\s*(como\s+funciona)\??\s*$",  # "Como funciona?" without subject
                r"^\s*(onde\s+fica)\??\s*$",      # "Onde fica?" without object
                r"^\s*(quando)\??\s*$"            # "Quando?" without context
            ]
        }
    
    def _build_topic_keywords(self) -> Dict[str, Set[str]]:
        """Build topic classification keywords"""
        return {
            "mathematics": {
                "matemática", "math", "cálculo", "números", "conta", "operações",
                "álgebra", "geometria", "aritmética", "mathematical"
            },
            "portuguese": {
                "português", "portuguese", "leitura", "escrita", "redação", "texto",
                "gramática", "literatura", "interpretação", "compreensão"
            },
            "english": {
                "inglês", "english", "idioma", "language", "vocabulary", "grammar"
            },
            "pricing": {
                "preço", "valor", "custa", "quanto", "investimento", "mensalidade",
                "price", "cost", "fee", "payment", "taxa", "matrícula"
            },
            "methodology": {
                "metodologia", "método", "como funciona", "ensino", "aprendizado",
                "pedagógico", "didático", "educational", "learning", "teaching"
            },
            "scheduling": {
                "agendar", "marcar", "horário", "visita", "apresentação", "appointment",
                "schedule", "booking", "disponibilidade", "tempo", "quando"
            },
            "unit_info": {
                "unidade", "endereço", "localização", "onde fica", "location",
                "address", "vila a", "kumon vila a"
            }
        }
    
    def _build_entity_patterns(self) -> Dict[str, str]:
        """Build entity extraction patterns"""
        return {
            "person_name": r"\b([A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,}(?:\s+[A-ZÁÊÉÔÕÂÎÇÜ][a-záêéôõâîçü]{2,})*)\b",
            "age": r"\b(\d{1,2})\s+anos?\b",
            "time_period": r"\b(manhã|tarde|noite|morning|afternoon|evening)\b",
            "weekday": r"\b(segunda|terça|quarta|quinta|sexta|sábado|domingo)\b",
            "program_name": r"\b(programa\s+de\s+)?(matemática|português|inglês)\b",
            "price_value": r"\br?\$?\s*(\d+(?:,\d{2})?)\s*(?:reais?|dollars?)?\b"
        }
    
    def get_or_create_context(self, phone_number: str) -> ContextMemory:
        """Get or create context memory for a conversation"""
        if phone_number not in self.contexts:
            self.contexts[phone_number] = ContextMemory(phone_number=phone_number)
            app_logger.info(f"Created new context for {phone_number}")
        
        # Update last accessed time
        self.contexts[phone_number].updated_at = datetime.now()
        return self.contexts[phone_number]
    
    def resolve_references(
        self, 
        message: str, 
        conversation_state: ConversationState
    ) -> Tuple[str, List[Reference]]:
        """
        Resolve references in the message
        
        Args:
            message: User's message potentially containing references
            conversation_state: Current conversation state
            
        Returns:
            Tuple of (resolved_message, found_references)
        """
        try:
            context = self.get_or_create_context(conversation_state["phone_number"])
            resolved_message = message
            found_references = []
            
            # Find all references
            for ref_type, patterns in self.reference_patterns.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, message, re.IGNORECASE)
                    for match in matches:
                        reference = Reference(
                            text=match.group(),
                            type=ref_type,
                            position=match.start()
                        )
                        
                        # Try to resolve the reference
                        resolved_entity = self._resolve_reference(
                            reference, context, conversation_state
                        )
                        
                        if resolved_entity:
                            reference.resolved_entity = resolved_entity
                            reference.confidence = 0.8  # High confidence for resolved refs
                            
                            # Replace in message
                            resolved_message = resolved_message.replace(
                                reference.text, 
                                resolved_entity, 
                                1  # Replace only first occurrence
                            )
                        
                        found_references.append(reference)
            
            app_logger.info(f"Resolved {len(found_references)} references")
            return resolved_message, found_references
            
        except Exception as e:
            app_logger.error(f"Error resolving references: {e}")
            return message, []
    
    def _resolve_reference(
        self, 
        reference: Reference, 
        context: ContextMemory, 
        conversation_state: ConversationState
    ) -> Optional[str]:
        """Resolve a specific reference to its entity"""
        try:
            ref_text = reference.text.lower().strip()
            
            # Anaphoric references ("isso", "aquilo")
            if reference.type == ReferenceType.ANAPHORIC:
                if ref_text in ["isso", "isto"]:
                    # Resolve to most recent topic or entity
                    if context.recent_mentions:
                        return context.recent_mentions[-1][0]
                    elif context.current_focus:
                        return context.current_focus
                
                elif ref_text in ["aquilo"]:
                    # Resolve to earlier mention
                    if len(context.recent_mentions) >= 2:
                        return context.recent_mentions[-2][0]
                
                elif ref_text in ["ele", "ela"]:
                    # Resolve to person mentioned
                    for entity_name, entity_data in context.entities.items():
                        if entity_data.get("type") == "person":
                            return entity_name
            
            # Deictic references ("esse programa", "aquele valor")
            elif reference.type == ReferenceType.DEICTIC:
                # Extract the noun following the deictic
                match = re.search(r"(esse|essa|este|esta|aquele|aquela)\s+(\w+)", 
                                ref_text)
                if match:
                    noun = match.group(2)
                    # Find the most recent entity of this type
                    for topic_name, topic in context.topics.items():
                        if noun in topic.keywords:
                            return f"{noun} de {topic_name}"
            
            # Elliptical references (missing object/subject)
            elif reference.type == ReferenceType.ELLIPTICAL:
                if ref_text.startswith("quanto custa"):
                    # Default to current focus or recent program mention
                    if context.current_focus:
                        return f"quanto custa o {context.current_focus}"
                    elif "mathematics" in context.topics:
                        return "quanto custa o programa de matemática"
                    elif "portuguese" in context.topics:
                        return "quanto custa o programa de português"
                
                elif ref_text.startswith("como funciona"):
                    if context.current_focus:
                        return f"como funciona o {context.current_focus}"
                    else:
                        return "como funciona a metodologia Kumon"
                
                elif ref_text.startswith("onde fica"):
                    return "onde fica a unidade Kumon Vila A"
                
                elif ref_text.startswith("quando"):
                    return "quando posso agendar uma visita"
            
            return None
            
        except Exception as e:
            app_logger.error(f"Error resolving specific reference: {e}")
            return None
    
    def detect_topic_transition(
        self, 
        message: str, 
        conversation_state: ConversationState
    ) -> TopicTransition:
        """
        Detect type of topic transition in the conversation
        
        Args:
            message: Current user message
            conversation_state: Current conversation state
            
        Returns:
            TopicTransition: Type of transition detected
        """
        try:
            context = self.get_or_create_context(conversation_state["phone_number"])
            current_topics = self._extract_topics_from_message(message)
            
            # No current focus - new topic
            if not context.current_focus:
                return TopicTransition.NEW_TOPIC
            
            # Check if current message relates to current focus
            if context.current_focus in current_topics:
                # Check if expanding or continuing
                if len(current_topics) > 1:
                    return TopicTransition.ELABORATION
                else:
                    return TopicTransition.CONTINUATION
            
            # Check if returning to previous topic
            for topic_name in current_topics:
                if topic_name in context.topic_stack[:-1]:  # Previous topics
                    return TopicTransition.RETURN
            
            # Check if it's a digression (related but different)
            current_stage = conversation_state["stage"].value
            message_topics = set(current_topics)
            stage_topics = self._get_stage_related_topics(current_stage)
            
            if message_topics.intersection(stage_topics):
                return TopicTransition.DIGRESSION
            
            # Completely new topic
            return TopicTransition.NEW_TOPIC
            
        except Exception as e:
            app_logger.error(f"Error detecting topic transition: {e}")
            return TopicTransition.CONTINUATION
    
    def _extract_topics_from_message(self, message: str) -> List[str]:
        """Extract topics mentioned in the message"""
        message_lower = message.lower()
        found_topics = []
        
        for topic_name, keywords in self.topic_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    found_topics.append(topic_name)
                    break  # Found this topic, move to next
        
        return found_topics
    
    def _get_stage_related_topics(self, stage: str) -> Set[str]:
        """Get topics related to a conversation stage"""
        stage_topics = {
            "greeting": {"unit_info"},
            "information": {"mathematics", "portuguese", "english", "pricing", "methodology"},
            "scheduling": {"scheduling", "unit_info"},
            "fallback": set(self.topic_keywords.keys())  # All topics available
        }
        
        return stage_topics.get(stage, set())
    
    def update_context_from_message(
        self, 
        message: str, 
        conversation_state: ConversationState,
        detected_topics: Optional[List[str]] = None
    ) -> None:
        """
        Update context memory based on new message
        
        Args:
            message: User's message
            conversation_state: Current conversation state  
            detected_topics: Optional pre-detected topics
        """
        try:
            context = self.get_or_create_context(conversation_state["phone_number"])
            
            # Extract topics if not provided
            if detected_topics is None:
                detected_topics = self._extract_topics_from_message(message)
            
            # Extract entities
            entities = self._extract_entities_from_message(message)
            
            # Update topics
            for topic_name in detected_topics:
                if topic_name not in context.topics:
                    context.topics[topic_name] = ConversationTopic(name=topic_name)
                
                topic = context.topics[topic_name]
                topic.last_mentioned = datetime.now()
                topic.mention_count += 1
                topic.importance_score += 0.1  # Increase importance
                
                # Update recent mentions
                context.recent_mentions.append((topic_name, datetime.now()))
            
            # Update entities
            for entity_type, entity_value in entities.items():
                context.entities[entity_value] = {
                    "type": entity_type,
                    "mentioned_at": datetime.now(),
                    "message": message[:100]  # Store context
                }
            
            # Update current focus (most important recent topic)
            if detected_topics:
                # Focus on the most recently mentioned topic with highest importance
                best_topic = max(
                    detected_topics, 
                    key=lambda t: context.topics[t].importance_score 
                    if t in context.topics else 0
                )
                context.current_focus = best_topic
                
                # Update topic stack
                if best_topic not in context.topic_stack[-1:]:  # Not already at top
                    context.topic_stack.append(best_topic)
                    # Keep stack size manageable
                    context.topic_stack = context.topic_stack[-5:]
            
            # Clean up old mentions (keep last 10)
            context.recent_mentions = context.recent_mentions[-10:]
            
            # Log conversation flow
            context.conversation_flow.append({
                "timestamp": datetime.now().isoformat(),
                "message": message[:100],
                "topics": detected_topics,
                "entities": entities,
                "stage": conversation_state["stage"].value,
                "step": conversation_state["step"].value
            })
            
            context.updated_at = datetime.now()
            app_logger.info(f"Updated context for {conversation_state['phone_number']}: "
                          f"topics={detected_topics}, focus={context.current_focus}")
            
        except Exception as e:
            app_logger.error(f"Error updating context: {e}")
    
    def _extract_entities_from_message(self, message: str) -> Dict[str, str]:
        """Extract entities from message using patterns"""
        entities = {}
        
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, message, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[-1]  # Get last group if tuple
                if match and len(match.strip()) > 1:
                    entities[entity_type] = match.strip()
        
        return entities
    
    def get_context_summary(self, phone_number: str) -> Dict[str, Any]:
        """Get comprehensive context summary for debugging/analysis"""
        if phone_number not in self.contexts:
            return {"status": "no_context"}
        
        context = self.contexts[phone_number]
        return {
            "current_focus": context.current_focus,
            "active_topics": list(context.topics.keys()),
            "topic_stack": context.topic_stack,
            "entities": list(context.entities.keys()),
            "recent_mentions": [(name, ts.isoformat()) for name, ts in context.recent_mentions[-5:]],
            "conversation_length": len(context.conversation_flow),
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat()
        }
    
    def maintain_context_continuity(
        self, 
        conversation_state: ConversationState
    ) -> Dict[str, Any]:
        """
        Maintain context continuity across conversation turns
        
        Returns context hints for response generation
        """
        try:
            context = self.get_or_create_context(conversation_state["phone_number"])
            
            continuity_hints = {
                "current_focus": context.current_focus,
                "recent_topics": [name for name, _ in context.recent_mentions[-3:]],
                "entities_to_reference": {},
                "topic_transition_type": None,
                "context_references": []
            }
            
            # Add entity references that should be maintained
            for entity_name, entity_data in context.entities.items():
                if entity_data["type"] in ["person_name", "program_name"]:
                    continuity_hints["entities_to_reference"][entity_name] = entity_data["type"]
            
            # Detect if we need to remind about context
            if len(context.conversation_flow) > 3:
                last_topics = [
                    entry["topics"] for entry in context.conversation_flow[-3:] 
                    if entry["topics"]
                ]
                if last_topics:
                    continuity_hints["context_references"] = [
                        topic for topics in last_topics for topic in topics
                    ]
            
            return continuity_hints
            
        except Exception as e:
            app_logger.error(f"Error maintaining context continuity: {e}")
            return {}
    
    def cleanup_old_contexts(self) -> None:
        """Clean up contexts older than TTL"""
        try:
            current_time = datetime.now()
            to_remove = []
            
            for phone_number, context in self.contexts.items():
                if current_time - context.updated_at > self.context_ttl:
                    to_remove.append(phone_number)
            
            for phone_number in to_remove:
                del self.contexts[phone_number]
                app_logger.info(f"Cleaned up old context for {phone_number}")
            
            if to_remove:
                app_logger.info(f"Cleaned up {len(to_remove)} old contexts")
                
        except Exception as e:
            app_logger.error(f"Error cleaning up contexts: {e}")


# Global instance
context_manager = ConversationContextManager()