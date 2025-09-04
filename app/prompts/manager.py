"""
LangSmith Prompt Manager for Kumon Assistant

This module provides centralized prompt management with:
- LangSmith Hub integration for versioned prompts
- Local fallback templates for offline operation
- Intelligent caching for performance
- Template variable substitution
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import aiofiles

# LangSmith removed - using local templates only
from langchain.prompts import PromptTemplate

from ..core.config import settings
from ..core.logger import app_logger
from ..core.safety.template_safety import ensure_safe_template
from .template_variables import template_variable_resolver


class PromptManager:
    """Manages prompts from local templates only"""

    def __init__(self):
        # Lazy initialization - defer I/O until needed
        self.cache = {}
        self.fallback_dir: Optional[Path] = None
        self._initialized = False
    
    def _ensure_initialized(self) -> None:
        """Lazy initialization of I/O resources"""
        if self._initialized:
            return
            
        # Skip heavy initialization during unit tests
        if os.getenv("UNIT_TESTING") == "1":
            app_logger.info("UNIT_TESTING=1: Skipping prompt manager heavy initialization")
            self._initialized = True
            return
            
        app_logger.info("Prompt manager initialized with local templates only")
        self.fallback_dir = Path("app/prompts/templates")
        self.fallback_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = True

    # Cache removed - using direct template loading only

    # LangSmith removed - using local templates only

    async def get_prompt(
        self,
        name: str,
        tag: str = "prod",
        variables: Optional[Dict[str, Any]] = None,
        fallback_enabled: bool = True,
        conversation_state: Optional[Dict] = None,
        student_name: Optional[str] = None,
    ) -> str:
        """
        Get a prompt from local templates only

        Args:
            name: Prompt name (e.g., 'kumon:greeting:welcome:initial')
            variables: Variables to substitute in template
            conversation_state: Current conversation context
            student_name: Student name for personalization

        Returns:
            Formatted prompt string
        """
        self._ensure_initialized()
        # LOCAL TEMPLATES ONLY - Simple and reliable approach
        prompt_template = None
        
        # Try new structured template system first with variant selection
        prompt_template = await self._fetch_from_fallback(name, conversation_state)
        
        # If structured template not found, try deterministic fallback chain
        if not prompt_template:
            prompt_template = await self._try_fallback_chain(name)

        # Last resort: base template
        if prompt_template is None:
            app_logger.error(f"🚨 All template sources failed for {name}, using BASE CECÍLIA")
            prompt_template = await self._get_base_cecilia_template()

        # Apply variables with intelligent stage-aware resolution
        if variables or conversation_state:
            try:
                # Get intelligent variables based on conversation state and stage
                resolved_variables = template_variable_resolver.get_template_variables(
                    conversation_state or {}, user_variables=variables
                )

                if resolved_variables:
                    # Pre-process template to handle missing variables gracefully
                    safe_template = self._preprocess_template(prompt_template, resolved_variables)
                    
                    # Use LangChain PromptTemplate for safe variable substitution
                    try:
                        template = PromptTemplate.from_template(safe_template)
                        # Only pass variables that exist in the template
                        template_vars = template.input_variables
                        filtered_vars = {k: v for k, v in resolved_variables.items() if k in template_vars}
                        
                        formatted_prompt = template.format(**filtered_vars)
                        app_logger.info(
                            f"Applied {len(filtered_vars)} variables to template: {name}"
                        )
                        # CRITICAL: Apply safety filter before returning
                        return ensure_safe_template(formatted_prompt, self._get_context_from_name(name))
                    except KeyError as ke:
                        app_logger.warning(f"Missing variable in template {name}: {ke}")
                        # Use template without problematic variables
                        return ensure_safe_template(safe_template, self._get_context_from_name(name))
                else:
                    app_logger.info(f"No variables to apply for template: {name}")

            except Exception as e:
                app_logger.error(f"Failed to format prompt template: {e}")
                # Fallback to simple string formatting if available
                if variables:
                    try:
                        formatted_response = prompt_template.format(**variables)
                        return ensure_safe_template(formatted_response, self._get_context_from_name(name))
                    except Exception as e2:
                        app_logger.error(f"Fallback formatting also failed: {e2}")

        # CRITICAL: Always apply safety filter before returning any template
        final_response = ensure_safe_template(prompt_template, self._get_context_from_name(name))
        return final_response

    def _preprocess_template(self, template: str, available_variables: Dict[str, Any]) -> str:
        """
        Pre-process template to handle missing variables gracefully
        
        Removes conditional blocks if variables are missing:
        - [[?var: "text with {var}"]] -> removed if var not available
        - [[var|default]] -> replaced with default if var not available
        """
        import re
        
        # Handle conditional blocks: [[?var: "content"]]
        pattern_conditional = r'\[\[\?([^:]+):\s*"([^"]+)"\]\]'
        def replace_conditional(match):
            var_name = match.group(1).strip()
            content = match.group(2)
            if var_name in available_variables:
                return content
            return ""  # Remove block if variable not available
        
        template = re.sub(pattern_conditional, replace_conditional, template)
        
        # Handle default values: [[var|default]]
        pattern_default = r'\[\[([^|]+)\|([^]]+)\]\]'
        def replace_default(match):
            var_name = match.group(1).strip()
            default = match.group(2).strip()
            if var_name in available_variables:
                return "{" + var_name + "}"
            return default
        
        template = re.sub(pattern_default, replace_default, template)
        
        # Remove any remaining unmatched variables in curly braces that aren't available
        # This prevents KeyError during template formatting
        pattern_vars = r'\{([^}]+)\}'
        found_vars = re.findall(pattern_vars, template)
        for var in found_vars:
            if var not in available_variables:
                app_logger.debug(f"Removing unavailable variable from template: {var}")
                # Replace with neutral placeholder
                template = template.replace("{" + var + "}", "")
        
        return template
    
    def _get_context_from_name(self, template_name: str) -> str:
        """Extract context from template name for safety filtering"""
        if "greeting" in template_name.lower():
            return "greeting"
        elif "information" in template_name.lower():
            return "information"
        elif "scheduling" in template_name.lower():
            return "scheduling"
        elif "handoff" in template_name.lower():
            return "general"
        else:
            return "general"

    # LangSmith fetch method removed - using local templates only

    async def _fetch_from_fallback(self, name: str, conversation_state: Optional[Dict] = None) -> Optional[str]:
        """Fetch prompt from local fallback templates with variant selection
        
        Path resolution rules:
        - namespace:stage:kind:name:variant -> {namespace}/{stage}/{kind}_{name}_{variant}.txt
        - namespace:stage:kind:name -> {namespace}/{stage}/{kind}_{name}_neutral.txt (default variant)
        """
        try:
            parts = name.split(":")
            
            # Determine variant based on available variables
            variant = None
            if conversation_state:
                # Check which variables are available to select best variant
                from .template_variables import template_variable_resolver
                variables = template_variable_resolver.get_template_variables(
                    conversation_state or {}
                )
                
                # Variant selection based on variable mask
                if "parent_name" in variables or "first_name" in variables:
                    variant = "with_name"
                elif any(v in variables for v in ["gender_pronoun", "gender_article"]):
                    variant = "with_pronoun"
                else:
                    variant = "neutral"
                
                # Log telemetry for variant selection
                forbidden_vars = []
                if hasattr(template_variable_resolver, 'mapper'):
                    current_stage = conversation_state.get("current_stage")
                    current_step = conversation_state.get("current_step")
                    if current_stage and current_step:
                        policy = template_variable_resolver._get_variable_policy(current_stage, current_step)
                        forbidden_vars = list(policy.forbidden)
                
                app_logger.info(
                    f"Template variant selection - name: {name}, variant: {variant}, "
                    f"resolved_vars: {list(variables.keys())}, "
                    f"policy_forbidden: {forbidden_vars}"
                )
            else:
                variant = parts[4] if len(parts) > 4 else "neutral"

            # Build filepath with namespace
            if len(parts) >= 4 and parts[0] == "kumon":
                namespace = parts[0]
                stage = parts[1]
                kind = parts[2]
                name_part = parts[3]
                
                # Handle ConversationStage enum values
                if stage.startswith("ConversationStage."):
                    stage = stage.replace("ConversationStage.", "").lower()
                elif hasattr(stage, 'value'):
                    stage = stage.value.lower()
                elif not isinstance(stage, str):
                    stage = str(stage).lower()
                
                # Try with selected variant first
                filepath = self.fallback_dir / namespace / stage / f"{kind}_{name_part}_{variant}.txt"
                if filepath.exists():
                    async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
                        content = await f.read()
                        app_logger.info(f"✅ Using template with variant: {filepath}")
                        return content.strip()
                
                # Fallback to neutral variant
                filepath = self.fallback_dir / namespace / stage / f"{kind}_{name_part}_neutral.txt"
                if filepath.exists():
                    async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
                        content = await f.read()
                        app_logger.info(f"✅ Using neutral template: {filepath}")
                        return content.strip()
                
                # Try without variant
                filepath = self.fallback_dir / namespace / stage / f"{kind}_{name_part}.txt"
                if filepath.exists():
                    async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
                        content = await f.read()
                        app_logger.info(f"✅ Using template without variant: {filepath}")
                        return content.strip()

            # Special mapping for legacy system templates and fallbacks
            legacy_mappings = {
                "kumon:conversation:general": "system/conversation/general.txt",
                "kumon:system:base:identity": "system/base/identity.txt",
                "kumon:fallback:level1:general": "fallback/general_assistance.txt",
                "kumon:fallback:level2:basic": "fallback/qualification_data_collection.txt",
                "kumon:handoff:transfer:human_contact": "fallback/handoff_general.txt",
            }

            if name in legacy_mappings:
                filepath = self.fallback_dir / legacy_mappings[name]
                if filepath.exists():
                    async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
                        content = await f.read()
                        app_logger.info(f"✅ Using mapped legacy template: {filepath}")
                        return content.strip()

            # Fallback to old structure for backward compatibility
            if len(parts) >= 3:
                stage, type_name, variant = parts[0], parts[1], parts[2]
                filename = f"{type_name}_{variant}.txt"
                filepath = self.fallback_dir / stage / filename
            else:
                # Legacy fallback naming
                filepath = self.fallback_dir / f"{name.replace(':', '_')}.txt"

            if filepath.exists():
                async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
                    content = await f.read()
                    app_logger.info(f"📁 Using legacy template: {filepath}")
                    return content.strip()
            else:
                app_logger.warning(f"❌ Template not found: {name} - Tried: {filepath}")
                return None

        except Exception as e:
            app_logger.error(f"Failed to load fallback template: {name} - {e}")
            return None
    
    async def _try_fallback_chain(self, name: str) -> Optional[str]:
        """Try deterministic fallback chain for template resolution
        
        Fallback order:
        1. kumon:greeting:response:general:{variant} (already tried)
        2. kumon:greeting:response:general:neutral
        3. kumon:fallback:level1:general
        4. Legacy Cecilia system
        """
        # Parse original name to construct fallbacks
        parts = name.split(":")
        
        fallback_candidates = []
        
        if len(parts) >= 4 and parts[0] == "kumon":
            # For kumon:greeting:response:general -> try neutral variant
            base_name = ":".join(parts[:4])
            fallback_candidates.append(f"{base_name}:neutral")
            
            # Generic fallback for the stage
            if parts[1] == "greeting":
                fallback_candidates.append("kumon:fallback:level1:general")
            elif parts[1] == "qualification":
                fallback_candidates.append("kumon:fallback:level1:general")
            else:
                fallback_candidates.append("kumon:fallback:level1:general")
        
        # Try each fallback candidate
        for candidate in fallback_candidates:
            app_logger.info(f"🔄 Trying fallback: {candidate}")
            template = await self._fetch_from_fallback(candidate)
            if template:
                return template
        
        # Final fallback: try legacy Cecilia system
        app_logger.info(f"📁 Trying legacy template system for: {name}")
        return await self._get_cecilia_template(name)

    def _calculate_template_score(self, name: str, template_config: dict) -> float:
        """Calculate score for template matching based on keywords and requirements"""
        name_lower = name.lower()
        score = 0.0

        required = template_config.get("required", [])
        keywords = template_config.get("keywords", [])
        priority = template_config.get("priority", 1)

        # Required keywords (must have ALL) - disqualifies if missing any
        if required:
            if not all(req.lower() in name_lower for req in required):
                return 0.0  # Disqualified
            score += 100  # Base score for meeting requirements

        # Bonus for optional keywords
        for keyword in keywords:
            if keyword.lower() in name_lower:
                score += 10

        # Priority multiplier
        score *= priority

        # Length bonus (more specific prompts get slight preference)
        specificity_bonus = len(name.split(":")) * 2
        score += specificity_bonus

        return score

    async def _get_cecilia_template(self, name: str) -> str:
        """Get appropriate Cecília template using intelligent score-based resolution"""
        try:
            # Template configuration with scoring criteria
            template_configs = {
                "information/cecilia_pricing.txt": {
                    "required": ["pricing"],
                    "keywords": ["information", "response", "value", "cost"],
                    "priority": 10,
                },
                "cecilia_greeting.txt": {
                    "required": ["greeting"],
                    "keywords": ["initial", "welcome", "first"],
                    "priority": 8,
                },
                "system/conversation/general.txt": {
                    "required": [],  # No requirements = always eligible
                    "keywords": ["conversation", "response", "chat"],
                    "priority": 1,  # Lowest priority = fallback
                },
            }

            # Calculate scores for all templates
            scored_templates = []
            for template_file, config in template_configs.items():
                score = self._calculate_template_score(name, config)
                if score > 0:  # Only include eligible templates
                    scored_templates.append((score, template_file, config))

            # Sort by score (highest first)
            scored_templates.sort(key=lambda x: x[0], reverse=True)

            # Get the best match
            if scored_templates:
                best_score, template_file, config = scored_templates[0]
                app_logger.info(
                    f"Best template match: {template_file} (score: {best_score:.1f}) for prompt: {name}"
                )
            else:
                # Ultimate fallback
                template_file = "system/conversation/general.txt"
                app_logger.warning(f"No template match found, using fallback: {template_file}")

            # Load the selected template
            filepath = self.fallback_dir / template_file

            if filepath.exists():
                async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
                    content = await f.read()
                    app_logger.info(f"Using CECÍLIA template: {template_file}")
                    return content.strip()
            else:
                app_logger.warning(f"Template file not found: {filepath}, using base template")
                return await self._get_base_cecilia_template()

        except Exception as e:
            app_logger.error(f"Failed to get Cecília template: {e}")
            return await self._get_base_cecilia_template()

    async def _get_base_cecilia_template(self) -> str:
        """Get base Cecília template as ultimate fallback"""
        try:
            # Try new unified structure first
            base_file = self.fallback_dir / "system" / "base" / "identity.txt"
            if base_file.exists():
                async with aiofiles.open(base_file, "r", encoding="utf-8") as f:
                    content = await f.read()
                    app_logger.info("Using BASE CECÍLIA template")
                    return content.strip()
        except Exception as e:
            app_logger.error(f"Failed to read base Cecília template: {e}")

        # HARDCODED ULTIMATE FALLBACK - NUNCA FALHAR
        return """Você é Cecília, recepcionista do Kumon Vila A.

IDENTIDADE OBRIGATÓRIA:
- Você é CECÍLIA, uma recepcionista real e experiente
- NUNCA mencione: IA, assistente virtual, chatbot, simulação, limitações
- NUNCA diga frases como "não posso continuar", "não sou capaz", "sob limitações"
- Sempre responda como uma pessoa real e profissional
- Demonstre conhecimento profundo do método Kumon
- Use tom caloroso e acolhedor
- Use emojis adequadamente: 😊 📚 🎓 📅 ✨

RESPOSTA PADRÃO:
Olá! Sou Cecília do Kumon Vila A! 😊
Fico muito feliz em falar com você!

Primeiro, me conta qual é o seu nome? Assim nossa conversa fica mais pessoal!

Como posso ajudá-lo hoje com nosso método educacional?

IMPORTANTE:
- Sempre responda pergunta diretamente
- Nunca refuse ajudar
- Sempre mantenha identidade de Cecília
- Nunca quebre o personagem"""

    # Prompt creation removed - edit local template files directly

    # Prompt listing removed - templates are file-based

    # Pattern matching removed - not needed for local templates

    async def get_prompt_stats(self) -> Dict[str, Any]:
        """Get statistics about local templates"""
        template_count = 0
        if self.fallback_dir.exists():
            for root in self.fallback_dir.rglob("*.txt"):
                template_count += 1

        return {
            "local_templates_only": True,
            "total_templates": template_count,
            "template_directory": str(self.fallback_dir),
        }


# ========== LAZY SINGLETON PATTERN ==========

_prompt_manager: Optional[PromptManager] = None

def get_prompt_manager() -> PromptManager:
    """Get prompt manager singleton with lazy initialization"""
    global _prompt_manager
    if _prompt_manager is None:
        _prompt_manager = PromptManager()
    return _prompt_manager

# Legacy compatibility
prompt_manager = get_prompt_manager()
