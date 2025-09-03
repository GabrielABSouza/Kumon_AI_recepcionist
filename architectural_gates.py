#!/usr/bin/env python3
"""
Architectural Protection Gates
Validates V2 architecture compliance to prevent regression
"""

import sys
import os
import re
from pathlib import Path

def check_edge_purity():
    """Verify no edges call SmartRouter or ResponsePlanner"""
    violations = []
    edges_dir = Path("app/core/edges")
    
    if not edges_dir.exists():
        return ["ERROR: edges directory not found"]
    
    patterns = [
        r'SmartRouterAdapter\(\)',
        r'ResponsePlanner\.plan\(',
        r'ResponsePlanner\(\)\.plan\(',
        r'adapter\.decide_route\(',
        r'state\[.*\]\s*='  # State mutations in edges
    ]
    
    for py_file in edges_dir.glob("*.py"):
        with open(py_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        for i, line in enumerate(content.split('\n'), 1):
            for pattern in patterns:
                if re.search(pattern, line):
                    violations.append(f"{py_file}:{i} - {line.strip()}")
    
    return violations

def check_migration_imports():
    """Verify workflow_migration.py has no legacy imports"""
    violations = []
    migration_file = Path("app/core/workflow_migration.py")
    
    if not migration_file.exists():
        return ["ERROR: workflow_migration.py not found"]
    
    with open(migration_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    forbidden_patterns = [
        r'from.*legacy',
        r'import.*legacy', 
        r'from.*v1',
        r'import.*old',
        r'from.*\.workflow\s', # Should not import main workflow
        r'universal_edge_router'
    ]
    
    for i, line in enumerate(content.split('\n'), 1):
        for pattern in forbidden_patterns:
            if re.search(pattern, line):
                violations.append(f"workflow_migration.py:{i} - {line.strip()}")
    
    return violations

def check_v2_flag_activation():
    """Verify V2 flag correctly routes to migration graph"""
    violations = []
    workflow_file = Path("app/core/workflow.py")
    
    if not workflow_file.exists():
        return ["ERROR: workflow.py not found"]
    
    with open(workflow_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if V2 routing exists
    if "workflow_v2_enabled" not in content:
        violations.append("Missing WORKFLOW_V2_ENABLED flag check in _create_workflow()")
    
    if "create_migrated_workflow" not in content:
        violations.append("Missing create_migrated_workflow() import in _create_workflow()")
    
    return violations

def main():
    """Run all architectural protection gates"""
    print("🛡️  Running Architectural Protection Gates...")
    
    all_violations = []
    
    # Gate 1: Edge Purity
    print("\n🔍 Checking Edge Purity...")
    edge_violations = check_edge_purity()
    if edge_violations:
        print(f"❌ Found {len(edge_violations)} edge violations:")
        for violation in edge_violations:
            print(f"   {violation}")
        all_violations.extend(edge_violations)
    else:
        print("✅ All edges are pure")
    
    # Gate 2: Migration Import Cleanliness
    print("\n🔍 Checking Migration Import Cleanliness...")
    import_violations = check_migration_imports()
    if import_violations:
        print(f"❌ Found {len(import_violations)} import violations:")
        for violation in import_violations:
            print(f"   {violation}")
        all_violations.extend(import_violations)
    else:
        print("✅ Migration imports are clean")
    
    # Gate 3: V2 Flag Activation
    print("\n🔍 Checking V2 Flag Activation...")
    flag_violations = check_v2_flag_activation()
    if flag_violations:
        print(f"❌ Found {len(flag_violations)} flag violations:")
        for violation in flag_violations:
            print(f"   {violation}")
        all_violations.extend(flag_violations)
    else:
        print("✅ V2 flag activation is correct")
    
    # Summary
    print(f"\n{'='*50}")
    if all_violations:
        print(f"❌ ARCHITECTURAL GATES FAILED: {len(all_violations)} violations found")
        sys.exit(1)
    else:
        print("✅ ALL ARCHITECTURAL GATES PASSED")
        print("🚀 V2 Architecture is compliant and ready for deployment")
        sys.exit(0)

if __name__ == "__main__":
    main()