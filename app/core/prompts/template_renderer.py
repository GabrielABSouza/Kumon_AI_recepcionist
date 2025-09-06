"""
Template Renderer V2 - Standardized Placeholder System

Implements standardized placeholder syntax and rendering with safe preprocessing.
Eliminates mustache {{}} variables and implements conditional blocks.
"""
from __future__ import annotations

import re
from typing import Dict, Any, Optional, Union

from ...core.logger import app_logger


class TemplateRenderer:
    """
    Safe template renderer with standardized placeholder syntax
    
    Supported syntax:
    - {variable} - Simple variable substitution
    - {variable|default} - Variable with default value
    - {?variable: content} - Conditional block (show content if variable exists)
    - {!variable: content} - Negative conditional (show content if variable doesn't exist)
    """
    
    def __init__(self):
        self.variables_resolved = 0
        self.conditionals_processed = 0
        self.mustache_converted = 0
    
    def preprocess_template(self, template: str) -> str:
        """
        Preprocess template to standardize placeholder syntax
        
        Steps:
        1. Convert {{variable}} → {variable}
        2. Convert [[var]] → {var} 
        3. Convert [[?var: content]] → {?var: content}
        4. Remove any remaining non-standard syntax
        """
        processed = template
        
        # Step 1: Convert mustache variables to standard format
        mustache_count = len(re.findall(r'\{\{[^}]+\}\}', processed))
        if mustache_count > 0:
            processed = re.sub(r'\{\{([^}]+)\}\}', r'{\1}', processed)
            self.mustache_converted += mustache_count
            app_logger.info(f"Converted {mustache_count} mustache variables to standard format")
        
        # Step 2: Convert bracket-style conditionals
        bracket_conditionals = re.findall(r'\[\[([?!][^:]+):\s*([^\]]+)\]\]', processed)
        for condition, content in bracket_conditionals:
            processed = processed.replace(f'[[{condition}: {content}]]', f'{{{condition}: {content}}}')
        
        # Step 3: Convert simple bracket variables
        processed = re.sub(r'\[\[([^:\]]+)\]\]', r'{\1}', processed)
        
        return processed.strip()
    
    def render_template(self, template: str, variables: Dict[str, Any] = None, 
                       stage: Optional[str] = None) -> str:
        """
        Render template with variables and conditional logic
        
        Args:
            template: Template string with placeholders
            variables: Dictionary of variable values
            stage: Conversation stage for stage-aware variable filtering
            
        Returns:
            Rendered template string
        """
        if not variables:
            variables = {}
        
        # Preprocess template
        processed_template = self.preprocess_template(template)
        
        # Apply stage-aware variable filtering
        filtered_variables = self._filter_variables_by_stage(variables, stage)
        
        # Process conditional blocks first
        rendered = self._process_conditionals(processed_template, filtered_variables)
        
        # Process variable substitutions
        rendered = self._process_variables(rendered, filtered_variables)
        
        # Clean up any remaining unresolved placeholders
        rendered = self._cleanup_unresolved_placeholders(rendered)
        
        # Final cleanup
        rendered = self._cleanup_whitespace(rendered)
        
        app_logger.debug(f"Template rendered: {self.variables_resolved} variables, "
                        f"{self.conditionals_processed} conditionals")
        
        return rendered
    
    def _filter_variables_by_stage(self, variables: Dict[str, Any], stage: Optional[str]) -> Dict[str, Any]:
        """Filter variables based on conversation stage restrictions"""
        if not stage:
            return variables
        
        # Stage-aware variable restrictions
        stage_restrictions = {
            'greeting': {
                'welcome': [],  # No personal variables in initial greeting
                'collection': ['first_name', 'parent_name']  # Allow basic info collection
            },
            'qualification': ['first_name', 'parent_name', 'child_name', 'age'],
            'information': ['first_name', 'parent_name', 'child_name', 'age', 'interest_area'],
            'scheduling': None  # All variables allowed in scheduling
        }
        
        allowed_variables = stage_restrictions.get(stage)
        
        # If no restrictions defined for stage, allow all variables
        if allowed_variables is None:
            return variables
        
        # If stage has sub-restrictions (like greeting.welcome), need more context
        if isinstance(allowed_variables, dict):
            # Default to most restrictive for safety
            allowed_variables = allowed_variables.get('welcome', [])
        
        # Filter variables
        filtered = {k: v for k, v in variables.items() if k in allowed_variables}
        
        filtered_count = len(variables) - len(filtered)
        if filtered_count > 0:
            app_logger.info(f"Stage-aware filtering: {filtered_count} variables blocked for stage '{stage}'")
        
        return filtered
    
    def _process_conditionals(self, template: str, variables: Dict[str, Any]) -> str:
        """Process conditional blocks in template"""
        
        # Positive conditionals: {?variable: content}
        positive_pattern = r'\{(\?[^:]+):\s*([^}]+)\}'
        
        def replace_positive_conditional(match):
            condition = match.group(1)[1:]  # Remove '?' prefix
            content = match.group(2)
            
            if condition in variables and variables[condition]:
                self.conditionals_processed += 1
                return content
            else:
                self.conditionals_processed += 1
                return ""
        
        template = re.sub(positive_pattern, replace_positive_conditional, template)
        
        # Negative conditionals: {!variable: content}
        negative_pattern = r'\{(![^:]+):\s*([^}]+)\}'
        
        def replace_negative_conditional(match):
            condition = match.group(1)[1:]  # Remove '!' prefix
            content = match.group(2)
            
            if condition not in variables or not variables[condition]:
                self.conditionals_processed += 1
                return content
            else:
                self.conditionals_processed += 1
                return ""
        
        template = re.sub(negative_pattern, replace_negative_conditional, template)
        
        return template
    
    def _process_variables(self, template: str, variables: Dict[str, Any]) -> str:
        """Process variable substitutions"""
        
        # Variables with defaults: {variable|default}
        default_pattern = r'\{([^|}]+)\|([^}]+)\}'
        
        def replace_variable_with_default(match):
            var_name = match.group(1)
            default_value = match.group(2)
            
            if var_name in variables and variables[var_name]:
                self.variables_resolved += 1
                return str(variables[var_name])
            else:
                self.variables_resolved += 1
                return default_value
        
        template = re.sub(default_pattern, replace_variable_with_default, template)
        
        # Simple variables: {variable}
        simple_pattern = r'\{([^}|?!]+)\}'
        
        def replace_simple_variable(match):
            var_name = match.group(1).strip()
            
            if var_name in variables and variables[var_name]:
                self.variables_resolved += 1
                return str(variables[var_name])
            else:
                # Variable not available - leave placeholder for cleanup
                return f'{{{var_name}}}'
        
        template = re.sub(simple_pattern, replace_simple_variable, template)
        
        return template
    
    def _cleanup_unresolved_placeholders(self, template: str) -> str:
        """Remove any unresolved placeholders to prevent leakage"""
        
        # Count unresolved placeholders before removal
        unresolved = re.findall(r'\{[^}]+\}', template)
        if unresolved:
            app_logger.warning(f"Removing {len(unresolved)} unresolved placeholders: {unresolved}")
        
        # Remove all remaining placeholders
        cleaned = re.sub(r'\{[^}]+\}', '', template)
        
        return cleaned
    
    def _cleanup_whitespace(self, template: str) -> str:
        """Clean up extra whitespace from template rendering"""
        
        # Remove multiple consecutive newlines
        cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', template)
        
        # Remove trailing/leading whitespace from lines
        lines = [line.rstrip() for line in cleaned.split('\n')]
        cleaned = '\n'.join(lines)
        
        # Remove leading/trailing whitespace from entire template
        cleaned = cleaned.strip()
        
        return cleaned
    
    def get_render_metrics(self) -> Dict[str, int]:
        """Get rendering metrics for observability"""
        return {
            "variables_resolved": self.variables_resolved,
            "conditionals_processed": self.conditionals_processed, 
            "mustache_converted": self.mustache_converted
        }
    
    def reset_metrics(self) -> None:
        """Reset rendering metrics"""
        self.variables_resolved = 0
        self.conditionals_processed = 0
        self.mustache_converted = 0


# Global renderer instance
template_renderer = TemplateRenderer()


def render_template(template: str, variables: Dict[str, Any] = None, 
                   stage: Optional[str] = None) -> str:
    """
    Convenience function for template rendering
    """
    return template_renderer.render_template(template, variables, stage)


def preprocess_template(template: str) -> str:
    """
    Convenience function for template preprocessing
    """
    return template_renderer.preprocess_template(template)


__all__ = [
    'TemplateRenderer',
    'template_renderer',
    'render_template',
    'preprocess_template'
]