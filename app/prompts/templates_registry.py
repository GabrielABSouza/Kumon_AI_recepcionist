"""
Canonical Templates Registry for Kumon Assistant

Defines the canonical template paths and fallback mechanisms.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

# ========== CANONICAL TEMPLATE REGISTRY ==========

TEMPLATES_BASE_DIR = Path("app/prompts/templates")

# Template registry with primary and fallback paths
CANONICAL_TEMPLATES: Dict[str, Dict[str, str]] = {
    # Greeting templates
    "kumon:greeting:response:general": {
        "primary": "kumon/greeting/response_general_with_name.txt",
        "fallback": "kumon/greeting/response_general_neutral.txt",
        "description": "General greeting response with optional personalization"
    },
    
    "kumon:greeting:response:general:neutral": {
        "primary": "kumon/greeting/response_general_neutral.txt",
        "fallback": "greeting/welcome/initial.txt",
        "description": "Neutral greeting without gender/name requirements"
    },
    
    "kumon:greeting:welcome:initial": {
        "primary": "greeting/welcome/initial.txt", 
        "fallback": "greeting/welcome_initial.txt",
        "description": "Initial welcome message for new contacts"
    },
    
    # Collection templates
    "kumon:greeting:collection:parent_name": {
        "primary": "greeting/collection/parent_name.txt",
        "fallback": "greeting/collection_parent_name.txt", 
        "description": "Collect parent name"
    },
    
    # Qualification templates
    "kumon:qualification:child_interest": {
        "primary": "greeting/response/child_interest.txt",
        "fallback": "greeting/response/self_interest.txt",
        "description": "Response for child interest inquiry"
    },
    
    # Information templates  
    "kumon:information:methodology": {
        "primary": "information/response/methodology.txt",
        "fallback": "information/cecilia_methodology_kumon.txt",
        "description": "Kumon methodology explanation"
    },
    
    "kumon:information:benefits": {
        "primary": "information/response/benefits.txt", 
        "fallback": "information/benefits_explanation.txt",
        "description": "Kumon program benefits"
    },
    
    "kumon:information:pricing": {
        "primary": "information/response/pricing.txt",
        "fallback": "information/response/program_mathematics.txt",
        "description": "Pricing information"
    },
}

# Variable requirements per template (for validation)
TEMPLATE_VARIABLE_REQUIREMENTS: Dict[str, List[str]] = {
    "kumon:greeting:response:general": ["parent_name"],
    "kumon:greeting:response:general:neutral": [],  # No variables required
    "kumon:greeting:welcome:initial": [],
    "kumon:greeting:collection:parent_name": [],
    "kumon:qualification:child_interest": ["parent_name"],
    "kumon:information:methodology": [],
    "kumon:information:benefits": [],
    "kumon:information:pricing": [],
}

# ========== TEMPLATE RESOLUTION FUNCTIONS ==========

def get_template_path(template_id: str) -> Optional[Path]:
    """
    Get the canonical path for a template with fallback mechanism.
    
    Args:
        template_id: Template identifier (e.g., 'kumon:greeting:response:general')
        
    Returns:
        Path to template file or None if not found
    """
    template_config = CANONICAL_TEMPLATES.get(template_id)
    if not template_config:
        return None
        
    # Try primary path first
    primary_path = TEMPLATES_BASE_DIR / template_config["primary"]
    if primary_path.exists():
        return primary_path
        
    # Fallback to secondary path
    fallback_path = TEMPLATES_BASE_DIR / template_config["fallback"]
    if fallback_path.exists():
        return fallback_path
        
    return None

def resolve_greeting_fallback(template_id: str) -> str:
    """
    Automatic fallback for greeting templates.
    If 'general' template is missing, automatically fallback to 'neutral'.
    
    Args:
        template_id: Original template ID
        
    Returns:
        Resolved template ID with fallback applied
    """
    if template_id == "kumon:greeting:response:general":
        # Check if primary exists
        primary_path = get_template_path(template_id)
        if primary_path is None or not primary_path.exists():
            # Fallback to neutral version
            return "kumon:greeting:response:general:neutral"
    
    return template_id

def get_template_variable_requirements(template_id: str) -> List[str]:
    """
    Get required variables for a template.
    
    Args:
        template_id: Template identifier
        
    Returns:
        List of required variable names
    """
    return TEMPLATE_VARIABLE_REQUIREMENTS.get(template_id, [])

def validate_template_registry() -> Dict[str, Any]:
    """
    Validate that all templates in the registry exist.
    
    Returns:
        Validation report with missing templates and statistics
    """
    report = {
        "total_templates": len(CANONICAL_TEMPLATES),
        "valid_templates": 0,
        "missing_primary": [],
        "missing_fallback": [],
        "completely_missing": [],
        "valid_paths": []
    }
    
    for template_id, config in CANONICAL_TEMPLATES.items():
        primary_path = TEMPLATES_BASE_DIR / config["primary"]
        fallback_path = TEMPLATES_BASE_DIR / config["fallback"]
        
        primary_exists = primary_path.exists()
        fallback_exists = fallback_path.exists()
        
        if primary_exists:
            report["valid_templates"] += 1
            report["valid_paths"].append(str(primary_path))
        elif fallback_exists:
            report["valid_templates"] += 1
            report["missing_primary"].append(template_id)
            report["valid_paths"].append(str(fallback_path))
        else:
            report["completely_missing"].append(template_id)
            
        if not primary_exists:
            report["missing_primary"].append(template_id)
        if not fallback_exists:
            report["missing_fallback"].append(template_id)
    
    report["validation_passed"] = len(report["completely_missing"]) == 0
    return report

def list_all_template_files() -> List[Path]:
    """
    Get all template files in the templates directory.
    
    Returns:
        List of all .txt files in templates directory
    """
    if not TEMPLATES_BASE_DIR.exists():
        return []
        
    return list(TEMPLATES_BASE_DIR.rglob("*.txt"))

# ========== TEMPLATE REGISTRY EXPORT ==========

__all__ = [
    "CANONICAL_TEMPLATES",
    "TEMPLATE_VARIABLE_REQUIREMENTS", 
    "get_template_path",
    "resolve_greeting_fallback",
    "get_template_variable_requirements",
    "validate_template_registry",
    "list_all_template_files"
]