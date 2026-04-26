"""``/project delete`` confirmation guards.

Without these guards, a typo (``/project delete hello-forge`` followed
by an accidental Enter on a slash-completion popup) would silently
remove the registry row, and ``/project delete hello-forge --purge``
would ``rm -rf`` the project tree with no chance to bail out.

Two tiers per ``_confirm_project_delete``:

- bare ``delete`` → ``[y/N]`` (registry-only; files survive at the path)
- ``--purge`` → ``Type DELETE <name> to confirm`` (irreversible)

A ``--yes`` / ``-y`` flag bypasses both for headless / scripted use.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def fake_project(tmp_path):
    """Minimal Project-shaped object with the fields the delete branch reads."""
    return SimpleNamespace(
        project_id="proj-abc-123",
        name="hello-forge",
        path=tmp_path / "hello-forge",
    )


@pytest.fixture
def fake_settings():
    settings = MagicMock()
    settings.active_project_id = None
    settings.save = MagicMock()
    return settings


def _drive_delete(args_str: str, fake_project, fake_settings, *, input_responses=()):
    """Run /project delete <args_str> with the given mocked input() responses.

    Returns ``(delete_called, purge_arg, settings_cleared)``.
    """
    from hosts.cli.commands import _handle_project_command

    delete_calls: list = []

    def fake_delete(project_id, *, purge_files=False):
        delete_calls.append((project_id, purge_files))

    inputs = iter(input_responses)

    def fake_input(_prompt=""):
        try:
            return next(inputs)
        except StopIteration:
            return ""

    with (
        patch(
            "hosts.cli.commands.PlayerProfile.load",
            return_value=SimpleNamespace(player_id="player-1"),
        ),
        patch("hosts.cli.commands.ProjectManager.find", return_value=fake_project),
        patch("hosts.cli.commands.ProjectManager.delete", side_effect=fake_delete),
        patch("builtins.input", fake_input),
    ):
        _handle_project_command(f"/project delete {args_str}", fake_settings)

    delete_called = bool(delete_calls)
    purge_arg = delete_calls[0][1] if delete_called else None
    return delete_called, purge_arg, fake_settings.save.called


# ---------------------------------------------------------------------------
# Bare delete (registry-only)
# ---------------------------------------------------------------------------


class TestBareDeleteAsksYesNo:
    def test_y_proceeds(self, fake_project, fake_settings):
        called, purge, _ = _drive_delete(
            "hello-forge",
            fake_project,
            fake_settings,
            input_responses=["y"],
        )
        assert called is True
        assert purge is False

    def test_yes_proceeds(self, fake_project, fake_settings):
        called, purge, _ = _drive_delete(
            "hello-forge",
            fake_project,
            fake_settings,
            input_responses=["yes"],
        )
        assert called is True
        assert purge is False

    def test_capital_y_proceeds(self, fake_project, fake_settings):
        # `[y/N]` convention — uppercase Y still means yes.
        called, _, _ = _drive_delete(
            "hello-forge",
            fake_project,
            fake_settings,
            input_responses=["Y"],
        )
        assert called is True

    def test_n_cancels(self, fake_project, fake_settings):
        called, _, _ = _drive_delete(
            "hello-forge",
            fake_project,
            fake_settings,
            input_responses=["n"],
        )
        assert called is False

    def test_empty_response_cancels(self, fake_project, fake_settings):
        # Default-no — Enter on the bare prompt should NOT delete.
        called, _, _ = _drive_delete(
            "hello-forge",
            fake_project,
            fake_settings,
            input_responses=[""],
        )
        assert called is False

    def test_garbage_response_cancels(self, fake_project, fake_settings):
        called, _, _ = _drive_delete(
            "hello-forge",
            fake_project,
            fake_settings,
            input_responses=["delete"],
        )
        assert called is False


# ---------------------------------------------------------------------------
# --purge (irreversible) — typed-name confirmation
# ---------------------------------------------------------------------------


class TestPurgeRequiresTypedName:
    def test_typed_name_proceeds(self, fake_project, fake_settings):
        called, purge, _ = _drive_delete(
            "hello-forge --purge",
            fake_project,
            fake_settings,
            input_responses=["DELETE hello-forge"],
        )
        assert called is True
        assert purge is True

    def test_y_alone_does_not_purge(self, fake_project, fake_settings):
        # Single-char "y" is good enough for bare delete, NOT for purge.
        called, _, _ = _drive_delete(
            "hello-forge --purge",
            fake_project,
            fake_settings,
            input_responses=["y"],
        )
        assert called is False

    def test_wrong_name_cancels(self, fake_project, fake_settings):
        # Typed-name guard catches typos.
        called, _, _ = _drive_delete(
            "hello-forge --purge",
            fake_project,
            fake_settings,
            input_responses=["DELETE hellow-forge"],
        )
        assert called is False

    def test_just_delete_keyword_cancels(self, fake_project, fake_settings):
        # Without the project name the typed-name guard rejects.
        called, _, _ = _drive_delete(
            "hello-forge --purge",
            fake_project,
            fake_settings,
            input_responses=["DELETE"],
        )
        assert called is False

    def test_lowercase_delete_cancels(self, fake_project, fake_settings):
        # Typed-name comparison is exact — lowercasing the keyword
        # bails so muscle-memory autocompletion doesn't slip through.
        called, _, _ = _drive_delete(
            "hello-forge --purge",
            fake_project,
            fake_settings,
            input_responses=["delete hello-forge"],
        )
        assert called is False


# ---------------------------------------------------------------------------
# --yes escape hatch (headless / scripted use)
# ---------------------------------------------------------------------------


class TestYesFlagBypassesConfirm:
    def test_yes_skips_bare_prompt(self, fake_project, fake_settings):
        # input() should NEVER be called — confirm by raising on input.
        from hosts.cli.commands import _handle_project_command

        delete_calls: list = []

        def fake_delete(project_id, *, purge_files=False):
            delete_calls.append((project_id, purge_files))

        def explode_on_input(_prompt=""):
            raise AssertionError("--yes should bypass input()")

        with (
            patch(
                "hosts.cli.commands.PlayerProfile.load",
                return_value=SimpleNamespace(player_id="player-1"),
            ),
            patch("hosts.cli.commands.ProjectManager.find", return_value=fake_project),
            patch("hosts.cli.commands.ProjectManager.delete", side_effect=fake_delete),
            patch("builtins.input", explode_on_input),
        ):
            _handle_project_command("/project delete hello-forge --yes", fake_settings)

        assert delete_calls == [("proj-abc-123", False)]

    def test_yes_skips_purge_prompt(self, fake_project, fake_settings):
        from hosts.cli.commands import _handle_project_command

        delete_calls: list = []

        def fake_delete(project_id, *, purge_files=False):
            delete_calls.append((project_id, purge_files))

        def explode_on_input(_prompt=""):
            raise AssertionError("--yes should bypass input()")

        with (
            patch(
                "hosts.cli.commands.PlayerProfile.load",
                return_value=SimpleNamespace(player_id="player-1"),
            ),
            patch("hosts.cli.commands.ProjectManager.find", return_value=fake_project),
            patch("hosts.cli.commands.ProjectManager.delete", side_effect=fake_delete),
            patch("builtins.input", explode_on_input),
        ):
            _handle_project_command("/project delete hello-forge --purge --yes", fake_settings)

        assert delete_calls == [("proj-abc-123", True)]

    def test_short_dash_y_also_bypasses(self, fake_project, fake_settings):
        called, _, _ = _drive_delete(
            "hello-forge -y",
            fake_project,
            fake_settings,
            # No input responses — would block forever if -y didn't bypass.
            input_responses=[],
        )
        assert called is True


# ---------------------------------------------------------------------------
# active_project_id cleared when active project is deleted
# ---------------------------------------------------------------------------


class TestActiveProjectClearedOnDelete:
    def test_active_project_cleared_after_confirmed_delete(self, fake_project, fake_settings):
        fake_settings.active_project_id = fake_project.project_id

        called, _, save_called = _drive_delete(
            "hello-forge",
            fake_project,
            fake_settings,
            input_responses=["y"],
        )

        assert called is True
        assert fake_settings.active_project_id is None
        assert save_called is True

    def test_active_project_untouched_when_confirm_cancels(self, fake_project, fake_settings):
        fake_settings.active_project_id = fake_project.project_id

        called, _, save_called = _drive_delete(
            "hello-forge",
            fake_project,
            fake_settings,
            input_responses=["n"],
        )

        assert called is False
        # Cancelled — settings.active_project_id stays put,
        # settings.save() not called.
        assert fake_settings.active_project_id == fake_project.project_id
        assert save_called is False
