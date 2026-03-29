"""HuggingFace Storage Bucket setup for Kourai Khryseai.

Creates the agent artifact bucket (ajbar/kourai-artifacts) on the HF Hub
using the huggingface_hub Python API. No FUSE daemon or binary required —
agents sync artifacts via push()/pull() in ArtifactStorage.

Usage:
    python scripts/setup_buckets.py
    uv run --no-active python scripts/setup_buckets.py
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_success(msg: str) -> None:
    logger.info(f"✓ {msg}")


def log_warning(msg: str) -> None:
    logger.warning(f"⚠ {msg}")


def log_error(msg: str) -> None:
    logger.error(f"❌ {msg}")


def log_info(msg: str, prefix: str = "ℹ") -> None:
    logger.info(f"{prefix} {msg}")


def run_python(code: str) -> tuple[str, int]:
    """Run Python code via uv and return (stdout, returncode)."""
    try:
        result = subprocess.run(  # noqa: S603
            ["uv", "run", "--no-active", "python", "-c", code],  # noqa: S607
            capture_output=True,
            text=True,
            shell=False,
        )
        return result.stdout.strip(), result.returncode
    except Exception as e:
        return f"Error: {e}", 1


def check_uv() -> bool:
    if not shutil.which("uv"):
        log_error("uv not found. Please install uv (part of Kourai setup)")
        return False
    log_success("Using uv for Python execution")
    return True


def check_huggingface_hub() -> bool:
    """Verify huggingface_hub is importable (declared in shared/pyproject.toml)."""
    _, returncode = run_python("import huggingface_hub; print(huggingface_hub.__version__)")
    if returncode != 0:
        log_error("huggingface_hub not importable — run: uv sync --all-packages")
        return False
    log_success("huggingface_hub available")
    return True


def get_hf_token() -> str | None:
    """Get HF token from environment or .env.hf file."""
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        log_success("HF_TOKEN found in environment")
        return hf_token

    env_hf_path = Path(".env.hf")
    if env_hf_path.exists():
        for line in env_hf_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("HF_TOKEN="):
                token = line.split("=", 1)[1].strip()
                if token:
                    log_success("HF_TOKEN found in .env.hf")
                    return token

    log_warning("No HF_TOKEN found")
    logger.info("")
    logger.info("Get a write-scope token from: https://huggingface.co/settings/tokens")
    logger.info("")

    try:
        token_input = input("Enter your HF token (or press Enter to skip): ").strip()
        if token_input:
            env_hf_path.write_text(
                f"# HuggingFace API Token for Kourai\nHF_TOKEN={token_input}\n",
                encoding="utf-8",
            )
            log_success("Token saved to .env.hf")
            return token_input
    except EOFError:
        log_warning("Token not provided. Set HF_TOKEN manually and re-run.")

    return None


def get_hf_username(hf_token: str) -> str | None:
    """Resolve HuggingFace username from the token via whoami."""
    code = """
from huggingface_hub import HfApi
try:
    info = HfApi().whoami()
    print(info["name"])
except Exception as e:
    print(f"Error: {e}")
    exit(1)
"""
    output, returncode = run_python(code)
    if returncode == 0 and output and not output.startswith("Error"):
        log_success(f"HuggingFace username: {output}")
        return output

    try:
        username = input("Enter your HuggingFace username: ").strip()
        return username or None
    except EOFError:
        return None


def create_artifact_bucket(hf_token: str, hf_username: str) -> bool:
    """Create the kourai-artifacts bucket (private, idempotent)."""
    bucket_id = f"{hf_username}/kourai-artifacts"
    code = f"""
from huggingface_hub import create_bucket
try:
    url = create_bucket("{bucket_id}", private=True, exist_ok=True)
    print(f"ok:{{url.handle}}")
except Exception as e:
    print(f"error:{{e}}")
    exit(1)
"""
    env = os.environ.copy()
    env["HF_TOKEN"] = hf_token
    try:
        result = subprocess.run(  # noqa: S603
            ["uv", "run", "--no-active", "python", "-c", code],  # noqa: S607
            capture_output=True,
            text=True,
            env=env,
            shell=False,
        )
        output = result.stdout.strip()
        if result.returncode == 0 and output.startswith("ok:"):
            handle = output[3:]
            log_success(f"Bucket ready: {handle}")
            return True
        log_error(f"Bucket creation failed: {output or result.stderr.strip()}")
        return False
    except Exception as e:
        log_error(f"Bucket creation failed: {e}")
        return False


def main() -> int:
    logger.info("")
    logger.info("🪣  Kourai Khryseai — HF Storage Bucket Setup")
    logger.info("=" * 48)
    logger.info("")

    log_info("Checking prerequisites...", "Step 1:")
    if not check_uv():
        return 1
    if not check_huggingface_hub():
        return 1

    logger.info("")
    log_info("HuggingFace authentication", "Step 2:")
    hf_token = get_hf_token()
    if not hf_token:
        log_warning("Skipping bucket creation — no HF_TOKEN available")
        logger.info("Set HF_TOKEN and re-run to create the bucket.")
        return 0

    logger.info("")
    log_info("Resolving HuggingFace username...", "Step 3:")
    hf_username = get_hf_username(hf_token)
    if not hf_username:
        log_error("Could not determine HuggingFace username")
        return 1

    logger.info("")
    log_info("Creating artifact bucket...", "Step 4:")
    if not create_artifact_bucket(hf_token, hf_username):
        return 1

    bucket_id = f"{hf_username}/kourai-artifacts"

    logger.info("")
    log_success("Setup complete!")
    logger.info("")
    log_info("Summary:", "")
    logger.info(f"  Bucket:     hf://buckets/{bucket_id}")
    logger.info(f"  Hub page:   https://huggingface.co/buckets/{bucket_id}")
    logger.info("")
    log_info("How agents sync artifacts:", "")
    logger.info("  storage = ArtifactStorage('dokimasia')")
    logger.info("  storage.pull()   # at startup")
    logger.info("  storage.push()   # after task")
    logger.info("")
    log_info("Manual sync via CLI:", "")
    logger.info(f"  hf buckets sync ./artifacts hf://buckets/{bucket_id}/dokimasia")
    logger.info(f"  hf buckets list {bucket_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
