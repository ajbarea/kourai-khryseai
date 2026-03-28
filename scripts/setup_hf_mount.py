"""Phase 1: HuggingFace Storage Buckets Setup.

Sets up HuggingFace Storage Buckets for agent artifact storage.

Prerequisites:
    - HuggingFace account at https://huggingface.co
    - HF API token with write permissions
    - huggingface_hub Python package installed

Usage:
    python scripts/setup_hf_mount.py
    uv run --no-active python scripts/setup_hf_mount.py
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
    """Log success message with checkmark."""
    logger.info(f"✓ {msg}")


def log_warning(msg: str) -> None:
    """Log warning message with caution sign."""
    logger.warning(f"⚠ {msg}")


def log_error(msg: str) -> None:
    """Log error message with X."""
    logger.error(f"❌ {msg}")


def log_info(msg: str, prefix: str = "ℹ") -> None:
    """Log info message."""
    logger.info(f"{prefix} {msg}")


def run_python(code: str) -> tuple[str, int]:
    """Run Python code and return output and return code."""
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
    """Check if uv is available."""
    if not shutil.which("uv"):
        log_error("uv not found. Please install uv (part of Kourai setup)")
        return False
    log_success("Using uv for Python execution")
    return True


def check_huggingface_hub() -> bool:
    """Check and install huggingface_hub if needed."""
    output, returncode = run_python("import huggingface_hub")
    if returncode != 0:
        log_warning("huggingface_hub not installed. Installing...")
        try:
            subprocess.run(
                ["uv", "pip", "install", "huggingface-hub"],  # noqa: S607
                check=True,
                capture_output=True,
                shell=False,
            )
        except subprocess.CalledProcessError:
            log_error("Failed to install huggingface_hub")
            return False
    log_success("huggingface_hub installed")
    return True


def get_hf_token() -> str | None:
    """Get HF token from environment or .env.hf file."""
    hf_token = os.environ.get("HF_TOKEN")
    if hf_token:
        log_success("HF_TOKEN already set in environment")
        return hf_token

    env_hf_path = Path(".env.hf")
    if env_hf_path.exists():
        with env_hf_path.open(encoding="utf-8") as f:
            content = f.read()
            if "hf_" in content:
                log_success("HF_TOKEN found in .env.hf")
                for line in content.split("\n"):
                    if line.startswith("HF_TOKEN="):
                        return line.split("=", 1)[1].strip()

    log_warning("No HF_TOKEN found")
    logger.info("")
    logger.info("Please get your token from: https://huggingface.co/settings/tokens")
    logger.info("Create a NEW token with 'write' scope.")
    logger.info("")

    try:
        token_input = input("Enter your HF token (or press Enter to skip): ").strip()
        if token_input:
            with env_hf_path.open("w", encoding="utf-8") as f:
                f.write("# HuggingFace API Token for HF-Mount\n")
                f.write(f"HF_TOKEN={token_input}\n")
            log_success("Token saved to .env.hf")
            return token_input
    except EOFError:
        log_warning("Token not provided. You'll need to set HF_TOKEN manually.")

    return None


def get_hf_username(hf_token: str) -> str | None:
    """Get HuggingFace username using whoami API."""
    code = """
from huggingface_hub import HfApi
try:
    api = HfApi()
    user_info = api.whoami()
    print(user_info["name"])
except Exception as e:
    print(f"Error: {e}")
    exit(1)
"""
    output, returncode = run_python(code)
    if returncode == 0 and output:
        log_success(f"HuggingFace username: {output}")
        return output

    try:
        username = input("Enter your HuggingFace username: ").strip()
        if username:
            return username
    except EOFError:
        pass

    return None


def create_bucket(hf_token: str, bucket_name: str) -> bool:
    """Create a single bucket."""
    code = f"""
import os
from huggingface_hub import HfApi
try:
    api = HfApi()
    api.create_bucket("{bucket_name}", private=True, exist_ok=True)
    print("created")
except Exception as e:
    error_msg = str(e)
    if "exists" in error_msg.lower():
        print("exists")
    elif "forbidden" in error_msg.lower() or "not the required permissions" in error_msg.lower():
        print("permission_denied")
    else:
        print(f"error: {{error_msg}}")
        raise
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
        if result.returncode == 0:
            if output == "created":
                log_success(f"Created bucket: {bucket_name}")
            elif output == "exists":
                log_success(f"Bucket already exists: {bucket_name}")
            elif output == "permission_denied":
                log_warning(
                    f"Insufficient permissions to create bucket: {bucket_name}. "
                    "Token needs 'write' scope. Create a new token at: "
                    "https://huggingface.co/settings/tokens"
                )
            return True

        log_error(f"Error creating bucket {bucket_name}")
        return False
    except Exception as e:
        log_error(f"Failed to create bucket {bucket_name}: {e}")
        return False


def create_buckets(hf_token: str, hf_username: str) -> bool:
    """Create the main bucket (sub-folders are virtual)."""
    bucket_name = f"{hf_username}/kourai-artifacts"
    if not create_bucket(hf_token, bucket_name):
        return False

    log_info(
        "Sub-folders for agents (dokimasia, techne, etc.) are virtual and created on-demand.", "ℹ"
    )
    return True


def check_hf_mount() -> bool:
    """Check if hf-mount is installed."""
    if shutil.which("hf-mount"):
        try:
            result = subprocess.run(
                ["hf-mount", "status"],  # noqa: S607
                capture_output=True,
                text=True,
                timeout=5,
                shell=False,
            )
            if result.returncode == 0:
                log_success("hf-mount is installed and responsive")
            else:
                log_success("hf-mount is installed")
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    log_warning("hf-mount not found in PATH")
    logger.info("Note: hf-mount installation requires platform-specific setup.")
    logger.info("See: https://github.com/huggingface/hf-mount")
    return False


def main() -> int:
    """Main HF-Mount setup workflow."""
    logger.info("")
    logger.info("🚀 Kourai Khryseai - Phase 1: HF-Mount Setup")
    logger.info("=" * 50)
    logger.info("")

    log_info("Checking prerequisites...", "Step 1:")
    if not check_uv():
        return 1
    if not check_huggingface_hub():
        return 1

    logger.info("")
    log_info("HuggingFace Authentication", "Step 2:")
    hf_token = get_hf_token()

    logger.info("")
    log_info("Detecting HuggingFace username...", "Step 3:")
    if hf_token:
        hf_username = get_hf_username(hf_token)
    else:
        try:
            hf_username = input("Enter your HuggingFace username: ").strip()
        except EOFError:
            hf_username = None

    if not hf_username:
        log_error("Could not determine HuggingFace username")
        return 1

    logger.info("")
    log_info("Creating HuggingFace Storage Buckets...", "Step 4:")
    if hf_token:
        if not create_buckets(hf_token, hf_username):
            log_error("Failed to create buckets")
            return 1
    else:
        log_warning("Skipping bucket creation (no HF_TOKEN)")
        logger.info("   Run this when you have your token:")
        logger.info("   export HF_TOKEN=hf_...")
        logger.info("   python scripts/setup_hf_mount.py")

    logger.info("")
    log_info("HF-Mount Installation", "Step 5:")
    check_hf_mount()

    logger.info("")
    log_success("Phase 1 Setup Complete!")
    logger.info("")
    log_info("Configuration Summary:", "")
    logger.info(f"  HuggingFace Username: {hf_username}")
    logger.info(f"  Main Bucket: {hf_username}/kourai-artifacts")
    logger.info("  Sub-buckets: dokimasia, techne, kallos, metis, mneme")
    if Path(".env.hf").exists():
        logger.info("  HF Token File: .env.hf")

    logger.info("")
    log_info("Next Steps:", "")
    logger.info("1. Start hf-mount daemon:")
    logger.info(
        f"   hf-mount start bucket {hf_username}/kourai-artifacts/dokimasia /tmp/hf-dokimasia"
    )
    logger.info("")
    logger.info("2. Verify mount:")
    logger.info("   ls -la /tmp/hf-dokimasia/")
    logger.info("")
    logger.info("3. Start Kourai with Docker Compose:")
    logger.info("   docker compose up dokimasia")
    logger.info("")
    logger.info("4. Check HF Hub for artifacts:")
    logger.info(f"   https://huggingface.co/buckets/{hf_username}/kourai-artifacts")
    logger.info("")
    log_info("Documentation:", "")
    logger.info("  - Full guide: scripts/../files/PHASE1_IMPLEMENTATION.md")
    logger.info("  - HF-Mount docs: https://github.com/huggingface/hf-mount")
    logger.info("  - HF Buckets docs: https://huggingface.co/docs/hub/storage-buckets")

    return 0


if __name__ == "__main__":
    sys.exit(main())
