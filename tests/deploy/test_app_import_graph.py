"""
Test that all app modules can be imported.
Catches broken imports like "from app.cache import ..." when module doesn't exist.
"""
import importlib
import pkgutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
APP_DIR = ROOT / "app"


@pytest.mark.skipif(not APP_DIR.exists(), reason="app/ folder not found")
def test_import_whole_app_package():
    """Walk through app package and import all modules."""
    # Ensure root is in PYTHONPATH
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    # Import base package
    try:
        app_pkg = importlib.import_module("app")
    except Exception as e:
        pytest.fail(f"Failed to import base 'app' package: {e}")

    # Walk through all submodules
    failures = []
    skipped = []
    successful = []

    for _finder, name, _ispkg in pkgutil.walk_packages(
        app_pkg.__path__, app_pkg.__name__ + "."
    ):
        # Skip test modules and known problematic imports
        if any(skip in name for skip in ["test_", "_test", ".tests.", "__pycache__"]):
            skipped.append(name)
            continue

        try:
            importlib.import_module(name)
            successful.append(name)
        except Exception as e:
            # Capture the error but continue testing other modules
            failures.append((name, repr(e)))

    # Report results
    print(f"\n✅ Successfully imported {len(successful)} modules")
    if skipped:
        print(f"⏭️  Skipped {len(skipped)} test/cache modules")

    if failures:
        msg = "\n".join(f"  ❌ {n}: {err}" for n, err in failures)
        pytest.fail(f"\nFailed to import {len(failures)} modules:\n{msg}")


def test_critical_app_modules():
    """Test critical app modules that must exist."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    critical_modules = [
        "app.api",
        "app.core",
        "app.services",
    ]

    for module_name in critical_modules:
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as e:
            pytest.fail(f"Critical module missing: {module_name} → {e}")


def test_no_circular_imports():
    """Basic test for circular import detection."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    # Try importing main entry point twice
    import app.main

    importlib.reload(app.main)  # Should not cause circular import error
