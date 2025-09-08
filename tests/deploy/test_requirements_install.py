"""
Test requirements.txt installation in clean environment.
Validates compatibility with python:3.11-slim Docker image.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQ = ROOT / "requirements.txt"


def _run(cmd: list[str], env=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)


def test_requirements_file_exists():
    """Ensure requirements.txt exists in project root."""
    assert REQ.exists(), "requirements.txt não encontrado na raiz do projeto"


def test_no_binary_dependencies_requiring_gcc():
    """Check we don't use packages that need compilation (incompatible with slim)."""
    txt = REQ.read_text(encoding="utf-8")

    # These packages require gcc/build tools and should use -binary versions
    problematic = ["psycopg2", "pillow", "numpy", "pandas", "scipy"]
    for pkg in problematic:
        # Check for package without -binary suffix
        pattern = rf"(^|\n)\s*{pkg}([=<>!]+|$)"
        if re.search(pattern, txt):
            # Allow if it has -binary suffix
            if f"{pkg}-binary" not in txt:
                raise AssertionError(
                    f"Use {pkg}-binary instead of {pkg} for python:3.11-slim"
                )


def test_requirements_install_on_clean_venv():
    """Test requirements install in clean virtual environment."""
    with tempfile.TemporaryDirectory() as td:
        venv_dir = Path(td) / ".venv"

        # Create venv
        rc = _run([sys.executable, "-m", "venv", str(venv_dir)])
        assert rc.returncode == 0, f"Failed to create venv: {rc.stderr}"

        # Get venv pip and python
        if sys.platform == "win32":
            pip = venv_dir / "Scripts" / "pip"
            # python = venv_dir / "Scripts" / "python"  # noqa: F841
        else:
            pip = venv_dir / "bin" / "pip"
            # python = venv_dir / "bin" / "python"  # noqa: F841

        # Upgrade pip for better dependency resolution
        rc = _run([str(pip), "install", "--upgrade", "pip", "setuptools", "wheel"])
        assert rc.returncode == 0, f"Failed to upgrade pip: {rc.stderr}"

        # Try to install requirements (simulates Dockerfile step)
        rc = _run([str(pip), "install", "--no-cache-dir", "-r", str(REQ)])
        if rc.returncode != 0:
            print("==== STDOUT ====")
            print(rc.stdout)
            print("==== STDERR ====")
            print(rc.stderr)
        assert rc.returncode == 0, "Falha ao instalar requirements.txt"

        # Check for conflicts
        rc = _run([str(pip), "check"])
        deps_msg = f"Conflitos de dependência: {rc.stdout}\n{rc.stderr}"
        assert rc.returncode == 0, deps_msg


def test_langchain_version_compatibility():
    """Ensure LangChain ecosystem versions are compatible."""
    txt = REQ.read_text(encoding="utf-8")

    # Extract versions
    langchain_match = re.search(r"langchain==([0-9.]+)", txt)
    langchain_core_match = re.search(r"langchain-core==([0-9.]+)", txt)
    # langsmith_match = re.search(r"langsmith==([0-9.]+)", txt)  # noqa: F841

    if langchain_match and langchain_core_match:
        langchain_ver = langchain_match.group(1)
        langchain_core_ver = langchain_core_match.group(1)

        # Known compatible versions
        if langchain_ver == "0.1.0":
            msg = (
                f"langchain {langchain_ver} incompatible with "
                f"langchain-core {langchain_core_ver}"
            )
            assert langchain_core_ver in [
                "0.1.19",
                "0.1.20",
                "0.1.21",
                "0.1.22",
                "0.1.23",
                "0.1.24",
            ], msg
