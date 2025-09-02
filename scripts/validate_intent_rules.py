#!/usr/bin/env python3
"""
Intent Rules Validation Script

Validates intent_rules.yaml against the JSON schema and performs
additional consistency checks for production readiness.

Usage:
    python3 scripts/validate_intent_rules.py
    python3 scripts/validate_intent_rules.py --path config/intent_rules.yaml
    python3 scripts/validate_intent_rules.py --verbose
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

import jsonschema
import yaml


class IntentRulesValidator:
    """Comprehensive intent rules validator"""
    
    def __init__(self, rules_path: str, schema_path: str, verbose: bool = False):
        self.rules_path = Path(rules_path)
        self.schema_path = Path(schema_path)
        self.verbose = verbose
        self.errors = []
        self.warnings = []
        
    def validate(self) -> bool:
        """
        Run complete validation suite.
        
        Returns:
            True if validation passes, False otherwise
        """
        print(f"🔍 Validating intent rules: {self.rules_path}")
        
        # Step 1: Load and parse files
        if not self._load_files():
            return False
            
        # Step 2: JSON Schema validation
        if not self._validate_schema():
            return False
            
        # Step 3: Business logic validation
        if not self._validate_business_rules():
            return False
            
        # Step 4: Performance validation
        if not self._validate_performance_requirements():
            return False
            
        # Step 5: Node coverage validation
        if not self._validate_node_coverage():
            return False
            
        # Summary
        self._print_summary()
        
        return len(self.errors) == 0
    
    def _load_files(self) -> bool:
        """Load YAML rules and JSON schema"""
        try:
            # Load rules
            if not self.rules_path.exists():
                self.errors.append(f"Rules file not found: {self.rules_path}")
                return False
                
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                self.rules = yaml.safe_load(f)
                
            # Load schema
            if not self.schema_path.exists():
                self.errors.append(f"Schema file not found: {self.schema_path}")
                return False
                
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                self.schema = json.load(f)
                
            if self.verbose:
                intents_count = len(self.rules.get('intents', []))
                print(f"✅ Loaded {intents_count} intent rules")
                
            return True
            
        except yaml.YAMLError as e:
            self.errors.append(f"YAML parsing error: {e}")
            return False
        except json.JSONDecodeError as e:
            self.errors.append(f"JSON schema parsing error: {e}")
            return False
        except Exception as e:
            self.errors.append(f"File loading error: {e}")
            return False
    
    def _validate_schema(self) -> bool:
        """Validate against JSON schema"""
        try:
            jsonschema.validate(self.rules, self.schema)
            if self.verbose:
                print("✅ JSON schema validation passed")
            return True
            
        except jsonschema.ValidationError as e:
            self.errors.append(f"Schema validation error: {e.message}")
            if hasattr(e, 'absolute_path') and e.absolute_path:
                path_str = ' -> '.join(str(p) for p in e.absolute_path)
                self.errors.append(f"  At path: {path_str}")
            return False
        except Exception as e:
            self.errors.append(f"Schema validation error: {e}")
            return False
    
    def _validate_business_rules(self) -> bool:
        """Validate business logic requirements"""
        success = True
        intents = self.rules.get('intents', [])
        
        # Check for duplicate rule IDs
        rule_ids = [intent['id'] for intent in intents]
        duplicates = [rule_id for rule_id in set(rule_ids) if rule_ids.count(rule_id) > 1]
        if duplicates:
            self.errors.append(f"Duplicate rule IDs found: {duplicates}")
            success = False
            
        # Validate prefilter_literal requirements
        for intent in intents:
            rule_id = intent['id']
            prefilter = intent.get('prefilter_literal', '')
            
            # Minimum 3 characters
            if len(prefilter) < 3:
                self.errors.append(f"Rule {rule_id}: prefilter_literal too short ({len(prefilter)} chars)")
                success = False
                
            # Should be lowercase normalized
            if prefilter != prefilter.lower():
                self.warnings.append(f"Rule {rule_id}: prefilter_literal should be lowercase")
        
        # Validate regex patterns
        for intent in intents:
            rule_id = intent['id']
            pattern = intent.get('pattern', '')
            
            try:
                re.compile(pattern)
            except re.error as e:
                self.errors.append(f"Rule {rule_id}: invalid regex pattern - {e}")
                success = False
                
            # Check for catastrophic backtracking patterns
            dangerous_patterns = [
                r'\(\.\*\)\+',  # (.*)+
                r'\(\.\+\)\*',  # (.+)*
                r'\(\w\+\)\+', # (\w+)+
            ]
            
            for dangerous in dangerous_patterns:
                if re.search(dangerous, pattern):
                    self.warnings.append(f"Rule {rule_id}: potentially dangerous regex pattern")
                    break
        
        # Validate priority distribution
        priorities = [intent.get('priority', 0) for intent in intents]
        priority_counts = defaultdict(int)
        for p in priorities:
            priority_counts[p] += 1
            
        # Warn about too many rules with same priority
        for priority, count in priority_counts.items():
            if count > 5:
                self.warnings.append(f"Priority {priority} used by {count} rules (collision risk)")
        
        if self.verbose and success:
            print("✅ Business rules validation passed")
            
        return success
    
    def _validate_performance_requirements(self) -> bool:
        """Validate performance-related requirements"""
        success = True
        intents = self.rules.get('intents', [])
        
        # Check total rule count (performance impact)
        rule_count = len(intents)
        if rule_count > 200:
            self.warnings.append(f"Large rule set ({rule_count}) may impact performance")
        elif rule_count < 10:
            self.warnings.append(f"Small rule set ({rule_count}) may have low coverage")
            
        # Check regex complexity
        complex_rules = 0
        for intent in intents:
            pattern = intent.get('pattern', '')
            # Simple heuristic: patterns with many groups, alternations, or quantifiers
            complexity_score = (
                pattern.count('(') +
                pattern.count('|') + 
                pattern.count('*') +
                pattern.count('+') +
                pattern.count('?')
            )
            
            if complexity_score > 15:
                complex_rules += 1
                self.warnings.append(f"Rule {intent['id']}: complex regex (score: {complexity_score})")
        
        if complex_rules > len(intents) * 0.2:  # More than 20% complex
            self.warnings.append(f"{complex_rules}/{rule_count} rules are complex (performance risk)")
            
        # Check prefilter uniqueness (collision detection)
        prefilters = [intent.get('prefilter_literal', '') for intent in intents]
        unique_prefilters = len(set(prefilters))
        if unique_prefilters < len(prefilters) * 0.8:  # Less than 80% unique
            collision_rate = (len(prefilters) - unique_prefilters) / len(prefilters)
            self.warnings.append(f"Prefilter collision rate: {collision_rate:.1%} (target: <5%)")
        
        if self.verbose and success:
            print("✅ Performance requirements validation passed")
            
        return success
    
    def _validate_node_coverage(self) -> bool:
        """Validate coverage of graph nodes"""
        try:
            # Import node enumeration
            sys.path.append(str(Path(__file__).parent.parent))
            from app.graph.nodes import enumerate_nodes
            
            # Get all available nodes
            available_nodes = enumerate_nodes()
            available_node_ids = {node['id'] for node in available_nodes}
            
            # Get nodes referenced in rules
            intents = self.rules.get('intents', [])
            referenced_nodes = set()
            
            for intent in intents:
                node_mapping = intent.get('node_mapping', [])
                referenced_nodes.update(node_mapping)
            
            # Check coverage
            missing_nodes = available_node_ids - referenced_nodes
            orphaned_references = referenced_nodes - available_node_ids
            
            coverage_rate = len(referenced_nodes & available_node_ids) / len(available_node_ids)
            
            if missing_nodes:
                self.warnings.append(f"Nodes without intent rules: {sorted(missing_nodes)}")
                
            if orphaned_references:
                self.errors.append(f"Invalid node references: {sorted(orphaned_references)}")
                return False
                
            if coverage_rate < 0.8:  # Less than 80% coverage
                self.warnings.append(f"Low node coverage: {coverage_rate:.1%} (target: >80%)")
            
            if self.verbose:
                print(f"✅ Node coverage: {coverage_rate:.1%} ({len(referenced_nodes)}/{len(available_node_ids)})")
                
            return True
            
        except Exception as e:
            self.warnings.append(f"Could not validate node coverage: {e}")
            return True  # Non-critical validation
    
    def _print_summary(self):
        """Print validation summary"""
        print(f"\n📊 Validation Summary:")
        print(f"   Errors: {len(self.errors)}")
        print(f"   Warnings: {len(self.warnings)}")
        
        if self.errors:
            print(f"\n❌ Errors:")
            for error in self.errors:
                print(f"   • {error}")
        
        if self.warnings:
            print(f"\n⚠️  Warnings:")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if not self.errors and not self.warnings:
            print("🎉 All validations passed!")
        elif not self.errors:
            print("✅ Validation passed with warnings")
        else:
            print("❌ Validation failed")


def main():
    parser = argparse.ArgumentParser(description="Validate intent rules configuration")
    parser.add_argument(
        "--path", 
        default="config/intent_rules.yaml",
        help="Path to intent rules YAML file"
    )
    parser.add_argument(
        "--schema",
        default="schemas/intent_rules_schema.json", 
        help="Path to JSON schema file"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Resolve paths relative to project root
    project_root = Path(__file__).parent.parent
    rules_path = project_root / args.path
    schema_path = project_root / args.schema
    
    validator = IntentRulesValidator(rules_path, schema_path, args.verbose)
    success = validator.validate()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()