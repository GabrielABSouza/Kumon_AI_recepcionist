"""
Template Key Canonical System

Provides normalized template key management with alias resolution and metadata support.
Replaces ad-hoc string keys with structured, canonical identifiers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Union


class TemplateKind(Enum):
    """Template classification for security and usage policies"""
    CONTENT = "content"           # User-facing content (safe for delivery)
    CONFIGURATION = "configuration"  # Internal config (never delivered to user)
    FRAGMENT = "fragment"         # Partial content (only used as component)


class TemplateContext(Enum):
    """Conversation context for template selection"""
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    INFORMATION = "information"
    SCHEDULING = "scheduling"
    FALLBACK = "fallback"
    CONFIRMATION = "confirmation"
    ERROR = "error"
    SYSTEM = "system"


class TemplateCategory(Enum):
    """Template functional category"""
    RESPONSE = "response"
    WELCOME = "welcome"
    COLLECTION = "collection"
    CLARIFICATION = "clarification"
    CONFIRMATION = "confirmation"
    ERROR = "error"
    BASE = "base"


@dataclass
class TemplateMetadata:
    """Template metadata from front-matter or inferred"""
    kind: TemplateKind = TemplateKind.CONTENT
    context: Optional[TemplateContext] = None
    variant: Optional[str] = None
    description: str = ""
    variables: List[str] = field(default_factory=list)
    stage_restrictions: Set[str] = field(default_factory=set)


@dataclass
class TemplateKey:
    """
    Canonical template key with normalization and alias resolution
    
    Format: namespace:context:category:name[:variant]
    Example: kumon:greeting:response:general:neutral
    """
    namespace: str
    context: str
    category: str
    name: str
    variant: Optional[str] = None
    
    @classmethod
    def from_string(cls, key_str: str) -> TemplateKey:
        """
        Parse template key from string with alias resolution
        
        Examples:
        - "kumon:greeting:response:general" → TemplateKey(...)
        - "kumon:ConversationStage.GREETING:response:general" → normalized to lowercase
        - "greeting:response:general" → namespace="kumon" inferred
        """
        # Normalize enum references
        key_str = cls._normalize_enum_references(key_str)
        
        parts = key_str.split(":")
        
        # Handle different key formats
        if len(parts) == 3:
            # Assume namespace is "kumon"
            namespace = "kumon"
            context, category, name = parts
            variant = None
        elif len(parts) == 4:
            namespace, context, category, name = parts
            variant = None
        elif len(parts) == 5:
            namespace, context, category, name, variant = parts
        else:
            raise ValueError(f"Invalid template key format: {key_str}")
            
        return cls(
            namespace=namespace.lower(),
            context=context.lower(),
            category=category.lower(),
            name=name.lower(),
            variant=variant.lower() if variant else None
        )
    
    @staticmethod
    def _normalize_enum_references(key_str: str) -> str:
        """Normalize enum references to lowercase strings"""
        # Handle ConversationStage.GREETING → greeting
        key_str = re.sub(r'ConversationStage\.(\w+)', lambda m: m.group(1).lower(), key_str)
        # Handle ConversationStep.WELCOME → welcome
        key_str = re.sub(r'ConversationStep\.(\w+)', lambda m: m.group(1).lower(), key_str)
        return key_str
    
    def to_canonical(self) -> str:
        """Convert to canonical string representation"""
        parts = [self.namespace, self.context, self.category, self.name]
        if self.variant:
            parts.append(self.variant)
        return ":".join(parts)
    
    def to_neutral_variant(self) -> TemplateKey:
        """Create neutral variant of this template key"""
        return TemplateKey(
            namespace=self.namespace,
            context=self.context,
            category=self.category,
            name=self.name,
            variant="neutral"
        )
    
    def matches(self, pattern: str) -> bool:
        """Check if key matches a pattern (supports wildcards)"""
        canonical = self.to_canonical()
        # Simple wildcard support
        pattern = pattern.replace("*", ".*")
        return re.match(f"^{pattern}$", canonical) is not None
    
    def __str__(self) -> str:
        return self.to_canonical()
    
    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return self.to_canonical() == other
        elif isinstance(other, TemplateKey):
            return self.to_canonical() == other.to_canonical()
        return False
    
    def __hash__(self) -> int:
        return hash(self.to_canonical())


class TemplateKeyRegistry:
    """Registry for template key normalization and alias resolution"""
    
    def __init__(self):
        self._aliases: Dict[str, str] = {}
        self._metadata_cache: Dict[str, TemplateMetadata] = {}
    
    def register_alias(self, alias: str, canonical: str) -> None:
        """Register an alias for a canonical key"""
        self._aliases[alias] = canonical
    
    def resolve_key(self, key_input: Union[str, TemplateKey]) -> TemplateKey:
        """Resolve any key input to canonical TemplateKey"""
        if isinstance(key_input, TemplateKey):
            return key_input
            
        # Check for direct alias
        canonical_str = self._aliases.get(key_input, key_input)
        
        # Parse and normalize
        return TemplateKey.from_string(canonical_str)
    
    def get_metadata(self, key: Union[str, TemplateKey]) -> TemplateMetadata:
        """Get metadata for a template key"""
        resolved_key = self.resolve_key(key)
        canonical = resolved_key.to_canonical()
        
        # Return cached metadata or create default
        return self._metadata_cache.get(canonical, TemplateMetadata())
    
    def set_metadata(self, key: Union[str, TemplateKey], metadata: TemplateMetadata) -> None:
        """Set metadata for a template key"""
        resolved_key = self.resolve_key(key)
        canonical = resolved_key.to_canonical()
        self._metadata_cache[canonical] = metadata
    
    def list_keys(self, pattern: Optional[str] = None) -> List[str]:
        """List all registered canonical keys, optionally filtered by pattern"""
        keys = list(self._metadata_cache.keys())
        
        if pattern:
            pattern_regex = pattern.replace("*", ".*")
            keys = [k for k in keys if re.match(f"^{pattern_regex}$", k)]
            
        return sorted(keys)


# Global registry instance
template_registry = TemplateKeyRegistry()


# Pre-register common aliases for backward compatibility
COMMON_ALIASES = {
    # Enum-based aliases
    "kumon:ConversationStage.GREETING:response:general": "kumon:greeting:response:general",
    "kumon:ConversationStep.WELCOME:response:initial": "kumon:greeting:welcome:initial",
    
    # Short-form aliases
    "greeting:response:general": "kumon:greeting:response:general",
    "greeting:welcome:initial": "kumon:greeting:welcome:initial",
    "qualification:child_interest": "kumon:qualification:response:child_interest",
    
    # Legacy aliases for existing code
    "kumon_greeting_response": "kumon:greeting:response:general",
    "kumon_greeting_neutral": "kumon:greeting:response:general:neutral",
}

# Register all aliases
for alias, canonical in COMMON_ALIASES.items():
    template_registry.register_alias(alias, canonical)


def normalize_template_key(key_input: Union[str, TemplateKey]) -> str:
    """Convenience function to normalize any template key input to canonical string"""
    return template_registry.resolve_key(key_input).to_canonical()


__all__ = [
    "TemplateKey",
    "TemplateKind", 
    "TemplateContext",
    "TemplateCategory",
    "TemplateMetadata",
    "TemplateKeyRegistry",
    "template_registry",
    "normalize_template_key",
]