"""
Prompt management package for Kumon Assistant

This package contains:
- LangSmith prompt manager for centralized prompt handling
- Local template fallbacks for offline operation
- Prompt versioning and caching logic
"""

try:
    from .manager import PromptManager, prompt_manager
    __all__ = ["PromptManager", "prompt_manager"]
except ImportError as e:
    print(f"Warning: Could not import prompt manager: {e}")
    __all__ = []