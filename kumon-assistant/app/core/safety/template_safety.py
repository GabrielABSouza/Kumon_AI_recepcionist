"""
Template Safety System - Prevents configuration templates from reaching users

CRITICAL: This module ensures internal configuration templates are never sent to users.
Multiple layers of protection against accidental template leakage.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TemplateSafetyFilter:
    """
    Multi-layer protection against sending configuration templates to users
    
    CRITICAL: Any template containing configuration directives should be blocked
    """
    
    def __init__(self):
        # Configuration template detection patterns
        self.config_patterns = [
            # Direct configuration keywords
            r'\b(?:DIRETRIZES|IMPORTANT[EA]?|OBRIGATÓR[IO]|NUNCA)\b',
            r'\b(?:Você é|VOCÊ É|Sempre|SEMPRE|Nunca|NUNCA)\s+(?:responda|mantenha|quebre)',
            
            # Template variable indicators (should never be shown to users)
            r'\{\{[\w_]+\}\}',
            r'\{[\w_]+\}',
            
            # System instructions
            r'personagem|identidade.*Cecília|CECÍLIA.*recepcionista',
            r'método.*educacional|MÉTODO.*EDUCACIONAL',
            
            # Template structure indicators
            r'RESPOSTA\s+OBRIGATÓRIA',
            r'Como.*ajudá.*hoje.*método',
            
            # Specific dangerous content from base template
            r'Sempre responda pergunta diretamente',
            r'Nunca refuse ajudar',
            r'Nunca quebre o personagem',
            r'Sempre mantenha identidade'
        ]
        
        # Compile patterns for performance
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.config_patterns]
        
        # Safe fallback templates for different contexts
        self.safe_fallbacks = {
            "greeting": "Olá! Bem-vindo ao Kumon Vila A! 😊\n\nMeu nome é Cecília. Como posso ajudá-lo hoje?",
            "information": "Ficou com alguma dúvida sobre o Kumon? Posso explicar melhor nosso método ou tirar outras questões!",
            "scheduling": "Vamos agendar sua visita ao Kumon Vila A! Qual seria o melhor horário para você?",
            "general": "Olá! Sou Cecília do Kumon Vila A. Como posso ajudá-lo hoje? 😊",
            "error": "Desculpe, houve um problema técnico. Entre em contato conosco:\n📞 (51) 99692-1999"
        }
    
    def is_configuration_template(self, template_content: str) -> bool:
        """
        Detect if template contains configuration directives
        
        Args:
            template_content: Template text to analyze
            
        Returns:
            True if template appears to be a configuration template
        """
        if not template_content:
            return False
            
        # Check against all config patterns
        for pattern in self.compiled_patterns:
            if pattern.search(template_content):
                logger.warning(f"🚨 Configuration template detected: {pattern.pattern}")
                return True
                
        return False
    
    def sanitize_template(self, template_content: str, context: str = "general") -> str:
        """
        Ensure template is safe for user consumption
        
        Args:
            template_content: Original template content
            context: Context for fallback selection (greeting, information, etc.)
            
        Returns:
            Safe template content or safe fallback
        """
        if not template_content:
            logger.warning("🚨 Empty template provided, using safe fallback")
            return self.safe_fallbacks.get(context, self.safe_fallbacks["general"])
        
        # Check if template is safe
        if self.is_configuration_template(template_content):
            logger.error(f"🚨 BLOCKED configuration template from reaching user. Context: {context}")
            logger.error(f"🚨 Blocked content preview: {template_content[:100]}...")
            
            # Return context-appropriate safe fallback
            return self.safe_fallbacks.get(context, self.safe_fallbacks["general"])
        
        # Template appears safe
        return template_content
    
    def get_safe_fallback(self, context: str = "general") -> str:
        """Get a guaranteed safe template for given context"""
        return self.safe_fallbacks.get(context, self.safe_fallbacks["general"])


# Global instance for easy access
template_safety_filter = TemplateSafetyFilter()


def ensure_safe_template(content: str, context: str = "general") -> str:
    """
    Convenience function to ensure template safety
    
    CRITICAL: This should be called before any template is sent to users
    """
    return template_safety_filter.sanitize_template(content, context)