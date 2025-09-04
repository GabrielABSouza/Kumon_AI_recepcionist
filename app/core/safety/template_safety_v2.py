"""
Template Safety System V2 - Metadata-Aware Fail-Soft Protection

Enhanced safety system that uses template metadata for classification and
implements true fail-soft behavior without emptying the outbox.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple, Union

from ...core.logger import app_logger
from ..prompts.template_key import TemplateKey, TemplateKind, TemplateMetadata
from ..prompts.template_loader import template_loader


class TemplateSecurityError(Exception):
    """Template security violation"""
    pass


class TemplateSafetySystemV2:
    """
    Metadata-aware template safety system with fail-soft behavior
    """
    
    def __init__(self):
        self.blocked_count = 0
        self.fallback_used_count = 0
        self.mustache_stripped_count = 0
        
        # Legacy regex patterns as fallback only
        self._legacy_config_patterns = [
            r'\{\{[A-Z_]{3,}\}\}',  # {{SYSTEM_VAR}}
            r'DIRETRIZES:',
            r'INSTRUÇÕES:',
            r'SISTEMA BASE',
            r'NUNCA se identifique como',
            r'PERSONALIDADE CORE',
        ]
    
    def check_and_sanitize(self, text: str, template_key: Optional[Union[str, TemplateKey]] = None, 
                          context: str = "general") -> Dict[str, any]:
        """
        Check template safety and sanitize with fail-soft behavior
        
        Args:
            text: Template content to check
            template_key: Template key for metadata lookup
            context: Conversation context (for fallback selection)
            
        Returns:
            {
                "safe": bool,           # Whether content is safe for delivery
                "text": str,            # Safe content (original or fallback)
                "reason": str,          # Reason for blocking (if any)
                "fallback_used": bool,  # Whether fallback was used
                "meta": {              # Additional metadata
                    "original_blocked": bool,
                    "fallback_key": str,
                    "safety_method": str
                }
            }
        """
        result = {
            "safe": True,
            "text": text,
            "reason": "",
            "fallback_used": False,
            "meta": {
                "original_blocked": False,
                "fallback_key": "",
                "safety_method": "none"
            }
        }
        
        # Step 1: Metadata-based safety check (preferred)
        if template_key:
            resolved_key = template_loader.template_loader.resolve_key(template_key) if hasattr(template_loader, 'resolve_key') else None
            if resolved_key:
                metadata_result = self._check_metadata_safety(text, resolved_key, context)
                if not metadata_result["safe"]:
                    return metadata_result
                result["meta"]["safety_method"] = "metadata"
        
        # Step 2: Content analysis (strip mustache, check patterns)
        content_result = self._check_content_safety(text, context)
        if not content_result["safe"]:
            return content_result
            
        # Step 3: Ensure no mustache variables in final output
        clean_text = self._strip_mustache_variables(text)
        if clean_text != text:
            self.mustache_stripped_count += 1
            result["text"] = clean_text
            result["meta"]["mustache_stripped"] = True
            app_logger.info(f"Mustache variables stripped from template output")
        
        return result
    
    def _check_metadata_safety(self, text: str, template_key: TemplateKey, context: str) -> Dict[str, any]:
        """Check safety based on template metadata"""
        try:
            # Try to load metadata
            _, metadata = template_loader.load_template(template_key)
            
            # Block configuration templates from user delivery
            if metadata.kind == TemplateKind.CONFIGURATION:
                self.blocked_count += 1
                
                # Get neutral fallback
                fallback_text, fallback_key = self._get_neutral_fallback(context, template_key)
                
                app_logger.warning(f"Configuration template blocked: {template_key.to_canonical()}")
                app_logger.info(f"fail_soft_used=true, reason=configuration_template_blocked")
                
                return {
                    "safe": False,  # Original was not safe
                    "text": fallback_text,  # But we provide safe fallback
                    "reason": "configuration_template_blocked",
                    "fallback_used": True,
                    "meta": {
                        "original_blocked": True,
                        "fallback_key": fallback_key,
                        "safety_method": "metadata"
                    }
                }
            
            # Block fragment templates when used standalone
            if metadata.kind == TemplateKind.FRAGMENT:
                app_logger.warning(f"Fragment template used standalone: {template_key.to_canonical()}")
                
                fallback_text, fallback_key = self._get_neutral_fallback(context, template_key)
                
                return {
                    "safe": False,
                    "text": fallback_text,
                    "reason": "fragment_template_standalone",
                    "fallback_used": True,
                    "meta": {
                        "original_blocked": True,
                        "fallback_key": fallback_key,
                        "safety_method": "metadata"
                    }
                }
            
            return {"safe": True, "text": text, "reason": "", "fallback_used": False, "meta": {"safety_method": "metadata"}}
            
        except Exception as e:
            app_logger.warning(f"Metadata safety check failed for {template_key}: {e}")
            # Fall back to content-based checking
            return {"safe": True, "text": text, "reason": "", "fallback_used": False, "meta": {"safety_method": "metadata_failed"}}
    
    def _check_content_safety(self, text: str, context: str) -> Dict[str, any]:
        """Check safety based on content patterns (legacy fallback)"""
        
        # Check for dangerous configuration patterns
        for pattern in self._legacy_config_patterns:
            if re.search(pattern, text, re.MULTILINE | re.IGNORECASE):
                self.blocked_count += 1
                
                # Get neutral fallback
                fallback_text, fallback_key = self._get_neutral_fallback(context)
                
                app_logger.warning(f"Configuration content detected by pattern: {pattern}")
                app_logger.info(f"fail_soft_used=true, reason=config_pattern_detected")
                
                return {
                    "safe": False,
                    "text": fallback_text,
                    "reason": "config_pattern_detected",
                    "fallback_used": True,
                    "meta": {
                        "original_blocked": True,
                        "fallback_key": fallback_key,
                        "safety_method": "pattern_matching",
                        "blocked_pattern": pattern
                    }
                }
        
        return {"safe": True, "text": text, "reason": "", "fallback_used": False, "meta": {"safety_method": "pattern_matching"}}
    
    def _strip_mustache_variables(self, text: str) -> str:
        """Strip any remaining mustache variables from final output"""
        # Remove {{...}} patterns
        clean_text = re.sub(r'\{\{[^}]+\}\}', '', text)
        
        # Clean up any resulting extra whitespace
        clean_text = re.sub(r'\n\s*\n\s*\n', '\n\n', clean_text)
        clean_text = clean_text.strip()
        
        return clean_text
    
    def _get_neutral_fallback(self, context: str, original_key: Optional[TemplateKey] = None) -> Tuple[str, str]:
        """
        Get neutral fallback content for the given context
        
        Returns:
            Tuple of (fallback_text, fallback_key)
        """
        # Define neutral fallbacks by context
        neutral_fallbacks = {
            "greeting": "kumon:greeting:response:general:neutral",
            "qualification": "kumon:qualification:response:general:neutral", 
            "information": "kumon:information:response:general:neutral",
            "scheduling": "kumon:scheduling:response:general:neutral",
            "fallback": "kumon:fallback:response:general:neutral",
        }
        
        # Get fallback key for context
        fallback_key = neutral_fallbacks.get(context, "kumon:greeting:response:general:neutral")
        
        try:
            # Try to load the neutral fallback
            fallback_content, _ = template_loader.load_template(fallback_key)
            self.fallback_used_count += 1
            return fallback_content, fallback_key
            
        except Exception as e:
            app_logger.error(f"Failed to load neutral fallback {fallback_key}: {e}")
            
            # Emergency hardcoded fallback
            emergency_fallback = "Olá! Sou a Cecília, recepcionista do Kumon Vila A. Como posso ajudá-lo hoje?"
            self.fallback_used_count += 1
            return emergency_fallback, "emergency_hardcoded"
    
    def get_safety_metrics(self) -> Dict[str, int]:
        """Get safety system metrics for observability"""
        return {
            "templates_blocked": self.blocked_count,
            "fallbacks_used": self.fallback_used_count, 
            "mustache_stripped": self.mustache_stripped_count
        }
    
    def reset_metrics(self) -> None:
        """Reset metrics counters"""
        self.blocked_count = 0
        self.fallback_used_count = 0
        self.mustache_stripped_count = 0


# Global instance
template_safety_v2 = TemplateSafetySystemV2()


def check_and_sanitize(text: str, template_key: Optional[Union[str, TemplateKey]] = None, 
                      context: str = "general") -> Dict[str, any]:
    """
    Convenience function for template safety checking
    
    This is the main entry point for the safety system.
    """
    return template_safety_v2.check_and_sanitize(text, template_key, context)


def ensure_safe_template(text: str, context: str = "general") -> str:
    """
    Legacy compatibility function - ensures template is safe for delivery
    
    Returns:
        Safe content (original or fallback)
    """
    result = check_and_sanitize(text, context=context)
    
    if result["fallback_used"]:
        app_logger.info(f"Template safety: fallback used, reason={result['reason']}")
    
    return result["text"]


__all__ = [
    'TemplateSafetySystemV2',
    'TemplateSecurityError', 
    'template_safety_v2',
    'check_and_sanitize',
    'ensure_safe_template'
]