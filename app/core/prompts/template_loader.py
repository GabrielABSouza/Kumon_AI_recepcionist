"""
Template Loader with Front-Matter Support

Loads templates with YAML front-matter metadata and canonical key resolution.
Supports fail-soft loading with fallback mechanisms.
"""
from __future__ import annotations

import re
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from ...core.logger import app_logger
from .template_key import (
    TemplateKey,
    TemplateKind,
    TemplateContext,
    TemplateMetadata,
    template_registry
)


class TemplateLoadError(Exception):
    """Template loading error"""
    pass


class TemplateLoader:
    """
    Loads templates with front-matter metadata support
    """
    
    def __init__(self, base_path: Union[str, Path] = "app/prompts/templates"):
        self.base_path = Path(base_path)
        self._content_cache: Dict[str, Tuple[str, TemplateMetadata]] = {}
        
    def load_template(self, key: Union[str, TemplateKey]) -> Tuple[str, TemplateMetadata]:
        """
        Load template content and metadata
        
        Args:
            key: Template key (canonical or alias)
            
        Returns:
            Tuple of (content, metadata)
            
        Raises:
            TemplateLoadError: If template cannot be loaded
        """
        # Resolve to canonical key
        resolved_key = template_registry.resolve_key(key)
        canonical = resolved_key.to_canonical()
        
        # Check cache first
        if canonical in self._content_cache:
            return self._content_cache[canonical]
        
        # Try to find template file
        template_path = self._find_template_file(resolved_key)
        if not template_path:
            # Try fallback to neutral variant
            neutral_key = resolved_key.to_neutral_variant()
            template_path = self._find_template_file(neutral_key)
            if template_path:
                app_logger.info(f"Template fallback: {canonical} → {neutral_key.to_canonical()}")
                resolved_key = neutral_key
                canonical = neutral_key.to_canonical()
            
        if not template_path:
            raise TemplateLoadError(f"Template not found: {canonical}")
        
        # Load and parse template
        content, metadata = self._load_and_parse_file(template_path, resolved_key)
        
        # Cache result
        self._content_cache[canonical] = (content, metadata)
        template_registry.set_metadata(canonical, metadata)
        
        app_logger.debug(f"Template loaded: {canonical} from {template_path}")
        return content, metadata
    
    def _find_template_file(self, key: TemplateKey) -> Optional[Path]:
        """Find template file for given key"""
        # Generate possible paths based on key structure
        possible_paths = [
            # kumon/greeting/response_general.txt
            f"{key.namespace}/{key.context}/{key.category}_{key.name}.txt",
            # kumon/greeting/response_general_neutral.txt (with variant)
            f"{key.namespace}/{key.context}/{key.category}_{key.name}_{key.variant}.txt" if key.variant else None,
            # greeting/response/general.txt
            f"{key.context}/{key.category}/{key.name}.txt",
            # greeting/response_general.txt 
            f"{key.context}/{key.category}_{key.name}.txt",
            # Legacy paths
            f"{key.context}/{key.name}.txt",
        ]
        
        # Filter out None values
        possible_paths = [p for p in possible_paths if p]
        
        # Try each path
        for path_str in possible_paths:
            full_path = self.base_path / path_str
            if full_path.exists():
                return full_path
                
        return None
    
    def _load_and_parse_file(self, file_path: Path, key: TemplateKey) -> Tuple[str, TemplateMetadata]:
        """Load and parse template file with front-matter"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_content = f.read()
        except Exception as e:
            raise TemplateLoadError(f"Failed to read template file {file_path}: {e}")
        
        # Parse front-matter if present
        content, metadata = self._parse_front_matter(raw_content, key, file_path)
        
        return content, metadata
    
    def _parse_front_matter(self, raw_content: str, key: TemplateKey, file_path: Path) -> Tuple[str, TemplateMetadata]:
        """Parse YAML front-matter from template content"""
        
        # Check for YAML front-matter
        front_matter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', raw_content, re.DOTALL)
        
        if front_matter_match:
            # Parse YAML metadata
            yaml_content = front_matter_match.group(1)
            template_content = front_matter_match.group(2)
            
            try:
                metadata_dict = yaml.safe_load(yaml_content) or {}
            except yaml.YAMLError as e:
                app_logger.warning(f"Invalid YAML front-matter in {file_path}: {e}")
                metadata_dict = {}
        else:
            # No front-matter, use full content
            template_content = raw_content
            metadata_dict = {}
        
        # Create metadata with defaults and inference
        metadata = self._create_metadata(metadata_dict, key, file_path)
        
        return template_content.strip(), metadata
    
    def _create_metadata(self, metadata_dict: Dict, key: TemplateKey, file_path: Path) -> TemplateMetadata:
        """Create TemplateMetadata with inference and validation"""
        
        # Parse kind with validation
        kind_str = metadata_dict.get('kind', '').lower()
        if kind_str in ['content', 'configuration', 'fragment']:
            kind = TemplateKind(kind_str)
        else:
            # Infer kind from path
            kind = self._infer_template_kind(key, file_path)
        
        # Parse context
        context_str = metadata_dict.get('context', key.context).lower()
        try:
            context = TemplateContext(context_str)
        except ValueError:
            context = None
            app_logger.warning(f"Unknown context '{context_str}' in {file_path}")
        
        # Extract other metadata
        variant = metadata_dict.get('variant', key.variant)
        description = metadata_dict.get('description', '')
        variables = metadata_dict.get('variables', [])
        stage_restrictions = set(metadata_dict.get('stage_restrictions', []))
        
        return TemplateMetadata(
            kind=kind,
            context=context,
            variant=variant,
            description=description,
            variables=variables,
            stage_restrictions=stage_restrictions
        )
    
    def _infer_template_kind(self, key: TemplateKey, file_path: Path) -> TemplateKind:
        """Infer template kind from key and path"""
        
        # Configuration templates (never for user delivery)
        if 'system' in str(file_path).lower() or 'base' in key.category:
            return TemplateKind.CONFIGURATION
            
        # Fragment templates (partial content)
        if 'fragment' in str(file_path).lower() or key.category in ['fragment', 'partial']:
            return TemplateKind.FRAGMENT
            
        # Default to content for user-facing templates
        if key.namespace == 'kumon':
            return TemplateKind.CONTENT
            
        # Conservative default
        return TemplateKind.FRAGMENT
    
    def validate_template(self, key: Union[str, TemplateKey]) -> Dict[str, any]:
        """
        Validate a template and return validation report
        
        Returns:
            Validation report with issues and recommendations
        """
        try:
            content, metadata = self.load_template(key)
            resolved_key = template_registry.resolve_key(key)
            
            issues = []
            warnings = []
            
            # Check for mustache variables in content templates
            if metadata.kind == TemplateKind.CONTENT:
                mustache_vars = re.findall(r'\{\{[^}]+\}\}', content)
                if mustache_vars:
                    issues.append(f"Mustache variables found in content template: {mustache_vars}")
            
            # Check for configuration templates in user-facing paths
            if metadata.kind == TemplateKind.CONFIGURATION and resolved_key.namespace == 'kumon':
                issues.append("Configuration template in user-facing path")
            
            # Check for required front-matter
            if not metadata.description:
                warnings.append("Missing description in front-matter")
            
            # Check variables consistency
            content_vars = re.findall(r'\{([^}]+)\}', content)
            declared_vars = set(metadata.variables)
            found_vars = set(content_vars)
            
            undeclared_vars = found_vars - declared_vars
            if undeclared_vars:
                warnings.append(f"Undeclared variables in content: {list(undeclared_vars)}")
            
            return {
                'valid': len(issues) == 0,
                'key': resolved_key.to_canonical(),
                'kind': metadata.kind.value,
                'issues': issues,
                'warnings': warnings,
                'metadata': metadata
            }
            
        except TemplateLoadError as e:
            return {
                'valid': False,
                'key': str(key),
                'error': str(e),
                'issues': [f"Template load error: {e}"],
                'warnings': []
            }
    
    def list_templates(self, pattern: Optional[str] = None) -> List[Dict[str, any]]:
        """List all available templates with metadata"""
        templates = []
        
        # Scan template directory
        if not self.base_path.exists():
            return templates
            
        for template_file in self.base_path.rglob("*.txt"):
            try:
                # Try to infer key from path
                relative_path = template_file.relative_to(self.base_path)
                inferred_key = self._infer_key_from_path(relative_path)
                
                if pattern and not inferred_key.matches(pattern):
                    continue
                
                # Load template
                content, metadata = self._load_and_parse_file(template_file, inferred_key)
                
                templates.append({
                    'key': inferred_key.to_canonical(),
                    'path': str(relative_path),
                    'kind': metadata.kind.value,
                    'context': metadata.context.value if metadata.context else None,
                    'variant': metadata.variant,
                    'description': metadata.description,
                    'variables': metadata.variables
                })
                
            except Exception as e:
                app_logger.warning(f"Failed to process template {template_file}: {e}")
                continue
        
        return sorted(templates, key=lambda x: x['key'])
    
    def _infer_key_from_path(self, relative_path: Path) -> TemplateKey:
        """Infer template key from file path"""
        parts = relative_path.with_suffix('').parts
        
        if len(parts) >= 3:
            # kumon/greeting/response_general.txt
            namespace = parts[0] if parts[0] != 'templates' else 'kumon'
            context = parts[1]
            filename = parts[-1]
            
            # Parse filename
            if '_' in filename:
                category, name_variant = filename.split('_', 1)
                if '_' in name_variant:
                    name, variant = name_variant.rsplit('_', 1)
                else:
                    name, variant = name_variant, None
            else:
                category, name, variant = 'response', filename, None
                
        elif len(parts) == 2:
            # greeting/general.txt
            namespace = 'kumon'
            context = parts[0]
            category = 'response'
            name = parts[1]
            variant = None
        else:
            # general.txt
            namespace = 'kumon'
            context = 'greeting'
            category = 'response'
            name = parts[0]
            variant = None
        
        return TemplateKey(
            namespace=namespace,
            context=context,
            category=category,
            name=name,
            variant=variant
        )


# Global template loader instance
template_loader = TemplateLoader()


__all__ = [
    'TemplateLoader',
    'TemplateLoadError',
    'template_loader'
]