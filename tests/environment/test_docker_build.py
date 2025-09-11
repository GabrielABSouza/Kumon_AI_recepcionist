"""
Docker build validation tests.

These tests can be run in CI/CD pipelines to validate that Docker builds
include all necessary files and dependencies.
"""
import subprocess
from pathlib import Path

import pytest


class TestDockerBuild:
    """Test suite for validating Docker build configuration."""

    @pytest.mark.skip(reason="Requires Docker environment - enable in CI/CD")
    def test_production_dockerfile_builds(self):
        """
        Test that the production Dockerfile builds successfully.

        This test is disabled by default but can be enabled in CI/CD environments
        to validate that the build process works correctly.
        """
        project_root = Path(__file__).parent.parent.parent
        dockerfile_path = project_root / "Dockerfile.production"

        assert dockerfile_path.exists(), "Dockerfile.production not found"

        # Build the Docker image
        build_command = [
            "docker",
            "build",
            "-f",
            str(dockerfile_path),
            "-t",
            "kumon-assistant:test",
            str(project_root),
        ]

        try:
            result = subprocess.run(
                build_command,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=project_root,
            )

            assert result.returncode == 0, (
                f"Docker build failed with code {result.returncode}. "
                f"Stdout: {result.stdout}. Stderr: {result.stderr}"
            )

        except subprocess.TimeoutExpired:
            pytest.fail("Docker build timed out after 5 minutes")
        except FileNotFoundError:
            pytest.skip("Docker not available in this environment")

    @pytest.mark.skip(reason="Requires Docker environment - enable in CI/CD")
    def test_docker_image_contains_data_files(self):
        """
        Test that the built Docker image contains required data files.

        This test validates that app/data/few_shot_examples.json exists
        inside the Docker container.
        """
        # Check if image exists from previous test or build
        check_image_cmd = ["docker", "images", "-q", "kumon-assistant:test"]

        try:
            result = subprocess.run(check_image_cmd, capture_output=True, text=True)
            if not result.stdout.strip():
                pytest.skip(
                    "Docker image kumon-assistant:test not found. Run build test first."
                )

        except FileNotFoundError:
            pytest.skip("Docker not available in this environment")

        # Test file existence inside container
        test_command = [
            "docker",
            "run",
            "--rm",
            "kumon-assistant:test",
            "python",
            "-c",
            "import pathlib; import sys; "
            "path = pathlib.Path('/app/app/data/few_shot_examples.json'); "
            "sys.exit(0 if path.exists() else 1)",
        ]

        try:
            result = subprocess.run(
                test_command, capture_output=True, text=True, timeout=60
            )

            assert result.returncode == 0, (
                f"few_shot_examples.json not found in Docker container. "
                f"This indicates a build configuration issue. "
                f"Stderr: {result.stderr}"
            )

        except subprocess.TimeoutExpired:
            pytest.fail("Docker container test timed out")
        except FileNotFoundError:
            pytest.skip("Docker not available in this environment")

    def test_dockerfile_includes_data_copy_instruction(self):
        """
        Test that Dockerfiles contain explicit COPY instructions for app/data/.

        This is a static analysis test that ensures the build configuration
        includes the necessary copy instructions.
        """
        project_root = Path(__file__).parent.parent.parent
        dockerfiles = [
            project_root / "Dockerfile",
            project_root / "Dockerfile.production",
        ]

        for dockerfile_path in dockerfiles:
            if not dockerfile_path.exists():
                continue

            content = dockerfile_path.read_text()

            # Check for app/data copy instruction
            data_copy_patterns = [
                "COPY app/data",
                "COPY ./app/data",
                "COPY app/ ./app/",  # This also includes data, but explicit is better
            ]

            has_data_copy = any(pattern in content for pattern in data_copy_patterns)

            assert has_data_copy, (
                f"{dockerfile_path.name} does not contain explicit data copy instruction. "
                f"Add 'COPY app/data/ ./app/data/' to ensure data files are included."
            )

        print("✅ DOCKERFILE VALIDATION: All Dockerfiles include data copy instructions")
