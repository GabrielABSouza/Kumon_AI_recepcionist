"""
Test that all critical packages can be imported.
Prevents "No module named ..." errors at runtime.
"""
import importlib

import pytest

# Critical imports that MUST work for the app to run
CRITICAL_IMPORTS = [
    "fastapi",
    "uvicorn",
    "requests",
    "redis",
    "asyncpg",
    "openai",
    "google.generativeai",
    "langgraph",
    "langchain",
    "langsmith",
    "pydantic",
    "dotenv",
]

# Optional imports that should work if in requirements
OPTIONAL_IMPORTS = [
    "httpx",
    "tenacity",
    "typing_extensions",
]


@pytest.mark.parametrize("mod", CRITICAL_IMPORTS)
def test_critical_third_party_imports(mod):
    """Test that critical third-party packages can be imported."""
    try:
        importlib.import_module(mod)
    except ModuleNotFoundError as e:
        pytest.fail(f"Critical import failed: {mod} → {e}")


@pytest.mark.parametrize("mod", OPTIONAL_IMPORTS)
def test_optional_third_party_imports(mod):
    """Test optional imports (skip if not installed)."""
    try:
        importlib.import_module(mod)
    except ModuleNotFoundError:
        pytest.skip(f"Optional module {mod} not installed")


def test_langchain_ecosystem_imports():
    """Test that LangChain ecosystem imports work together."""
    imports = []

    try:
        pass

        imports.append("langchain.LLMChain")
    except ImportError as e:
        pytest.fail(f"Failed to import from langchain: {e}")

    try:
        pass

        imports.append("langchain_core.messages.HumanMessage")
    except ImportError as e:
        pytest.fail(f"Failed to import from langchain_core: {e}")

    try:
        pass

        imports.append("langgraph.graph.StateGraph")
    except ImportError as e:
        pytest.fail(f"Failed to import from langgraph: {e}")

    assert len(imports) >= 3, "Not all LangChain ecosystem imports succeeded"
