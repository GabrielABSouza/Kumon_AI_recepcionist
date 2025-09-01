"""
LangSmith Prompt Manager for Kumon Assistant

This module provides centralized prompt management with:
- LangSmith Hub integration for versioned prompts
- Local fallback templates for offline operation
- Intelligent caching for performance
- Template variable substitution
"""

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
        self.cache = {}
        self.fallback_dir = Path("app/prompts/templates")

        app_logger.info("Prompt manager initialized with local templates only")
        self.fallback_dir.mkdir(parents=True, exist_ok=True)

        # Cache will be loaded lazily on first use

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
        # LOCAL TEMPLATES ONLY - Simple and reliable approach
        prompt_template = None
        
        # Try new structured template system first
        prompt_template = await self._fetch_from_fallback(name)
        
        # If structured template not found, try legacy Cecília template system
        if not prompt_template:
            app_logger.info(f"📁 Trying legacy template system for: {name}")
            prompt_template = await self._get_cecilia_template(name)

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
                    # Use LangChain PromptTemplate for safe variable substitution
                    template = PromptTemplate.from_template(prompt_template)
                    formatted_prompt = template.format(**resolved_variables)
                    app_logger.info(
                        f"Applied {len(resolved_variables)} variables to template: {name}"
                    )
                    # CRITICAL: Apply safety filter before returning
                    return ensure_safe_template(formatted_prompt, self._get_context_from_name(name))
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

    async def _fetch_from_fallback(self, name: str) -> Optional[str]:
        """Fetch prompt from local fallback templates with unified 1:1 mapping"""
        try:
            # Convert prompt name to file path with 1:1 mapping
            # kumon:greeting:welcome:initial -> greeting/welcome/initial.txt
            # kumon:system:conversation:general -> system/conversation/general.txt
            parts = name.split(":")[1:]  # Remove 'kumon' prefix

            if len(parts) >= 3:
                # Unified structure: category/subcategory/specific.txt
                category, subcategory, specific = parts[0], parts[1], parts[2]
                filepath = self.fallback_dir / category / subcategory / f"{specific}.txt"

                if filepath.exists():
                    async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
                        content = await f.read()
                        app_logger.info(f"✅ Using unified template: {filepath}")
                        return content.strip()

            # Special mapping for legacy system templates and fallbacks
            legacy_mappings = {
                "kumon:conversation:general": "system/conversation/general.txt",
                "kumon:system:base:identity": "system/base/identity.txt",
                "kumon:fallback:level1:general": "fallback/cecilia_fallback_general.txt",
                "kumon:fallback:level2:basic": "fallback/cecilia_fallback_level2_menu.txt",
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


# Global instance
prompt_manager = PromptManager()
