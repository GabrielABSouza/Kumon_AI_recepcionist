#!/bin/bash

# Script to safely remove legacy workflow files
# These files are not in the runtime path and can be removed

echo "Starting cleanup of legacy workflow files..."

# Files to remove (not in runtime path)
FILES_TO_REMOVE=(
    "app/workflows/secure_conversation_workflow.py"
    "app/workflows/graph.py"
    "app/workflows/nodes.py"
    "app/workflows/edges.py"
    "app/workflows/states.py"
    "app/workflows/conversation_workflow_patterns.py"
    "app/workflows/enhanced_workflow_patterns.py"
    "app/workflows/pattern_registry.py"
    "app/workflows/contracts.py"
    "app/workflows/maintainability_engine.py"
    "app/workflows/development_workflow.py"
    "app/workflows/validators.py"
)

# Create backup directory
BACKUP_DIR="legacy_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Creating backup in $BACKUP_DIR..."

# Backup and remove files
for file in "${FILES_TO_REMOVE[@]}"; do
    if [ -f "$file" ]; then
        echo "Backing up and removing: $file"
        cp "$file" "$BACKUP_DIR/" 2>/dev/null
        rm "$file"
    else
        echo "File not found (already removed?): $file"
    fi
done

# Remove states subdirectory if exists
if [ -d "app/workflows/states" ]; then
    echo "Backing up and removing: app/workflows/states/"
    cp -r "app/workflows/states" "$BACKUP_DIR/" 2>/dev/null
    rm -rf "app/workflows/states"
fi

echo ""
echo "Files to KEEP (used by SmartRouter):"
echo "  - app/workflows/intent_classifier.py"
echo "  - app/workflows/intelligent_threshold_system.py"
echo "  - app/workflows/pattern_scorer.py"
echo "  - app/workflows/smart_router.py"
echo "  - app/workflows/context_manager.py"
echo "  - app/workflows/workflow_orchestrator.py"
echo "  - app/workflows/__init__.py"

echo ""
echo "Cleanup complete! Backup created in: $BACKUP_DIR"
echo "If anything breaks, restore from the backup directory."