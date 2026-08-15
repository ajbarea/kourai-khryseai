"""Tests for the ty environment preflight in scripts/lint.py.

Bug guard: `make lint` reported 336 ty diagnostics on a clean tree while CI
was green. No code defect -- uv defaults to `.venv` (the Docker-side venv) on
a WSL host, which lacks the hosts/cli and hosts/gui dependencies, so ty
type-checked those sources against an environment that could not resolve
their imports. The preflight turns that into one actionable line.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from scripts import lint

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestCheckTyEnvironment:
    def test_passes_when_every_marker_resolves(self):
        """The suite runs in the all-packages venv, so the preflight is a no-op."""
        assert lint.check_ty_environment() == 0

    def test_markers_are_the_modules_ty_actually_needs(self):
        """Guard the guard: a marker that no longer exists would never fire."""
        for name in lint.TY_ENV_MARKERS:
            assert importlib.util.find_spec(name) is not None, (
                f"{name} is not a real dependency any more -- update TY_ENV_MARKERS"
            )

    def test_fails_and_names_the_missing_module(self, monkeypatch, capsys):
        monkeypatch.setattr(lint, "TY_ENV_MARKERS", ("definitely_not_installed_xyz",))

        assert lint.check_ty_environment() == 1

        out = capsys.readouterr().out
        assert "definitely_not_installed_xyz" in out
        assert sys.prefix in out, "must name the venv, or the message is unactionable"
        assert "uv sync --all-packages" in out

    def test_reports_every_missing_module_not_just_the_first(self, monkeypatch, capsys):
        monkeypatch.setattr(lint, "TY_ENV_MARKERS", ("nope_one_xyz", "nope_two_xyz"))

        assert lint.check_ty_environment() == 1

        out = capsys.readouterr().out
        assert "nope_one_xyz" in out
        assert "nope_two_xyz" in out


class TestTyPaths:
    def test_ty_paths_exist_on_disk(self):
        """A renamed directory would silently shrink the type-checked surface."""
        for rel in lint.TY_PATHS:
            assert (REPO_ROOT / rel).is_dir(), f"TY_PATHS entry {rel!r} is not a directory"

    @pytest.mark.parametrize(
        "ci_path",
        ["agents", "hosts/cli", "hosts/gui", "mcp_servers", "shared/src", "tests"],
    )
    def test_covers_everything_ci_checks(self, ci_path):
        """Local lint must not check less than .github/workflows/tests.yml does."""
        assert ci_path in lint.TY_PATHS
