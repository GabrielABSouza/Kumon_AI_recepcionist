#!/usr/bin/env python3
"""
Template Lint System - Validates template files against security and style rules

This script ensures that templates:
1. Do NOT contain {{...}} mustache variables (security risk)
2. Are gender-neutral (avoid gendered pronouns)
3. Use proper conditional blocks [[?var: "content"]] and defaults [[var|default]]
4. Have proper encoding and structure

Usage:
    python scripts/lint_templates.py
    python scripts/lint_templates.py --fix   # Auto-fix some issues
    python scripts/lint_templates.py --strict  # Exit with error code on violations
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Set

# Color codes for output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def colored(text: str, color: str) -> str:
    """Add color to text"""
    return f"{color}{text}{Colors.END}"

class TemplateLinter:
    """Lints template files for security and style issues"""
    
    def __init__(self, fix_mode: bool = False):
        self.fix_mode = fix_mode
        self.issues = []
        self.fixed_issues = []
        
        # Patterns for linting
        self.mustache_pattern = re.compile(r'\{\{[^}]+\}\}')
        self.gendered_pronouns = [
            # Portuguese gendered pronouns and articles
            r'\b(ele|ela|dele|dela|nele|nela|seu|sua|seus|suas)\b',
            r'\b(o aluno|a aluna|alunos|alunas)\b',
            r'\b(professor|professora|mestres|mestras)\b',
            r'\b(filho|filha|filhos|filhas)\b',
        ]
        
        # Allowed template variables (single braces)
        self.allowed_variables = {
            # Basic identity variables
            'first_name', 'parent_name', 'child_name', 'student_name', 'username',
            'age', 'student_age', 'grade', 'phone_number', 'email',
            'current_time', 'current_date',
            
            # Scheduling variables
            'confirmed_day', 'confirmed_time', 'available_slots',
            'time_option1', 'time_option2', 'time_option3',
            
            # Context variables
            'context', 'user_message',
            
            # Gender-related variables (deprecated - should be replaced with neutral alternatives)
            'gender_pronoun', 'gender_article', 'gender_possessive', 'gender_self_suffix'
        }
    
    def lint_file(self, file_path: Path) -> List[Dict]:
        """Lint a single template file"""
        try:
            content = file_path.read_text(encoding='utf-8')
            file_issues = []
            
            # Check 1: Mustache variables (SECURITY CRITICAL)
            mustache_matches = self.mustache_pattern.findall(content)
            if mustache_matches:
                issue = {
                    'type': 'SECURITY',
                    'severity': 'CRITICAL',
                    'rule': 'no-mustache-variables',
                    'message': f'Template contains {{...}} mustache variables: {mustache_matches}',
                    'file': file_path,
                    'matches': mustache_matches
                }
                file_issues.append(issue)
                
                # Auto-fix: convert {{var}} to {var}
                if self.fix_mode:
                    fixed_content = re.sub(r'\{\{([^}]+)\}\}', r'{\1}', content)
                    file_path.write_text(fixed_content, encoding='utf-8')
                    self.fixed_issues.append(f"Fixed mustache variables in {file_path}")
                    
            # Check 2: Gendered pronouns
            for pattern in self.gendered_pronouns:
                gender_matches = re.findall(pattern, content, re.IGNORECASE)
                if gender_matches:
                    issue = {
                        'type': 'STYLE',
                        'severity': 'WARNING',
                        'rule': 'gender-neutral',
                        'message': f'Template contains gendered language: {gender_matches}',
                        'file': file_path,
                        'matches': gender_matches
                    }
                    file_issues.append(issue)
            
            # Check 3: Proper variable format validation
            single_brace_vars = re.findall(r'\{([^}]+)\}', content)
            for var in single_brace_vars:
                if var not in self.allowed_variables:
                    issue = {
                        'type': 'STYLE',
                        'severity': 'INFO',
                        'rule': 'unknown-variable',
                        'message': f'Unknown template variable: {var}',
                        'file': file_path,
                        'matches': [var]
                    }
                    file_issues.append(issue)
            
            # Check 4: Template structure validation
            # Validate conditional blocks [[?var: "content"]]
            conditional_pattern = r'\[\[\?([^:]+):\s*"([^"]+)"\]\]'
            conditional_matches = re.findall(conditional_pattern, content)
            for var, _ in conditional_matches:
                var_clean = var.strip()
                if var_clean not in self.allowed_variables:
                    issue = {
                        'type': 'STYLE',
                        'severity': 'INFO', 
                        'rule': 'unknown-conditional-variable',
                        'message': f'Unknown conditional variable: {var_clean}',
                        'file': file_path,
                        'matches': [var_clean]
                    }
                    file_issues.append(issue)
            
            return file_issues
            
        except Exception as e:
            return [{
                'type': 'ERROR',
                'severity': 'CRITICAL',
                'rule': 'file-read-error',
                'message': f'Failed to read template file: {e}',
                'file': file_path,
                'matches': []
            }]
    
    def lint_templates(self, template_dir: Path) -> bool:
        """Lint all template files in directory"""
        template_files = list(template_dir.glob('**/*.txt'))
        
        print(colored(f"🔍 Linting {len(template_files)} template files...", Colors.BLUE))
        print()
        
        total_issues = 0
        critical_issues = 0
        
        for template_file in template_files:
            file_issues = self.lint_file(template_file)
            
            if file_issues:
                # Show file header
                rel_path = template_file.relative_to(template_dir)
                print(colored(f"📄 {rel_path}", Colors.BOLD))
                
                for issue in file_issues:
                    total_issues += 1
                    
                    # Color code by severity
                    if issue['severity'] == 'CRITICAL':
                        color = Colors.RED
                        critical_issues += 1
                    elif issue['severity'] == 'WARNING':
                        color = Colors.YELLOW
                    else:
                        color = Colors.CYAN
                    
                    severity_colored = colored(issue['severity'], color)
                    type_colored = colored(issue['type'], Colors.MAGENTA)
                    
                    print(f"  {severity_colored} [{type_colored}] {issue['rule']}")
                    print(f"    {issue['message']}")
                
                print()  # Empty line after each file
        
        # Summary
        if total_issues == 0:
            print(colored("✅ All templates passed linting!", Colors.GREEN))
            return True
        else:
            status_color = Colors.RED if critical_issues > 0 else Colors.YELLOW
            print(colored(f"📊 Linting Summary:", Colors.BOLD))
            print(f"  Total issues: {total_issues}")
            print(f"  Critical: {critical_issues}")
            print(f"  Templates checked: {len(template_files)}")
            
            if self.fixed_issues:
                print(colored(f"\n🔧 Auto-fixed issues:", Colors.GREEN))
                for fix in self.fixed_issues:
                    print(f"  ✓ {fix}")
            
            print(colored(f"\n{'❌' if critical_issues > 0 else '⚠️'} Linting {'failed' if critical_issues > 0 else 'completed with warnings'}", status_color))
            return critical_issues == 0

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Lint Kumon Assistant template files")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues where possible")
    parser.add_argument("--strict", action="store_true", help="Exit with error code on any violations")
    parser.add_argument("--templates-dir", type=Path, default=Path("app/prompts/templates"), 
                       help="Path to templates directory")
    
    args = parser.parse_args()
    
    # Check if templates directory exists
    if not args.templates_dir.exists():
        print(colored(f"❌ Templates directory not found: {args.templates_dir}", Colors.RED))
        sys.exit(1)
    
    # Run linter
    linter = TemplateLinter(fix_mode=args.fix)
    success = linter.lint_templates(args.templates_dir)
    
    # Exit code handling
    if args.strict and not success:
        sys.exit(1)
    elif not success:
        sys.exit(0)  # Warnings don't cause failure unless --strict

if __name__ == "__main__":
    main()