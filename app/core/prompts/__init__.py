"""
Core prompts module for template management
"""

from .template_key import (
    TemplateKey,
    TemplateKind,
    TemplateContext, 
    TemplateCategory,
    TemplateMetadata,
    TemplateKeyRegistry,
    template_registry,
    normalize_template_key
)

__all__ = [
    "TemplateKey",
    "TemplateKind",
    "TemplateContext",
    "TemplateCategory", 
    "TemplateMetadata",
    "TemplateKeyRegistry",
    "template_registry",
    "normalize_template_key"
]