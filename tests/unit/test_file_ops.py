import pytest

from kourai_common.file_ops import PathViolation, is_safe_path, validate_file_path


def test_validate_file_path_safe(tmp_path):
    project_root = tmp_path
    safe_file = "src/main.py"

    # allow_create=True by default
    resolved = validate_file_path(project_root, safe_file)
    assert resolved == project_root / "src" / "main.py"


def test_validate_file_path_escape(tmp_path):
    project_root = tmp_path
    escape_file = "../main.py"

    with pytest.raises(PathViolation, match="Path escape detected"):
        validate_file_path(project_root, escape_file)


def test_validate_file_path_invalid_extension(tmp_path):
    project_root = tmp_path
    invalid_ext = "main.exe"

    with pytest.raises(PathViolation, match="Extension.*is not in the allowed write list"):
        validate_file_path(project_root, invalid_ext)


def test_is_safe_path(tmp_path):
    project_root = tmp_path
    assert is_safe_path(project_root, "src/main.py") is True
    assert is_safe_path(project_root, "../main.py") is False
    assert is_safe_path(project_root, "main.exe") is False


def test_symlink_escape(tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()

    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()

    symlink_path = project_root / "link"
    try:
        symlink_path.symlink_to(outside_dir)
    except OSError:
        pytest.skip("Symlinks not supported/enabled on this system.")

    # Try to write inside the symlink which points outside
    escape_via_link = "link/main.py"

    with pytest.raises(PathViolation, match="Symlink escape detected"):
        validate_file_path(project_root, escape_via_link)
