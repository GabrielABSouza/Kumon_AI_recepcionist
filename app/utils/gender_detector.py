"""
Gender Detection Utility for Dynamic Template Adaptation

Detects gender context from conversation to adapt pronouns and articles dynamically.
"""

import re
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class GenderContext:
    """Gender context for template variable replacement"""
    gender_pronoun: str          # dele/dela/dele(a)
    gender_article: str          # o/a/a(o) 
    gender_possessive: str       # seu/sua/seu(a)
    gender_child_term: str       # filho/filha/criança
    confidence: float            # 0.0 to 1.0
    detected_method: str         # name_analysis, keywords, neutral


class GenderDetector:
    """Detects gender context from conversation messages and names"""
    
    def __init__(self):
        # Common Brazilian male names
        self.male_names = {
            "joão", "pedro", "lucas", "matheus", "gabriel", "rafael", "guilherme", 
            "bruno", "andré", "felipe", "carlos", "daniel", "fernando", "ricardo",
            "thiago", "leonardo", "marcos", "antonio", "rodrigo", "eduardo", "diego"
        }
        
        # Common Brazilian female names  
        self.female_names = {
            "maria", "ana", "juliana", "fernanda", "amanda", "gabriela", "rafaela",
            "carolina", "beatriz", "leticia", "camila", "isabela", "larissa", "patricia",
            "mariana", "natalia", "bruna", "carla", "daniela", "vanessa", "priscila"
        }
        
        # Gender indicator patterns
        self.male_patterns = [
            r'\bmeu filho\b', r'\bo menino\b', r'\bele\b', r'\bgaroto\b',
            r'\bfilho\b(?!\s*dele)', r'\bpara ele\b', r'\bdeleb'
        ]
        
        self.female_patterns = [
            r'\bminha filha\b', r'\ba menina\b', r'\bela\b', r'\bgarota\b', 
            r'\bfilha\b(?!\s*dele)', r'\bpara ela\b', r'\bdela\b'
        ]

    def detect_gender_context(
        self, 
        conversation_state: Dict,
        student_name: Optional[str] = None
    ) -> GenderContext:
        """
        Detect gender context from conversation state and student name
        
        Args:
            conversation_state: Current conversation context
            student_name: Student name if available
            
        Returns:
            GenderContext with appropriate variables
        """
        
        # Priority 1: Analyze student name if available
        if student_name:
            gender_from_name = self._analyze_name_gender(student_name)
            if gender_from_name:
                return gender_from_name
        
        # Priority 2: Analyze conversation messages for gender keywords
        messages = conversation_state.get("messages", [])
        gender_from_keywords = self._analyze_keyword_patterns(messages)
        if gender_from_keywords:
            return gender_from_keywords
            
        # Priority 3: Check for any name mentioned in conversation
        gender_from_conversation = self._analyze_conversation_names(messages)
        if gender_from_conversation:
            return gender_from_conversation
            
        # Fallback: Neutral context
        return self._neutral_context()

    def _analyze_name_gender(self, name: str) -> Optional[GenderContext]:
        """Analyze gender from student name"""
        clean_name = name.lower().strip()
        first_name = clean_name.split()[0] if clean_name else ""
        
        if first_name in self.male_names:
            return GenderContext(
                gender_pronoun="ele",
                gender_article="o", 
                gender_possessive="seu",
                gender_child_term="filho",
                confidence=0.8,
                detected_method="name_analysis"
            )
        elif first_name in self.female_names:
            return GenderContext(
                gender_pronoun="ela",
                gender_article="a",
                gender_possessive="sua", 
                gender_child_term="filha",
                confidence=0.8,
                detected_method="name_analysis"
            )
        
        return None

    def _analyze_keyword_patterns(self, messages: list) -> Optional[GenderContext]:
        """Analyze gender from keyword patterns in messages"""
        
        all_text = " ".join([
            self._get_message_content(msg).lower()
            for msg in messages 
            if self._get_message_role(msg) == "user"
        ])
        
        male_matches = sum(1 for pattern in self.male_patterns if re.search(pattern, all_text, re.IGNORECASE))
        female_matches = sum(1 for pattern in self.female_patterns if re.search(pattern, all_text, re.IGNORECASE))
        
        if male_matches > female_matches and male_matches > 0:
            return GenderContext(
                gender_pronoun="ele",
                gender_article="o",
                gender_possessive="seu", 
                gender_child_term="filho",
                confidence=min(0.9, 0.6 + (male_matches * 0.1)),
                detected_method="keywords"
            )
        elif female_matches > male_matches and female_matches > 0:
            return GenderContext(
                gender_pronoun="ela",
                gender_article="a",
                gender_possessive="sua",
                gender_child_term="filha", 
                confidence=min(0.9, 0.6 + (female_matches * 0.1)),
                detected_method="keywords"
            )
            
        return None

    def _analyze_conversation_names(self, messages: list) -> Optional[GenderContext]:
        """Extract and analyze names mentioned in conversation"""
        
        all_text = " ".join([
            self._get_message_content(msg)
            for msg in messages 
            if self._get_message_role(msg) == "user"
        ])
        
        # Look for name patterns
        name_patterns = [
            r'\bchama ([A-Z][a-z]+)\b',
            r'\bnome (?:é|eh) ([A-Z][a-z]+)\b', 
            r'\bé o ([A-Z][a-z]+)\b',
            r'\bé a ([A-Z][a-z]+)\b'
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, all_text, re.IGNORECASE)
            for match in matches:
                gender_context = self._analyze_name_gender(match)
                if gender_context:
                    gender_context.confidence *= 0.7  # Lower confidence for extracted names
                    gender_context.detected_method = "conversation_names"
                    return gender_context
        
        return None

    def _neutral_context(self) -> GenderContext:
        """Return neutral gender context as fallback"""
        return GenderContext(
            gender_pronoun="ele(a)",
            gender_article="a criança", 
            gender_possessive="seu(a)",
            gender_child_term="criança",
            confidence=0.3,
            detected_method="neutral"
        )

    def get_template_variables(
        self, 
        conversation_state: Dict,
        student_name: Optional[str] = None,
        confidence_threshold: float = 0.5
    ) -> Dict[str, str]:
        """
        Get template variables for gender-aware responses
        
        Args:
            conversation_state: Current conversation context
            student_name: Student name if available
            confidence_threshold: Minimum confidence for gender detection (default 0.5)
        
        Returns dictionary ready for template formatting
        Only returns gender variables if confidence meets threshold
        """
        # Check data sufficiency before attempting detection
        has_sufficient_data = self._has_sufficient_data(conversation_state, student_name)
        
        if not has_sufficient_data:
            # Return empty dict when insufficient data
            # This allows the template system to use neutral fallbacks
            return {}
        
        context = self.detect_gender_context(conversation_state, student_name)
        
        # Only return gender variables if confidence meets threshold
        if context.confidence < confidence_threshold:
            # For low confidence, return neutral or empty
            if context.detected_method == "neutral":
                # For explicitly neutral context, return empty to avoid gender assumptions
                return {}
            # Otherwise return neutral forms
            return {
                "gender_pronoun": "ele(a)",
                "gender_article": "a criança", 
                "gender_possessive": "seu(a)",
                "gender_child_term": "criança",
                "gender_self_suffix": "o(a)",
                "gender_confidence": context.confidence,
                "gender_method": "low_confidence"
            }
        
        return {
            "gender_pronoun": context.gender_pronoun,
            "gender_article": context.gender_article, 
            "gender_possessive": context.gender_possessive,
            "gender_child_term": context.gender_child_term,
            "gender_self_suffix": "o" if context.gender_pronoun == "ele" else "a" if context.gender_pronoun == "ela" else "o(a)",
            "gender_confidence": context.confidence,
            "gender_method": context.detected_method
        }
    
    def _get_message_content(self, msg) -> str:
        """Safely extract message content from both dict and LangChain BaseMessage objects"""
        if hasattr(msg, "content"):
            # LangChain BaseMessage object (HumanMessage, AIMessage, etc.)
            return msg.content or ""
        elif isinstance(msg, dict):
            # Dictionary format
            return msg.get("content", "")
        else:
            # Fallback for unknown types
            return str(msg) if msg else ""
    
    def _get_message_role(self, msg) -> str:
        """Safely extract message role from both dict and LangChain BaseMessage objects"""
        if hasattr(msg, "type"):
            # LangChain BaseMessage object - map types to roles
            message_type = getattr(msg, "type", "").lower()
            if "human" in message_type:
                return "user"
            elif "ai" in message_type:
                return "assistant"
            else:
                return message_type
        elif isinstance(msg, dict):
            # Dictionary format
            return msg.get("role", "")
        else:
            # Fallback
            return ""
    
    def _has_sufficient_data(self, conversation_state: Dict, student_name: Optional[str] = None) -> bool:
        """
        Check if we have sufficient data for reliable gender detection
        
        Returns:
            True if we have enough data, False otherwise
        """
        # Check if we have explicit gender preference
        collected_data = conversation_state.get("collected_data", {})
        if collected_data.get("preferred_pronoun"):
            return True
        
        # Check if we have a meaningful student name (not placeholder)
        if student_name:
            # Skip placeholder values
            placeholders = ["seu(a) filho(a)", "criança", "filho(a)", "[child_name]"]
            if student_name.lower().strip() not in placeholders and len(student_name.strip()) > 2:
                return True
        
        # Check if we have substantial conversation history with gender indicators
        messages = conversation_state.get("messages", [])
        user_messages = [msg for msg in messages if self._get_message_role(msg) == "user"]
        
        # Need at least 2 user messages with meaningful content
        if len(user_messages) >= 2:
            total_content = " ".join([self._get_message_content(msg) for msg in user_messages])
            # Check for explicit gender mentions
            if any(pattern in total_content.lower() for pattern in ["meu filho", "minha filha", "ele é", "ela é"]):
                return True
        
        # No sufficient data
        return False


# Global instance
gender_detector = GenderDetector()