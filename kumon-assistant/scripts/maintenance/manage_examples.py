#!/usr/bin/env python3
"""
CLI script to manage few-shot examples for Kumon AI Receptionist
"""
import sys
import os
import json
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.few_shot_manager import FewShotManager


def main():
    manager = FewShotManager()
    
    if len(sys.argv) < 2:
        print_help()
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        list_examples(manager)
    elif command == "add":
        add_example(manager)
    elif command == "search":
        search_examples(manager)
    elif command == "stats":
        show_statistics(manager)
    elif command == "export":
        export_examples(manager)
    elif command == "import":
        import_examples(manager)
    elif command == "backup":
        backup_examples(manager)
    elif command == "validate":
        validate_examples(manager)
    elif command == "categories":
        list_categories(manager)
    else:
        print(f"Unknown command: {command}")
        print_help()


def print_help():
    print("""
Kumon Few-Shot Examples Manager

Usage: python manage_examples.py <command> [options]

Commands:
  list [category]     - List all examples or examples from specific category
  add                - Add a new example (interactive)
  search <query>     - Search examples by question or keywords
  stats              - Show statistics about examples
  export [filename]  - Export examples to CSV
  import <filename>  - Import examples from CSV
  backup             - Create a backup of current examples
  validate           - Validate examples and show issues
  categories         - List all categories

Examples:
  python manage_examples.py list
  python manage_examples.py list pricing
  python manage_examples.py search "metodologia"
  python manage_examples.py add
  python manage_examples.py export kumon_examples.csv
    """)


def list_examples(manager):
    """List examples, optionally filtered by category"""
    
    category = sys.argv[2] if len(sys.argv) > 2 else None
    
    if category:
        examples = manager.get_examples_by_category(category)
        print(f"\n=== Examples from category: {category} ===\n")
    else:
        data = manager.load_examples()
        examples = data.get("examples", [])
        print(f"\n=== All Examples ({len(examples)} total) ===\n")
    
    if not examples:
        print("No examples found.")
        return
    
    for i, example in enumerate(examples):
        print(f"{i+1}. [{example.get('category', 'general')}] {example.get('question', '')[:80]}...")
        print(f"   Answer: {example.get('answer', '')[:100]}...")
        print(f"   Keywords: {', '.join(example.get('keywords', []))}")
        print()


def add_example(manager):
    """Add a new example interactively"""
    
    print("\n=== Add New Example ===\n")
    
    question = input("Question: ").strip()
    if not question:
        print("Question cannot be empty.")
        return
    
    answer = input("Answer: ").strip() 
    if not answer:
        print("Answer cannot be empty.")
        return
    
    print("\nAvailable categories:")
    data = manager.load_examples()
    categories = data.get("categories", {})
    for cat, info in categories.items():
        print(f"  - {cat}: {info.get('description', '')}")
    
    category = input("Category (default: general): ").strip() or "general"
    
    keywords_str = input("Keywords (comma-separated): ").strip()
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()] if keywords_str else []
    
    success = manager.add_example(question, answer, category, keywords)
    
    if success:
        print("✅ Example added successfully!")
    else:
        print("❌ Failed to add example.")


def search_examples(manager):
    """Search examples"""
    
    if len(sys.argv) < 3:
        print("Please provide a search query.")
        return
    
    query = " ".join(sys.argv[2:])
    examples = manager.search_examples(query)
    
    print(f"\n=== Search Results for: '{query}' ({len(examples)} found) ===\n")
    
    if not examples:
        print("No examples found.")
        return
    
    for i, example in enumerate(examples):
        print(f"{i+1}. [{example.get('category', 'general')}] {example.get('question', '')}")
        print(f"   Answer: {example.get('answer', '')[:150]}...")
        print(f"   Keywords: {', '.join(example.get('keywords', []))}")
        print()


def show_statistics(manager):
    """Show statistics about examples"""
    
    stats = manager.get_statistics()
    
    print("\n=== Few-Shot Examples Statistics ===\n")
    print(f"Total Examples: {stats['total']}")
    print(f"Average Question Length: {stats.get('average_question_length', 0):.1f} characters")
    print(f"Average Answer Length: {stats.get('average_answer_length', 0):.1f} characters")
    print(f"Total Keywords: {stats.get('keywords_count', 0)}")
    print(f"Average Keywords per Example: {stats.get('average_keywords_per_example', 0):.1f}")
    
    print("\nExamples by Category:")
    for category, count in stats.get('categories', {}).items():
        percentage = (count / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"  {category}: {count} ({percentage:.1f}%)")


def export_examples(manager):
    """Export examples to CSV"""
    
    filename = sys.argv[2] if len(sys.argv) > 2 else None
    filepath = manager.export_to_csv(filename)
    
    if filepath:
        print(f"✅ Examples exported to: {filepath}")
    else:
        print("❌ Failed to export examples.")


def import_examples(manager):
    """Import examples from CSV"""
    
    if len(sys.argv) < 3:
        print("Please provide CSV filename.")
        return
    
    filepath = sys.argv[2]
    
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
    
    success = manager.import_from_csv(filepath)
    
    if success:
        print("✅ Examples imported successfully!")
    else:
        print("❌ Failed to import examples.")


def backup_examples(manager):
    """Create backup of examples"""
    
    backup_path = manager.backup_examples()
    
    if backup_path:
        print(f"✅ Backup created: {backup_path}")
    else:
        print("❌ Failed to create backup.")


def validate_examples(manager):
    """Validate examples and show issues"""
    
    issues = manager.validate_examples()
    
    print(f"\n=== Validation Results ===\n")
    
    if not issues:
        print("✅ All examples are valid!")
        return
    
    print(f"Found {len(issues)} examples with issues:\n")
    
    for issue in issues:
        print(f"Example #{issue['index'] + 1}:")
        for problem in issue['problems']:
            print(f"  ⚠️  {problem}")
        print()


def list_categories(manager):
    """List all available categories"""
    
    data = manager.load_examples()
    categories = data.get("categories", {})
    
    print("\n=== Available Categories ===\n")
    
    if not categories:
        print("No categories defined.")
        return
    
    for category, info in categories.items():
        examples_count = len(manager.get_examples_by_category(category))
        print(f"{category}")
        print(f"  Description: {info.get('description', 'No description')}")
        print(f"  Examples: {examples_count}")
        print()


if __name__ == "__main__":
    main() 