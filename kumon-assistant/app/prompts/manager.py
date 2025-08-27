"""
LangSmith Prompt Manager for Kumon Assistant

This module provides centralized prompt management with:
- LangSmith Hub integration for versioned prompts
- Local fallback templates for offline operation
- Intelligent caching for performance
- Template variable substitution
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import hashlib
import aiofiles

from langsmith import Client as LangSmithClient
from langchain.prompts import PromptTemplate

from ..core.config import settings
from ..core.logger import app_logger


class PromptManager:
    """Manages prompts from LangSmith with local fallback"""
    
    def __init__(self):
        self.client = None
        self.cache = {}
        self.cache_file = Path("cache/prompts/langsmith_cache.json")
        self.fallback_dir = Path("app/prompts/templates")
        self.cache_ttl = 3600  # 1 hour cache TTL
        
        # Initialize client if API key is available
        if settings.LANGSMITH_API_KEY:
            try:
                self.client = LangSmithClient(
                    api_url=settings.LANGSMITH_ENDPOINT,
                    api_key=settings.LANGSMITH_API_KEY
                )
                app_logger.info("LangSmith client initialized successfully")
            except Exception as e:
                app_logger.error(f"Failed to initialize LangSmith client: {e}")
                self.client = None
        else:
            app_logger.warning("LANGSMITH_API_KEY not set. Using fallback templates only.")
        
        # Ensure cache directory exists
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.fallback_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache will be loaded lazily on first use
    
    async def _load_cache(self) -> None:
        """Load prompt cache from disk"""
        try:
            if self.cache_file.exists():
                async with aiofiles.open(self.cache_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    self.cache = json.loads(content)
                    app_logger.info(f"Loaded {len(self.cache)} prompts from cache")
        except Exception as e:
            app_logger.error(f"Failed to load prompt cache: {e}")
            self.cache = {}
    
    async def _save_cache(self) -> None:
        """Save prompt cache to disk"""
        try:
            async with aiofiles.open(self.cache_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.cache, ensure_ascii=False, indent=2))
        except Exception as e:
            app_logger.error(f"Failed to save prompt cache: {e}")
    
    def _get_cache_key(self, name: str, tag: str = "prod") -> str:
        """Generate cache key for prompt"""
        return f"{name}:{tag}"
    
    def _is_cache_valid(self, cache_entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid"""
        if "timestamp" not in cache_entry:
            return False
        
        cache_time = datetime.fromisoformat(cache_entry["timestamp"])
        return datetime.now() - cache_time < timedelta(seconds=self.cache_ttl)
    
    async def get_prompt(
        self, 
        name: str, 
        tag: str = "prod",
        variables: Optional[Dict[str, Any]] = None,
        fallback_enabled: bool = True
    ) -> str:
        """
        Get a prompt from LangSmith Hub with fallback to local templates
        
        Args:
            name: Prompt name (e.g., 'kumon:greeting:welcome:initial')
            tag: Version tag (e.g., 'prod', 'dev', 'v1.0.0')
            variables: Variables to substitute in template
            fallback_enabled: Whether to use local fallback if LangSmith fails
            
        Returns:
            Formatted prompt string
        """
        # Load cache on first use if empty
        if not self.cache:
            await self._load_cache()
            
        cache_key = self._get_cache_key(name, tag)
        
        # FORÇAR CECÍLIA: Sempre usar templates da Cecília devido a problemas com LangSmith
        app_logger.info(f"FORÇANDO uso do template CECÍLIA para: {name}")
        prompt_template = await self._get_cecilia_template(name)
        
        if prompt_template is None:
            # ÚLTIMO RECURSO: Template base da Cecília
            app_logger.error(f"Cecília template failed for {name}, using BASE CECÍLIA")
            prompt_template = await self._get_base_cecilia_template()
            
            # Cache the result
            self.cache[cache_key] = {
                "template": prompt_template,
                "timestamp": datetime.now().isoformat()
            }
            asyncio.create_task(self._save_cache())
        
        # Apply variables if provided
        if variables:
            try:
                # Use LangChain PromptTemplate for safe variable substitution
                template = PromptTemplate.from_template(prompt_template)
                return template.format(**variables)
            except Exception as e:
                app_logger.error(f"Failed to format prompt template: {e}")
                # Fallback to simple string formatting
                return prompt_template.format(**variables)
        
        return prompt_template
    
    async def _fetch_from_langsmith(
        self, 
        name: str, 
        tag: str = "prod"
    ) -> Optional[str]:
        """Fetch prompt from LangSmith Hub"""
        if not self.client:
            return None
        
        try:
            # Try to get the prompt by name (sem tag funciona melhor)
            try:
                prompt = self.client.pull_prompt(name)
            except:
                # Fallback para formato com tag
                prompt = self.client.pull_prompt(f"{name}:{tag}")
            
            if hasattr(prompt, 'template'):
                app_logger.info(f"Fetched prompt from LangSmith: {name}:{tag}")
                return prompt.template
            elif hasattr(prompt, 'messages') and prompt.messages:
                # Handle ChatPromptTemplate
                if hasattr(prompt.messages[0], 'prompt'):
                    return prompt.messages[0].prompt.template
                return str(prompt.messages[0])
            else:
                app_logger.warning(f"Unexpected prompt format from LangSmith: {name}")
                return None
                
        except Exception as e:
            app_logger.error(f"Failed to fetch prompt from LangSmith: {name}:{tag} - {e}")
            return None
    
    async def _fetch_from_fallback(self, name: str) -> Optional[str]:
        """Fetch prompt from local fallback templates"""
        try:
            # Convert prompt name to file path
            # kumon:greeting:welcome:initial -> greeting/welcome_initial.txt
            parts = name.split(':')[1:]  # Remove 'kumon' prefix
            if len(parts) >= 3:
                stage, type_name, variant = parts[0], parts[1], parts[2]
                filename = f"{type_name}_{variant}.txt"
                filepath = self.fallback_dir / stage / filename
            else:
                # Fallback naming
                filepath = self.fallback_dir / f"{name.replace(':', '_')}.txt"
            
            if filepath.exists():
                async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    app_logger.info(f"Using fallback template: {filepath}")
                    return content.strip()
            else:
                app_logger.warning(f"Fallback template not found: {filepath}")
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
                    "priority": 10
                },
                "cecilia_greeting.txt": {
                    "required": ["greeting"],
                    "keywords": ["initial", "welcome", "first"],
                    "priority": 8
                },
                "cecilia_conversation.txt": {
                    "required": [],  # No requirements = always eligible
                    "keywords": ["conversation", "response", "chat"],
                    "priority": 1  # Lowest priority = fallback
                }
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
                app_logger.info(f"Best template match: {template_file} (score: {best_score:.1f}) for prompt: {name}")
            else:
                # Ultimate fallback
                template_file = "cecilia_conversation.txt"
                app_logger.warning(f"No template match found, using fallback: {template_file}")
            
            # Load the selected template
            filepath = self.fallback_dir / template_file
            
            if filepath.exists():
                async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
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
            base_file = self.fallback_dir / "cecilia_base_system.txt"
            if base_file.exists():
                async with aiofiles.open(base_file, 'r', encoding='utf-8') as f:
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
    
    async def create_prompt(
        self, 
        name: str, 
        template: str, 
        tags: Optional[List[str]] = None,
        description: Optional[str] = None
    ) -> bool:
        """
        Create or update a prompt in LangSmith Hub
        
        Args:
            name: Prompt name
            template: Prompt template content
            tags: List of tags to apply
            description: Optional description
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            app_logger.error("Cannot create prompt: LangSmith client not initialized")
            return False
        
        try:
            from langchain.prompts import PromptTemplate as LCPromptTemplate
            
            # Create LangChain PromptTemplate
            lc_prompt = LCPromptTemplate.from_template(template)
            
            # Push to LangSmith using correct API
            self.client.push_prompt(name, object=lc_prompt, tags=tags, description=description)
            
            # Clear cache for this prompt
            cache_keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"{name}:")]
            for key in cache_keys_to_remove:
                del self.cache[key]
            
            app_logger.info(f"Created/updated prompt in LangSmith: {name}")
            return True
            
        except Exception as e:
            app_logger.error(f"Failed to create prompt in LangSmith: {name} - {e}")
            return False
    
    async def list_prompts(
        self, 
        pattern: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[str]:
        """
        List available prompts
        
        Args:
            pattern: Optional name pattern to filter (e.g., 'kumon:greeting:*')
            tags: Optional tags to filter by
            
        Returns:
            List of prompt names
        """
        prompts = []
        
        # Add cached prompts
        for cache_key in self.cache.keys():
            name = cache_key.split(':')[:-1]  # Remove tag
            name = ':'.join(name)
            if pattern is None or self._matches_pattern(name, pattern):
                prompts.append(name)
        
        # Add LangSmith prompts if available
        if self.client:
            try:
                # This would require LangSmith API to support listing prompts
                # For now, we rely on cache and fallback files
                pass
            except Exception as e:
                app_logger.error(f"Failed to list prompts from LangSmith: {e}")
        
        return list(set(prompts))  # Remove duplicates
    
    def _matches_pattern(self, name: str, pattern: str) -> bool:
        """Check if name matches pattern (simple wildcard support)"""
        if '*' not in pattern:
            return name == pattern
        
        # Simple wildcard matching
        pattern_parts = pattern.split('*')
        if len(pattern_parts) == 2:
            prefix, suffix = pattern_parts
            return name.startswith(prefix) and name.endswith(suffix)
        
        return False
    
    async def get_prompt_stats(self) -> Dict[str, Any]:
        """Get statistics about prompt usage and cache"""
        fallback_count = 0
        if self.fallback_dir.exists():
            for stage_dir in self.fallback_dir.iterdir():
                if stage_dir.is_dir():
                    fallback_count += len(list(stage_dir.glob('*.txt')))
        
        return {
            "langsmith_enabled": self.client is not None,
            "cached_prompts": len(self.cache),
            "fallback_templates": fallback_count,
            "cache_ttl": self.cache_ttl,
            "cache_file": str(self.cache_file)
        }


# Global instance
prompt_manager = PromptManager()