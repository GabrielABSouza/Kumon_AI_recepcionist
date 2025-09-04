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
        # Configuration template detection patterns - ONLY for unrendered templates
        self.config_patterns = [
            # Template variable indicators (should never be shown to users)
            r'\{\{[\w_]+\}\}',
            r'\{[A-Z_]{3,}\}',  # Only all-caps template variables
            
            # System instructions - ONLY explicit instruction patterns
            r'^Você é.*recepcionista.*Kumon',  # Line start only
            r'^DIRETRIZES:',
            r'^INSTRUÇÕES:',
            r'^POLÍTICA:',
            
            # Template structure indicators - ONLY explicit template markers
            r'RESPOSTA\s+OBRIGATÓRIA',
            r'^## (DIRETRIZES|INSTRUÇÕES|POLÍTICA)',
            
            # Specific dangerous content from base template - ONLY if at line start
            r'^Sempre responda pergunta diretamente',
            r'^Nunca refuse ajudar',
            r'^Nunca quebre o personagem',
            r'^Sempre mantenha identidade'
        ]
        
        # Allowlist for safe content that should pass even if it matches some patterns
        self.safe_content_patterns = [
            # Normal business content
            r'método educacional.*Kumon',  # Allow mentions of Kumon method
            r'nosso método',  # Allow "our method"
            r'método de ensino',  # Allow "teaching method"
        ]
        
        # Compile patterns for performance
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE | re.MULTILINE) for pattern in self.config_patterns]
        self.compiled_safe_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.safe_content_patterns]
        
        # Template files that are allowed to contain configuration content
        self.allowed_template_files = {
            "app/prompts/templates/fallback/general_assistance.txt",
            "app/prompts/templates/greeting/",
            "app/prompts/templates/information/",
            "app/prompts/templates/scheduling/"
        }
        
        # Safe fallback templates for different contexts
        self.safe_fallbacks = {
            "greeting": "Olá! Bem-vindo ao Kumon Vila A! 😊\n\nMeu nome é Cecília. Como posso ajudá-lo hoje?",
            "information": "Ficou com alguma dúvida sobre o Kumon? Posso explicar melhor nosso método ou tirar outras questões!",
            "scheduling": "Vamos agendar sua visita ao Kumon Vila A! Qual seria o melhor horário para você?",
            "general": "Olá! Sou Cecília do Kumon Vila A. Como posso ajudá-lo hoje? 😊",
            "error": "Desculpe, houve um problema técnico. Entre em contato conosco:\n📞 (51) 99692-1999"
        }
    
    def is_configuration_template(self, template_content: str, context: str = "general") -> bool:
        """
        Detect if template contains configuration directives
        
        Args:
            template_content: Template text to analyze
            context: Context for template safety assessment
            
        Returns:
            True if template appears to be a configuration template
        """
        if not template_content:
            return False
        
        # Check for configuration directives in ALL contexts (including greeting)
        # Configuration directives are NEVER safe regardless of context
            
        # Check if content is explicitly safe first
        for safe_pattern in self.compiled_safe_patterns:
            if safe_pattern.search(template_content):
                logger.info(f"✅ Content matches safe pattern: {safe_pattern.pattern}")
                return False  # Safe content, not a config template
        
        # Check against all config patterns for other contexts
        for pattern in self.compiled_patterns:
            if pattern.search(template_content):
                logger.warning(f"🚨 Configuration template detected: {pattern.pattern}")
                return True
                
        return False
    
    def sanitize_template(self, template_content: str, context: str = "general", source_file: str = None) -> str:
        """
        Ensure template is safe for user consumption
        
        Args:
            template_content: Original template content
            context: Context for fallback selection (greeting, information, etc.)
            source_file: Source template file path (if known) for allowlist checking
            
        Returns:
            Safe template content or safe fallback
        """
        if not template_content:
            logger.warning("🚨 Empty template provided, using safe fallback")
            return self.safe_fallbacks.get(context, self.safe_fallbacks["general"])
        
        # Check if source file is in allowlist
        if source_file:
            for allowed_path in self.allowed_template_files:
                if allowed_path in source_file:
                    logger.info(f"✅ Template from allowed path: {source_file}")
                    return template_content  # Skip safety check for allowed files
        
        # Check if template is safe
        if self.is_configuration_template(template_content, context):
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


def ensure_safe_template(content: str, context: str = "general", source_file: str = None) -> str:
    """
    Convenience function to ensure template safety
    
    CRITICAL: This should be called before any template is sent to users
    """
    return template_safety_filter.sanitize_template(content, context, source_file)


def check_and_sanitize(text: str, context: str = "general") -> dict:
    """
    Safety "fail-soft": check template safety and return sanitized result
    
    Returns:
        {
            "safe": bool,
            "text": sanitized_text_or_fallback,
            "reason": optional_reason,
            "meta": {"safety_blocked": true/false, "pattern": "...", "context": "..."}
        }
    """
    if not text:
        return {
            "safe": True,
            "text": template_safety_filter.get_safe_fallback(context),
            "reason": "empty_text",
            "meta": {"safety_blocked": True, "pattern": "empty", "context": context}
        }
    
    # Check if the text is a configuration template
    is_unsafe = template_safety_filter.is_configuration_template(text, context)
    
    if is_unsafe:
        # Return safe fallback instead of blocking
        safe_text = template_safety_filter.get_safe_fallback(context)
        return {
            "safe": True,  # Always safe because we provide fallback
            "text": safe_text,
            "reason": "configuration_template_detected",
            "meta": {
                "safety_blocked": True, 
                "pattern": "template_variables", 
                "context": context,
                "original_length": len(text),
                "fallback_used": True
            }
        }
    
    # Text is safe as-is
    return {
        "safe": True,
        "text": text,
        "reason": None,
        "meta": {"safety_blocked": False, "pattern": None, "context": context}
    }