"""
Build integrity tests for deployment validation.

These tests validate that critical data files and resources are present
in the deployed environment, preventing runtime FileNotFoundError issues.
"""
import json
import os
import pathlib
from pathlib import Path


class TestBuildIntegrity:
    """Test suite for validating deployment build integrity."""

    def test_few_shot_examples_file_exists(self):
        """
        CRITICAL TEST: Validate few-shot examples JSON file is present in build.

        This test prevents the production FileNotFoundError by ensuring
        app/data/few_shot_examples.json is included in the deployment package.

        SCENARIO: Check file existence using same logic as production code
        EXPECTED: File exists and is readable
        ASSERTION: File path exists and contains valid JSON

        🔥 RED PHASE: This will FAIL if build configuration doesn't include app/data/
        """
        # Method 1: Test the exact same path resolution as prompt_utils.py
        prompt_utils_path = str(
            pathlib.Path(__file__).parent.parent.parent
            / "app"
            / "utils"
            / "prompt_utils.py"
        )

        # Verify prompt_utils.py exists (sanity check)
        assert os.path.exists(
            prompt_utils_path
        ), f"prompt_utils.py not found at {prompt_utils_path}"

        # Method 2: Construct path using same logic as prompt_utils.py
        # This simulates: pathlib.Path(__file__).parent.parent / "data" / "few_shot_examples.json"
        # where __file__ is app/utils/prompt_utils.py
        base_dir = pathlib.Path(__file__).parent.parent.parent  # Go to project root
        app_utils_dir = base_dir / "app" / "utils"  # Simulate being in app/utils/
        file_path = (
            app_utils_dir.parent / "data" / "few_shot_examples.json"
        )  # Same as prompt_utils logic

        assert file_path.exists(), (
            f"CRITICAL BUILD ERROR: few_shot_examples.json not found at {file_path}. "
            f"This will cause FileNotFoundError in production. "
            f"Verify Dockerfile copies app/data/ directory correctly."
        )

        # Method 3: Alternative direct path (for CI/Docker environments)
        direct_path = Path("app/data/few_shot_examples.json")
        if not file_path.exists() and direct_path.exists():
            file_path = direct_path

        # Validate file is readable and contains valid JSON
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Basic structure validation
            assert isinstance(data, list), "few_shot_examples.json must contain a list"
            assert len(data) > 0, "few_shot_examples.json must not be empty"

            # Validate each example has required structure
            for i, example in enumerate(data):
                assert isinstance(example, dict), f"Example {i} must be a dictionary"
                assert "user_question" in example, f"Example {i} missing user_question"
                assert (
                    "ideal_response" in example
                ), f"Example {i} missing ideal_response"

        except json.JSONDecodeError as e:
            raise AssertionError(
                f"few_shot_examples.json contains invalid JSON: {str(e)}"
            )
        except UnicodeDecodeError as e:
            raise AssertionError(f"few_shot_examples.json encoding error: {str(e)}")

        print(
            f"✅ BUILD INTEGRITY SUCCESS: few_shot_examples.json found and validated at {file_path}"
        )

    def test_required_directories_exist(self):
        """
        Test that all required application directories exist in the build.

        This prevents runtime errors when the application tries to create
        or access files in expected directories.
        """
        base_dir = pathlib.Path(__file__).parent.parent.parent

        required_dirs = ["app", "app/data", "app/utils", "app/core", "app/api"]

        for dir_path in required_dirs:
            full_path = base_dir / dir_path
            assert full_path.exists(), f"Required directory missing: {dir_path}"
            assert full_path.is_dir(), f"Path exists but is not a directory: {dir_path}"

        print("✅ DIRECTORY STRUCTURE SUCCESS: All required directories present")

    def test_app_data_directory_contents(self):
        """
        Test that app/data directory contains expected files.

        This ensures all data files needed by the application are included
        in the deployment package.
        """
        base_dir = pathlib.Path(__file__).parent.parent.parent
        data_dir = base_dir / "app" / "data"

        assert data_dir.exists(), "app/data directory does not exist"

        # Check for critical files
        critical_files = ["few_shot_examples.json"]

        for filename in critical_files:
            file_path = data_dir / filename
            assert file_path.exists(), f"Critical data file missing: {filename}"
            assert file_path.is_file(), f"Path exists but is not a file: {filename}"

            # Check file is not empty
            assert (
                file_path.stat().st_size > 0
            ), f"Critical data file is empty: {filename}"

        print("✅ DATA FILES SUCCESS: All critical data files present and non-empty")

    def test_import_paths_work(self):
        """
        Test that critical imports work in the deployment environment.

        This catches missing dependencies or import path issues early.
        """
        # Test importing key modules
        try:
            from app.utils.prompt_utils import load_few_shot_examples

        except ImportError as e:
            raise AssertionError(f"Critical import failed: {str(e)}")

        # Test the actual function that caused the production error
        try:
            examples = load_few_shot_examples()
            assert isinstance(
                examples, list
            ), "load_few_shot_examples should return a list"
            assert len(examples) > 0, "Few-shot examples should not be empty"

        except FileNotFoundError as e:
            raise AssertionError(f"PRODUCTION ERROR REPRODUCED: {str(e)}")
        except Exception as e:
            raise AssertionError(
                f"Unexpected error in load_few_shot_examples: {str(e)}"
            )

        print("✅ IMPORT SUCCESS: All critical imports and functions work correctly")
