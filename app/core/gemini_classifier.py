"""
Minimal intent classifier using Gemini Flash.
Maps user message to one of the predefined intents.
"""
import os
import google.generativeai as genai
from enum import Enum
from typing import Tuple, Optional


class Intent(Enum):
    """Supported intents for the system."""
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    INFORMATION = "information"
    SCHEDULING = "scheduling"
    FALLBACK = "fallback"


class GeminiClassifier:
    """Simple intent classifier using Gemini Flash."""
    
    def __init__(self):
        # Configure Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        self.enabled = bool(api_key)
        
        if self.enabled:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        else:
            self.model = None
    
    def classify(self, text: str) -> Tuple[Intent, float]:
        """
        Classify user message into an intent.
        Returns (intent, confidence).
        """
        if not self.enabled:
            # Simple fallback classification for testing
            return self._simple_classify(text)
        
        prompt = self._build_prompt(text)
        
        try:
            response = self.model.generate_content(prompt)
            result = response.text.strip().lower()
            
            # Parse response
            intent, confidence = self._parse_response(result)
            return intent, confidence
            
        except Exception as e:
            print(f"Classification error: {e}")
            return Intent.FALLBACK, 0.0
    
    def _simple_classify(self, text: str) -> Tuple[Intent, float]:
        """Simple keyword-based classification for testing."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["oi", "olá", "bom dia", "boa tarde"]):
            return Intent.GREETING, 0.9
        elif any(word in text_lower for word in ["matricular", "matrícula", "inscrever"]):
            return Intent.QUALIFICATION, 0.85
        elif any(word in text_lower for word in ["método", "funciona", "kumon"]):
            return Intent.INFORMATION, 0.8
        elif any(word in text_lower for word in ["agendar", "visita", "horário"]):
            return Intent.SCHEDULING, 0.85
        else:
            return Intent.FALLBACK, 0.5
    
    def _build_prompt(self, text: str) -> str:
        """Build classification prompt from template."""
        # Load prompt template
        try:
            import os
            from pathlib import Path
            prompt_path = Path(__file__).parent.parent / "prompts" / "gemini_prompt.txt"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                template = f.read()
        except Exception:
            # Fallback prompt if file not found
            template = """Classifique a mensagem em: greeting, qualification, information, scheduling ou fallback.
Responda: categoria|confiança"""
        
        return f"{template}\n\nMensagem: \"{text}\""

    def _parse_response(self, response: str) -> Tuple[Intent, float]:
        """Parse Gemini response into intent and confidence."""
        try:
            parts = response.split("|")
            if len(parts) != 2:
                return Intent.FALLBACK, 0.0
            
            intent_str = parts[0].strip()
            confidence = float(parts[1].strip())
            
            # Map to Intent enum
            intent_map = {
                "greeting": Intent.GREETING,
                "qualification": Intent.QUALIFICATION,
                "information": Intent.INFORMATION,
                "scheduling": Intent.SCHEDULING,
                "fallback": Intent.FALLBACK
            }
            
            intent = intent_map.get(intent_str, Intent.FALLBACK)
            return intent, confidence
            
        except Exception:
            return Intent.FALLBACK, 0.0


# Global instance
classifier = GeminiClassifier()