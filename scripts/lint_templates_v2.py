#!/usr/bin/env python3
"""
Template Linter V2 - Advanced Template Validation

Comprehensive template linting system with metadata validation, security checks,
and CI integration. Replaces the basic mustache-only linter.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.core.prompts.template_loader import template_loader
    from app.core.prompts.template_key import TemplateKey
    from app.core.prompts.variable_policy import variable_policy, ConversationStage
    import yaml
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


class TemplateLintError(Exception):
    """Template linting error"""
    pass


class TemplateLinter:
    """
    Advanced template linter with security and quality checks
    """
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.total_files = 0
        self.failed_files = 0
        
        # Linting rules configuration
        self.rules = {
            'require_front_matter': True,
            'require_kind_field': True,
            'forbid_mustache': True,
            'forbid_config_in_user_paths': True,
            'validate_variable_policy': True,
            'require_description': True,
            'validate_yaml_syntax': True,
            'check_placeholder_syntax': True
        }
    
    def lint_directory(self, directory: Path, pattern: str = "*.txt") -> Dict[str, Any]:
        """
        Lint all templates in a directory
        
        Args:
            directory: Directory to scan
            pattern: File pattern to match
            
        Returns:
            Linting report
        """
        if not directory.exists():
            raise TemplateLintError(f"Directory does not exist: {directory}")
        
        template_files = list(directory.rglob(pattern))
        self.total_files = len(template_files)
        
        print(f"Linting {self.total_files} template files in {directory}")
        
        file_results = []
        
        for template_file in template_files:
            try:
                result = self.lint_file(template_file)
                file_results.append(result)
                
                if not result['valid']:
                    self.failed_files += 1
                
            except Exception as e:
                self.failed_files += 1
                error_result = {
                    'file': str(template_file.relative_to(directory)),
                    'valid': False,
                    'errors': [f"Failed to lint file: {e}"],
                    'warnings': []
                }
                file_results.append(error_result)
                self.errors.append(f"{template_file.relative_to(directory)}: {e}")
        
        # Generate summary report
        return self._generate_report(file_results, directory)
    
    def lint_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Lint a single template file
        
        Returns:
            File linting result
        """
        result = {
            'file': str(file_path.name),
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try to infer template key from path
            template_key = self._infer_template_key(file_path)
            
            # Run all linting checks
            self._check_front_matter(content, result)
            self._check_mustache_variables(content, result)
            self._check_configuration_placement(file_path, content, result)
            self._check_placeholder_syntax(content, result)
            self._check_variable_policy(content, template_key, result)
            self._check_content_quality(content, result)
            
            # Set overall validity
            result['valid'] = len(result['errors']) == 0
            
        except Exception as e:
            result['valid'] = False
            result['errors'].append(f"File processing error: {e}")
        
        return result
    
    def _check_front_matter(self, content: str, result: Dict[str, Any]) -> None:
        """Check YAML front-matter requirements"""
        
        front_matter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        
        if not front_matter_match and self.rules['require_front_matter']:
            result['errors'].append("Missing YAML front-matter - all templates must include metadata")
            return
        
        if front_matter_match:
            yaml_content = front_matter_match.group(1)
            
            # Validate YAML syntax
            if self.rules['validate_yaml_syntax']:
                try:
                    metadata = yaml.safe_load(yaml_content)
                    if not isinstance(metadata, dict):
                        result['errors'].append("Front-matter must be a YAML dictionary")
                        return
                except yaml.YAMLError as e:
                    result['errors'].append(f"Invalid YAML syntax in front-matter: {e}")
                    return
            else:
                metadata = {}
            
            # Check required fields
            if self.rules['require_kind_field'] and 'kind' not in metadata:
                result['errors'].append("Missing required 'kind' field in front-matter")
            
            if self.rules['require_description'] and not metadata.get('description', '').strip():
                result['warnings'].append("Missing or empty 'description' field in front-matter")
            
            # Validate kind value
            kind = metadata.get('kind', '').lower()
            if kind and kind not in ['content', 'configuration', 'fragment']:
                result['errors'].append(f"Invalid 'kind' value: {kind}. Must be 'content', 'configuration', or 'fragment'")
            
            # Check context value
            context = metadata.get('context', '').lower()
            if context:
                valid_contexts = [stage.value for stage in ConversationStage]
                if context not in valid_contexts and context != 'system':
                    result['warnings'].append(f"Unknown context '{context}'. Valid contexts: {valid_contexts}")
    
    def _check_mustache_variables(self, content: str, result: Dict[str, Any]) -> None:
        """Check for forbidden mustache variables"""
        
        if not self.rules['forbid_mustache']:
            return
        
        mustache_vars = re.findall(r'\{\{[^}]+\}\}', content)
        
        if mustache_vars:
            result['errors'].append(f"Mustache variables forbidden: {mustache_vars}")
            result['errors'].append("Use standard placeholder syntax {variable} instead of {{variable}}")
    
    def _check_configuration_placement(self, file_path: Path, content: str, result: Dict[str, Any]) -> None:
        """Check for configuration templates in user-facing paths"""
        
        if not self.rules['forbid_config_in_user_paths']:
            return
        
        # Extract kind from front-matter
        front_matter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        
        if front_matter_match:
            try:
                metadata = yaml.safe_load(front_matter_match.group(1))
                kind = metadata.get('kind', '').lower()
            except:
                kind = ''
        else:
            kind = ''
        
        # Check if configuration template is in user-facing path
        path_str = str(file_path).lower()
        is_user_facing = any(segment in path_str for segment in ['kumon/', 'greeting/', 'qualification/', 'information/'])
        
        if kind == 'configuration' and is_user_facing:
            result['errors'].append("Configuration template (kind=configuration) found in user-facing path")
            result['errors'].append("Configuration templates should be in system/ or internal/ directories")
    
    def _check_placeholder_syntax(self, content: str, result: Dict[str, Any]) -> None:
        """Check placeholder syntax consistency"""
        
        if not self.rules['check_placeholder_syntax']:
            return
        
        # Find all placeholder patterns
        standard_vars = re.findall(r'\{([^}|?!:]+)\}', content)
        conditional_vars = re.findall(r'\{([?!][^}:]+):', content)
        default_vars = re.findall(r'\{([^}|?!:]+)\|[^}]+\}', content)
        bracket_vars = re.findall(r'\[\[([^\]]+)\]\]', content)
        
        # Warn about bracket-style variables (should be migrated)
        if bracket_vars:
            result['warnings'].append(f"Old bracket-style variables found: {bracket_vars}")
            result['warnings'].append("Consider migrating to standard {variable} syntax")
        
        # Check for malformed conditionals
        malformed_conditionals = re.findall(r'\{[?!][^}:]*\}', content)  # Missing colon
        if malformed_conditionals:
            result['errors'].append(f"Malformed conditional syntax: {malformed_conditionals}")
            result['errors'].append("Conditionals must have format {{?variable: content}} or {{!variable: content}}")
    
    def _check_variable_policy(self, content: str, template_key: Optional[TemplateKey], result: Dict[str, Any]) -> None:
        """Check variable policy compliance"""
        
        if not self.rules['validate_variable_policy'] or not template_key:
            return
        
        # Infer stage from template key
        stage = template_key.context if template_key.context in [s.value for s in ConversationStage] else 'greeting'
        
        try:
            # Validate template variables against policy
            validation = variable_policy.validate_template_variables(content, stage)
            
            for violation in validation.get('violations', []):
                result['errors'].append(f"Variable policy violation: {violation['variable']} "
                                      f"({violation['category']}) - {violation['reason']}")
            
            for warning in validation.get('warnings', []):
                result['warnings'].append(f"Variable policy warning: {warning['variable']} "
                                        f"({warning['category']}) - {warning['reason']}")
                
        except Exception as e:
            result['warnings'].append(f"Variable policy check failed: {e}")
    
    def _check_content_quality(self, content: str, result: Dict[str, Any]) -> None:
        """Check general content quality"""
        
        # Remove front-matter for content checks
        content_only = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
        
        # Check for empty content
        if not content_only.strip():
            result['errors'].append("Template content is empty")
            return
        
        # Check for extremely short content
        if len(content_only.strip()) < 10:
            result['warnings'].append("Template content is very short (< 10 characters)")
        
        # Check for potential encoding issues
        if '�' in content:
            result['warnings'].append("Possible encoding issues detected (replacement characters found)")
        
        # Check for common issues
        if content_only.count('\n') > 50:
            result['warnings'].append("Template is very long (>50 lines) - consider breaking into fragments")
        
        # Check for consistent line endings
        if '\r\n' in content and '\n' in content.replace('\r\n', ''):
            result['warnings'].append("Mixed line endings detected - use consistent line endings")
    
    def _infer_template_key(self, file_path: Path) -> Optional[TemplateKey]:
        """Try to infer template key from file path"""
        
        try:
            # Get path relative to templates directory
            path_parts = file_path.parts
            
            # Find templates directory in path
            templates_idx = None
            for i, part in enumerate(path_parts):
                if part == 'templates':
                    templates_idx = i
                    break
            
            if templates_idx is None or templates_idx + 1 >= len(path_parts):
                return None
            
            # Extract path after templates/
            template_path_parts = path_parts[templates_idx + 1:]
            
            if len(template_path_parts) >= 2:
                # kumon/greeting/response_general.txt
                namespace = template_path_parts[0]
                context = template_path_parts[1]
                filename = template_path_parts[-1]
                
                # Parse filename
                name_without_ext = Path(filename).stem
                if '_' in name_without_ext:
                    parts = name_without_ext.split('_')
                    category = parts[0] if len(parts) > 1 else 'response'
                    name_parts = parts[1:]
                    
                    # Check if last part is a variant
                    variant = None
                    if name_parts and name_parts[-1] in ['neutral', 'personalized', 'friendly', 'formal']:
                        variant = name_parts[-1]
                        name = '_'.join(name_parts[:-1])
                    else:
                        name = '_'.join(name_parts)
                else:
                    category = 'response'
                    name = name_without_ext
                    variant = None
                
                return TemplateKey(
                    namespace=namespace,
                    context=context,
                    category=category,
                    name=name,
                    variant=variant
                )
        
        except Exception:
            return None
        
        return None
    
    def _generate_report(self, file_results: List[Dict[str, Any]], directory: Path) -> Dict[str, Any]:
        """Generate comprehensive linting report"""
        
        passed_files = [r for r in file_results if r['valid']]
        failed_files = [r for r in file_results if not r['valid']]
        
        all_errors = []
        all_warnings = []
        
        for result in file_results:
            for error in result['errors']:
                all_errors.append(f"{result['file']}: {error}")
            for warning in result['warnings']:
                all_warnings.append(f"{result['file']}: {warning}")
        
        return {
            'summary': {
                'total_files': self.total_files,
                'passed_files': len(passed_files),
                'failed_files': len(failed_files),
                'success_rate': f"{len(passed_files)/self.total_files*100:.1f}%" if self.total_files > 0 else "0%"
            },
            'linting_passed': len(failed_files) == 0,
            'errors': all_errors,
            'warnings': all_warnings,
            'file_results': file_results,
            'rules_applied': self.rules
        }


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Template Linter V2 - Advanced Template Validation")
    parser.add_argument("path", nargs="?", default="app/prompts/templates",
                       help="Path to templates directory (default: app/prompts/templates)")
    parser.add_argument("--strict", action="store_true",
                       help="Strict mode - fail on warnings")
    parser.add_argument("--pattern", default="*.txt",
                       help="File pattern to match (default: *.txt)")
    parser.add_argument("--output", type=str,
                       help="Output report to JSON file")
    parser.add_argument("--rules", type=str,
                       help="JSON file with custom linting rules")
    parser.add_argument("--quiet", action="store_true",
                       help="Quiet mode - only show summary")
    parser.add_argument("--ci", action="store_true",
                       help="CI mode - optimized output for continuous integration")
    
    args = parser.parse_args()
    
    # Initialize linter
    linter = TemplateLinter()
    
    # Load custom rules if provided
    if args.rules:
        try:
            with open(args.rules, 'r') as f:
                custom_rules = json.load(f)
                linter.rules.update(custom_rules)
                print(f"Loaded custom rules from {args.rules}")
        except Exception as e:
            print(f"Failed to load custom rules: {e}")
            sys.exit(1)
    
    # Run linting
    try:
        templates_path = Path(args.path)
        report = linter.lint_directory(templates_path, args.pattern)
        
        # Output handling
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Report saved to {args.output}")
        
        # Console output
        if not args.quiet:
            if args.ci:
                # CI-friendly output
                print(f"Template Linting Results:")
                print(f"Files processed: {report['summary']['total_files']}")
                print(f"Passed: {report['summary']['passed_files']}")
                print(f"Failed: {report['summary']['failed_files']}")
                print(f"Success rate: {report['summary']['success_rate']}")
                
                if report['errors']:
                    print(f"\nErrors ({len(report['errors'])}):")
                    for error in report['errors']:
                        print(f"  ❌ {error}")
                
                if report['warnings']:
                    print(f"\nWarnings ({len(report['warnings'])}):")
                    for warning in report['warnings']:
                        print(f"  ⚠️  {warning}")
            else:
                # Detailed output
                print(f"\n{'='*60}")
                print(f"TEMPLATE LINTING REPORT")
                print(f"{'='*60}")
                print(f"Total files: {report['summary']['total_files']}")
                print(f"Passed: {report['summary']['passed_files']} ✅")
                print(f"Failed: {report['summary']['failed_files']} ❌")
                print(f"Success rate: {report['summary']['success_rate']}")
                
                if report['errors']:
                    print(f"\n🚨 ERRORS ({len(report['errors'])}):")
                    for error in report['errors']:
                        print(f"  {error}")
                
                if report['warnings']:
                    print(f"\n⚠️  WARNINGS ({len(report['warnings'])}):")
                    for warning in report['warnings']:
                        print(f"  {warning}")
                
                print(f"\n{'='*60}")
        
        # Determine exit code
        exit_code = 0
        
        if not report['linting_passed']:
            exit_code = 1
        elif args.strict and report['warnings']:
            exit_code = 1
            print("STRICT MODE: Failing due to warnings")
        
        if exit_code == 0:
            print("✅ All templates passed linting!")
        else:
            print("❌ Template linting failed!")
        
        sys.exit(exit_code)
        
    except Exception as e:
        print(f"❌ Linting failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()