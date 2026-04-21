"""Tests for the pluggable command runner (sandbox.py + subprocess.run_command)."""

from __future__ import annotations

import shutil
import sys

import pytest

from kourai_common import sandbox as sandbox_mod
from kourai_common.sandbox import (
    ContainerRunner,
    HostRunner,
    _select_runner,
    get_runner,
    set_runner,
)
from kourai_common.subprocess import run_command


@pytest.fixture(autouse=True)
def _reset_runner():
    set_runner(None)
    yield
    set_runner(None)


@pytest.mark.asyncio
async def test_host_runner_executes_and_captures_stdout():
    rc, out, err = await HostRunner().run(
        [sys.executable, "-c", "print('hello')"], cwd=None, status_callback=None
    )
    assert rc == 0
    assert "hello" in out
    assert err == ""


@pytest.mark.asyncio
async def test_host_runner_streams_lines_via_status_callback():
    seen: list[str] = []

    async def cb(line: str) -> None:
        seen.append(line)

    rc, out, _ = await HostRunner().run(
        [sys.executable, "-c", "print('a'); print('b')"], cwd=None, status_callback=cb
    )
    assert rc == 0
    # status callback received the command echo + each non-blank stdout line
    assert seen[0].startswith("$ ")
    assert "a" in seen
    assert "b" in seen
    assert out.splitlines() == ["a", "b"]


@pytest.mark.asyncio
async def test_run_command_delegates_to_active_runner(tmp_path):
    captured = {}

    class FakeRunner:
        async def run(self, cmd, cwd, status_callback):
            captured["cmd"] = cmd
            captured["cwd"] = cwd
            return 0, "fake-out", ""

    set_runner(FakeRunner())
    rc, out, _ = await run_command(["whatever"], cwd=str(tmp_path))
    assert rc == 0
    assert out == "fake-out"
    assert captured == {"cmd": ["whatever"], "cwd": str(tmp_path)}


def test_selector_defaults_to_host(monkeypatch):
    monkeypatch.delenv("KOURAI_SANDBOX", raising=False)
    assert isinstance(_select_runner(), HostRunner)


def test_selector_picks_container_when_docker_present(monkeypatch):
    monkeypatch.setenv("KOURAI_SANDBOX", "container")
    monkeypatch.setattr(sandbox_mod.shutil, "which", lambda _: "/usr/bin/docker")
    assert isinstance(_select_runner(), ContainerRunner)


def test_selector_falls_back_when_docker_missing(monkeypatch, caplog):
    monkeypatch.setenv("KOURAI_SANDBOX", "container")
    monkeypatch.setattr(sandbox_mod.shutil, "which", lambda _: None)
    caplog.set_level("WARNING")
    runner = _select_runner()
    assert isinstance(runner, HostRunner)
    assert any("falling back to HostRunner" in m for m in caplog.messages)


def test_selector_falls_back_on_unknown_value(monkeypatch):
    monkeypatch.setenv("KOURAI_SANDBOX", "magicbox")
    assert isinstance(_select_runner(), HostRunner)


def test_get_runner_caches_selection(monkeypatch):
    set_runner(None)
    monkeypatch.delenv("KOURAI_SANDBOX", raising=False)
    a = get_runner()
    b = get_runner()
    assert a is b


@pytest.mark.asyncio
async def test_container_runner_falls_back_when_cwd_is_none():
    """ContainerRunner needs a workspace to mount; with no cwd it must fall back."""
    runner = ContainerRunner(image="kourai-sandbox:latest")
    rc, out, _ = await runner.run(
        [sys.executable, "-c", "print('host-side')"], cwd=None, status_callback=None
    )
    assert rc == 0
    assert "host-side" in out


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
@pytest.mark.asyncio
async def test_container_runner_runs_in_container(tmp_path):
    """End-to-end: requires docker + a built kourai-sandbox image."""
    # Confirm the image exists; otherwise skip rather than fail noisily.
    import subprocess as sp

    inspect = sp.run(
        ["docker", "image", "inspect", "kourai-sandbox:latest"],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspect.returncode != 0:
        pytest.skip("kourai-sandbox image not built (run `make sandbox-image`)")

    runner = ContainerRunner()
    rc, out, _ = await runner.run(
        ["python3", "-c", "print('inside')"], cwd=str(tmp_path), status_callback=None
    )
    assert rc == 0
    assert "inside" in out


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
@pytest.mark.asyncio
async def test_container_runner_can_write_to_bind_mounted_workspace(tmp_path):
    """Regression: container process must run as host uid so it can write the worktree.

    Without --user $(id -u) the in-image forge user (uid 1000) PermissionErrors on a
    workspace owned by the host user — silently breaking every real agent edit.
    """
    import subprocess as sp

    inspect = sp.run(
        ["docker", "image", "inspect", "kourai-sandbox:latest"],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspect.returncode != 0:
        pytest.skip("kourai-sandbox image not built (run `make sandbox-image`)")

    runner = ContainerRunner()
    rc, _, err = await runner.run(
        ["python3", "-c", "open('agent_wrote_this.txt','w').write('ok')"],
        cwd=str(tmp_path),
        status_callback=None,
    )
    assert rc == 0, f"container could not write to workspace: {err}"
    assert (tmp_path / "agent_wrote_this.txt").read_text() == "ok"


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not installed")
@pytest.mark.asyncio
async def test_container_runner_has_no_network(tmp_path):
    """Regression: --network none must actually disable DNS / outbound."""
    import subprocess as sp

    inspect = sp.run(
        ["docker", "image", "inspect", "kourai-sandbox:latest"],
        capture_output=True,
        text=True,
        check=False,
    )
    if inspect.returncode != 0:
        pytest.skip("kourai-sandbox image not built (run `make sandbox-image`)")

    runner = ContainerRunner()
    rc, out, _ = await runner.run(
        [
            "python3",
            "-c",
            "import socket\n"
            "try:\n"
            "    socket.gethostbyname('example.com')\n"
            "    print('LEAK')\n"
            "except Exception as e:\n"
            "    print('blocked', type(e).__name__)",
        ],
        cwd=str(tmp_path),
        status_callback=None,
    )
    assert rc == 0
    assert "blocked" in out and "LEAK" not in out
