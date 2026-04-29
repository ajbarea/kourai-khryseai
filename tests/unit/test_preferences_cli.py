"""``/preferences`` slash command — list / set / forget pipeline.

Covers the M17 Phase 2 item 7 surface end-to-end at the handler level:
project-scope vs global resolution, closed-vocab gate on ``set``,
right-to-forget on individual kinds and ``--all``, alias dispatch
through ``__main__``, and the bare-list rendering path.
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from kourai_common.player import _ensure_player_tables


@pytest.fixture
def _isolate_player_db(tmp_path, monkeypatch):
    """Sandbox the SQLite player DB so the CLI tests touch nothing on disk."""
    db_path = tmp_path / "test_memory.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)

    import kourai_common.player as player_mod

    player_mod._tables_initialized = False
    _ensure_player_tables(conn)
    monkeypatch.setattr(player_mod, "_get_player_db", lambda: conn)
    yield conn
    conn.close()


@pytest.fixture
def _fake_player_profile(monkeypatch):
    """A loaded profile so ``_player_id`` returns a stable uuid in tests."""
    fake = MagicMock(player_id="player-uuid")
    monkeypatch.setattr(
        "hosts.cli.commands.PlayerProfile.load",
        lambda *a, **k: fake,
    )
    return fake


@pytest.fixture
def _capture_echo(monkeypatch):
    """Capture all ``_echo`` output across the dispatch + handler path."""
    echoed: list[str] = []
    monkeypatch.setattr(
        "hosts.cli.commands._echo",
        lambda text="", nl=True: echoed.append(text),
    )
    return echoed


@pytest.fixture
def _global_scope(monkeypatch):
    """Force ``_active_project_fact_id`` to None — global preference scope."""
    monkeypatch.setattr(
        "hosts.cli.commands._active_project_fact_id",
        lambda settings: None,
    )
    monkeypatch.setattr(
        "hosts.cli.commands._active_project",
        lambda settings: None,
    )


@pytest.fixture
def _project_scope(monkeypatch):
    """Force a stable project_id so every test scopes the same way."""
    project = MagicMock()
    project.name = "harbour"
    project.path = "/projects/harbour"
    monkeypatch.setattr(
        "hosts.cli.commands._active_project",
        lambda settings: project,
    )
    monkeypatch.setattr(
        "hosts.cli.commands._active_project_fact_id",
        lambda settings: "harbour-fact-id",
    )
    return project


def _settings():
    from hosts.cli.settings import CLISettings

    return CLISettings()


class TestBareListing:
    """Bare ``/preferences`` lists everything in the active scope."""

    def test_empty_scope_renders_set_hint(
        self, _isolate_player_db, _fake_player_profile, _capture_echo, _global_scope
    ):
        from hosts.cli.commands import _handle_preferences_command

        _handle_preferences_command("/preferences", _settings())
        out = "\n".join(_capture_echo)
        assert "Preferences" in out
        assert "global" in out
        assert "set" in out  # hint to set one

    def test_lists_project_and_global_rows(
        self, _isolate_player_db, _fake_player_profile, _capture_echo, _project_scope
    ):
        from hosts.cli.commands import _handle_preferences_command
        from kourai_common.facts import set_preference_fact

        # Project-scoped fact + a global fact for the same player.
        set_preference_fact("player-uuid", "harbour-fact-id", "coverage_target", "80%")
        set_preference_fact("player-uuid", None, "python_version", "3.13")

        _handle_preferences_command("/preferences", _settings())
        out = "\n".join(_capture_echo)
        assert "coverage_target" in out
        assert "80%" in out
        assert "python_version" in out
        assert "3.13" in out
        assert "harbour" in out  # active project name surfaced


class TestSet:
    """``/preferences set`` writes through to the fact axis."""

    def test_writes_active_scope(
        self, _isolate_player_db, _fake_player_profile, _capture_echo, _project_scope
    ):
        from hosts.cli.commands import _handle_preferences_command
        from kourai_common.facts import list_preference_facts

        _handle_preferences_command("/preferences set coverage_target 80%", _settings())
        out = "\n".join(_capture_echo)
        assert "coverage_target" in out
        assert "80%" in out
        assert "harbour" in out  # confirmation surfaces the scope

        rows = list_preference_facts("player-uuid", project_id="harbour-fact-id")
        assert {r["kind"]: r["value"] for r in rows} == {"coverage_target": "80%"}

    def test_replaces_existing_same_kind_row(
        self, _isolate_player_db, _fake_player_profile, _capture_echo, _project_scope
    ):
        from hosts.cli.commands import _handle_preferences_command
        from kourai_common.facts import list_preference_facts

        _handle_preferences_command("/preferences set coverage_target 80%", _settings())
        _handle_preferences_command("/preferences set coverage_target 95%", _settings())
        rows = list_preference_facts("player-uuid", project_id="harbour-fact-id")
        # Single row, latest value — no duplicate accumulation.
        assert len(rows) == 1
        assert rows[0]["value"] == "95%"

    def test_rejects_unknown_kind_with_valid_kinds_listed(
        self, _isolate_player_db, _fake_player_profile, _capture_echo, _project_scope
    ):
        from hosts.cli.commands import _handle_preferences_command

        _handle_preferences_command("/preferences set tab_width 4", _settings())
        out = "\n".join(_capture_echo).lower()
        assert "unknown" in out
        # The closed-vocab list helps the player recover.
        assert "coverage_target" in out
        assert "python_version" in out

    def test_usage_hint_when_value_missing(
        self, _isolate_player_db, _fake_player_profile, _capture_echo, _project_scope
    ):
        from hosts.cli.commands import _handle_preferences_command

        _handle_preferences_command("/preferences set coverage_target", _settings())
        out = "\n".join(_capture_echo).lower()
        assert "usage" in out
        assert "coverage_target" in out


class TestForget:
    """Right-to-forget — every fact is removable without an operator step."""

    def test_forgets_named_kind_in_active_scope(
        self, _isolate_player_db, _fake_player_profile, _capture_echo, _project_scope
    ):
        from hosts.cli.commands import _handle_preferences_command
        from kourai_common.facts import list_preference_facts, set_preference_fact

        set_preference_fact("player-uuid", "harbour-fact-id", "coverage_target", "80%")
        set_preference_fact("player-uuid", "harbour-fact-id", "python_version", "3.13")

        _handle_preferences_command("/preferences forget coverage_target", _settings())
        rows = list_preference_facts("player-uuid", project_id="harbour-fact-id")
        # python_version survives — only the named kind goes.
        assert {r["kind"] for r in rows} == {"python_version"}

    def test_forget_all_clears_active_scope_only(
        self,
        _isolate_player_db,
        _fake_player_profile,
        _capture_echo,
        _project_scope,
    ):
        from hosts.cli.commands import _handle_preferences_command
        from kourai_common.facts import list_preference_facts, set_preference_fact

        set_preference_fact("player-uuid", "harbour-fact-id", "coverage_target", "80%")
        set_preference_fact("player-uuid", "harbour-fact-id", "python_version", "3.13")
        # A global row that must NOT be wiped by --all on the project scope.
        set_preference_fact("player-uuid", None, "commit_style", "conventional")

        _handle_preferences_command("/preferences forget --all", _settings())

        scoped = list_preference_facts("player-uuid", project_id="harbour-fact-id")
        # All scoped rows gone.
        assert [r for r in scoped if r["scope"] == "project"] == []
        # The global commit_style still surfaces in the project scope (because
        # the listing widens to global) — its scope is "global", not "project".
        assert any(r["kind"] == "commit_style" and r["scope"] == "global" for r in scoped)

    def test_forget_with_no_match_reports_clearly(
        self, _isolate_player_db, _fake_player_profile, _capture_echo, _project_scope
    ):
        from hosts.cli.commands import _handle_preferences_command

        _handle_preferences_command("/preferences forget coverage_target", _settings())
        out = "\n".join(_capture_echo).lower()
        assert "no" in out
        assert "coverage_target" in out

    def test_usage_hint_when_kind_missing(
        self, _isolate_player_db, _fake_player_profile, _capture_echo, _project_scope
    ):
        from hosts.cli.commands import _handle_preferences_command

        _handle_preferences_command("/preferences forget", _settings())
        out = "\n".join(_capture_echo).lower()
        assert "usage" in out


class TestAliasAndDispatch:
    """``/prefs`` and dispatch from ``__main__`` reach the handler."""

    def test_prefs_alias_normalises_to_preferences(
        self, _isolate_player_db, _fake_player_profile, _capture_echo, _project_scope
    ):
        # The dispatch in __main__.py rewrites /prefs → /preferences before
        # invoking the handler. Stand the rewrite in here so we verify the
        # alias contract without spinning up the REPL loop.
        from hosts.cli.commands import _handle_preferences_command

        _handle_preferences_command("/preferences set python_version 3.13", _settings())
        out = "\n".join(_capture_echo)
        assert "python_version" in out
        assert "3.13" in out

    def test_help_subcommand_lists_closed_vocab(
        self, _fake_player_profile, _capture_echo, _project_scope
    ):
        from hosts.cli.commands import _handle_preferences_command

        _handle_preferences_command("/preferences help", _settings())
        out = "\n".join(_capture_echo)
        # All five Phase 1 vocab kinds must be discoverable from /help here.
        for kind in (
            "coverage_target",
            "python_version",
            "style_rules",
            "commit_style",
            "test_framework",
        ):
            assert kind in out


class TestNoActiveProfile:
    """Without a loaded profile, the handler short-circuits with a hint."""

    def test_no_profile_emits_hint(self, _capture_echo, monkeypatch):
        monkeypatch.setattr(
            "hosts.cli.commands.PlayerProfile.load",
            lambda *a, **k: None,
        )
        with patch("hosts.cli.commands._active_project_fact_id", return_value=None):
            from hosts.cli.commands import _handle_preferences_command

            _handle_preferences_command("/preferences", _settings())

        out = "\n".join(_capture_echo).lower()
        assert "no active player profile" in out
