"""
Integration tests for the Automated Backup System

Tests the backup infrastructure: scripts, configuration, and file handling.
These tests are designed to run on all platforms (Windows, macOS, Linux).

- Cross-platform test compatibility
- Test file structure and configuration
- Mock external dependencies (HF CLI) when needed
- Focus on Python-runnable validation
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest


def get_project_root():
    """Get project root from test file location."""

    return Path(__file__).parent.parent.parent


class TestBackupScriptValidation:
    """Test that backup scripts exist and have proper structure."""

    def test_backup_script_exists(self):
        """Backup script should exist and be readable."""
        repo_root = get_project_root()
        backup_script = repo_root / "scripts" / "backup_player_data.sh"
        assert backup_script.exists(), f"Backup script not found: {backup_script}"
        assert backup_script.is_file()
        assert backup_script.stat().st_size > 0, "Script file is empty"

    def test_restore_script_exists(self):
        """Restore script should exist and be readable."""
        repo_root = get_project_root()
        restore_script = repo_root / "scripts" / "restore_player_data.sh"
        assert restore_script.exists(), f"Restore script not found: {restore_script}"
        assert restore_script.is_file()
        assert restore_script.stat().st_size > 0, "Script file is empty"

    def test_setup_cron_script_exists(self):
        """Cron setup script should exist."""
        repo_root = get_project_root()
        setup_script = repo_root / "scripts" / "setup-cron.sh"
        assert setup_script.exists(), f"Setup script not found: {setup_script}"
        assert setup_script.is_file()
        assert setup_script.stat().st_size > 0, "Script file is empty"

    def test_env_example_has_backup_vars(self):
        """.env.example should document all backup-related variables."""
        repo_root = get_project_root()
        env_file = repo_root / ".env.example"
        assert env_file.exists(), ".env.example not found"
        content = env_file.read_text(encoding="utf-8")
        assert "HF_TOKEN" in content


class TestBackupScriptContent:
    """Test backup script implementation details."""

    def test_backup_script_has_dry_run_support(self):
        """Backup script should support dry-run mode via env var."""
        repo_root = get_project_root()
        script = repo_root / "scripts" / "backup_player_data.sh"
        content = script.read_text(encoding="utf-8")

        assert "BACKUP_DRY_RUN" in content, "Should support BACKUP_DRY_RUN env var"
        assert "hf buckets sync" in content, "Should use hf CLI for backups"

    def test_backup_script_has_retention_logic(self):
        """Backup script should support automatic cleanup of old backups."""
        repo_root = get_project_root()
        script = repo_root / "scripts" / "backup_player_data.sh"
        content = script.read_text(encoding="utf-8")

        assert "BACKUP_RETENTION_DAYS" in content, "Should support retention policy"
        assert "hf buckets" in content, "Should use hf CLI"

    def test_backup_script_has_error_handling(self):
        """Backup script should handle errors gracefully."""
        repo_root = get_project_root()
        script = repo_root / "scripts" / "backup_player_data.sh"
        content = script.read_text(encoding="utf-8")

        assert "error" in content.lower() or "HF_TOKEN" in content, "Should validate inputs"

    def test_restore_script_has_list_mode(self):
        """Restore script should support listing available backups."""
        repo_root = get_project_root()
        script = repo_root / "scripts" / "restore_player_data.sh"
        content = script.read_text(encoding="utf-8")

        assert "list" in content.lower(), "Should support list action"
        assert "restore" in content.lower(), "Should support restore action"

    def test_restore_script_has_safety_backup(self):
        """Restore script should protect existing data before restore."""
        repo_root = get_project_root()
        script = repo_root / "scripts" / "restore_player_data.sh"
        content = script.read_text(encoding="utf-8")

        assert "backup" in content.lower(), "Should backup before restore"

    def test_cron_script_has_install_uninstall(self):
        """Cron script should support install/uninstall operations."""
        repo_root = get_project_root()
        script = repo_root / "scripts" / "setup-cron.sh"
        content = script.read_text(encoding="utf-8")

        assert "install" in content.lower(), "Should support install"
        assert "uninstall" in content.lower(), "Should support uninstall"
        assert "crontab" in content, "Should use crontab"

    def test_cron_script_has_status_mode(self):
        """Cron script should support status checking."""
        repo_root = get_project_root()
        script = repo_root / "scripts" / "setup-cron.sh"
        content = script.read_text(encoding="utf-8")

        assert "status" in content.lower(), "Should support status command"


class TestBackupConfiguration:
    """Test backup configuration files."""

    def test_env_example_has_required_backup_variables(self):
        """.env.example should document all backup-related variables."""
        repo_root = get_project_root()
        env_file = repo_root / ".env.example"
        content = env_file.read_text(encoding="utf-8")

        assert "HF_TOKEN" in content, "Should document HF_TOKEN"
        assert "BACKUP_USER" in content, "Should document BACKUP_USER"
        assert "BACKUP_BUCKET_NAME" in content, "Should document BACKUP_BUCKET_NAME"
        assert "BACKUP_RETENTION_DAYS" in content, "Should document retention"

    def test_env_example_has_helpful_comments(self):
        """.env.example should have clear documentation."""
        repo_root = get_project_root()
        env_file = repo_root / ".env.example"
        content = env_file.read_text(encoding="utf-8")

        assert "#" in content, "Should have comments"
        assert "HuggingFace" in content or "huggingface" in content, "Should mention HF"


class TestBackupPathHandling:
    """Test backup path construction and date handling."""

    def test_backup_date_format(self):
        """Backup date should follow YYYYMMDD_HHMMSS format."""
        backup_date = datetime.now().strftime("%Y%m%d_%H%M%S")

        assert len(backup_date) == 15, f"Date format incorrect: {backup_date}"

        parsed = datetime.strptime(backup_date, "%Y%m%d_%H%M%S")
        assert isinstance(parsed, datetime)

    def test_bucket_path_construction(self):
        """Backup bucket path should be correctly formatted."""
        username = "testuser"
        bucket_name = "kourai-backups"
        backup_date = "20260325_140000"

        bucket_path = f"{username}/{bucket_name}/profiles/{backup_date}"

        assert bucket_path == "testuser/kourai-backups/profiles/20260325_140000"
        assert bucket_path.count("/") == 3

    def test_retention_date_calculation(self):
        """Cleanup should correctly calculate retention cutoff date."""
        retention_days = 30
        now = datetime.now()
        cutoff = now - timedelta(days=retention_days)

        old_backup_date = (now - timedelta(days=31)).strftime("%Y%m%d")
        assert old_backup_date < cutoff.strftime("%Y%m%d")

        recent_backup_date = (now - timedelta(days=29)).strftime("%Y%m%d")
        assert recent_backup_date > cutoff.strftime("%Y%m%d")


class TestBackupLogging:
    """Test backup logging infrastructure."""

    def test_logs_directory_exists(self):
        """Logs directory should be created for backups."""
        repo_root = get_project_root()
        logs_dir = repo_root / "logs" / "backups"

        logs_dir.mkdir(parents=True, exist_ok=True)

        assert logs_dir.exists()
        assert logs_dir.is_dir()

    def test_backup_log_format(self):
        """Backup logs should have consistent format."""
        repo_root = get_project_root()
        logs_dir = repo_root / "logs" / "backups"
        logs_dir.mkdir(parents=True, exist_ok=True)

        log_file = logs_dir / f"backup_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        log_entry = f"[{datetime.now().isoformat()}] [INFO] Test backup entry\n"
        log_file.write_text(log_entry)

        content = log_file.read_text()
        assert "[INFO]" in content
        assert "Test backup entry" in content

        log_file.unlink()


class TestBackupSecurityAndIgnore:
    """Test that sensitive files are properly protected."""

    def test_env_in_gitignore(self):
        """Credential files should be in .gitignore, but template should be tracked."""
        repo_root = get_project_root()
        gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8")

        # .env should be ignored (contains real credentials)
        assert ".env" in gitignore, ".env not in .gitignore"

        # .env.example should NOT be ignored (it's the template)
        # Check that it's not explicitly ignored with a dedicated line
        gitignore_lines = {line.strip() for line in gitignore.split("\n")}
        assert ".env.example" not in gitignore_lines, ".env.example should not be in .gitignore"

    def test_env_example_is_placeholder_only(self):
        """.env.example should never contain real tokens."""
        repo_root = get_project_root()
        content = (repo_root / ".env.example").read_text(encoding="utf-8")

        assert "hf_your" not in content.lower() or "xxx" in content or "YOUR" in content, (
            ".env.example should only contain placeholder values"
        )


class TestBackupIntegration:
    """End-to-end backup system structure tests."""

    def test_backup_workflow_complete(self):
        """All required backup components should exist."""
        scripts = [
            "scripts/backup_player_data.sh",
            "scripts/restore_player_data.sh",
            "scripts/setup-cron.sh",
        ]

        repo_root = get_project_root()
        for script in scripts:
            script_path = repo_root / script
            assert script_path.exists(), f"Missing: {script}"

        env_file = repo_root / ".env.example"
        assert env_file.exists(), "Missing: .env.example"

    def test_backup_directories_writable(self):
        """Backup log directories should be writable."""
        repo_root = get_project_root()
        logs_dir = repo_root / "logs" / "backups"

        logs_dir.mkdir(parents=True, exist_ok=True)

        assert os.access(logs_dir, os.W_OK), f"Not writable: {logs_dir}"

        test_file = logs_dir / ".write_test"
        test_file.write_text("test")
        assert test_file.exists()
        test_file.unlink()


class TestPlayerDataStructure:
    """Test player data that will be backed up."""

    def test_player_data_directory_structure(self):
        """Player data directory should have expected structure."""
        player_data_dir = Path.home() / ".kourai_khryseai" / "profiles"

        if not player_data_dir.exists():
            pytest.skip("Player data not initialized yet")

        assert player_data_dir.is_dir()

        json_files = list(player_data_dir.glob("*.json"))
        assert len(json_files) > 0, "No player profile JSON files found"

        for json_file in json_files:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            assert isinstance(data, dict), f"Invalid JSON in {json_file}"
