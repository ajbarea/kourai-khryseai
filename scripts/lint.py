"""Code quality checks and formatting.

Two passes are available — ``fix`` (every auto-fixer) and ``check`` (every
strict check, no mutation). The dev_cli ``lint`` task and ``validate.py``
both invoke this script with ``--check-only`` so they mirror CI's strict
``ruff format --check`` semantics; the ``fix`` task uses ``--fix-only``
to apply auto-formatters without then verifying. Running the script with
no flags runs both passes in order — useful for ad-hoc local cleanup.
Output streams live to the terminal and to ``logs/dev-runner-latest.log`` (see
scripts/dev_log.py).

Usage:
    uv run kourai-dev lint        # check-only (CI-equivalent; via dev_cli)
    uv run kourai-dev fix         # fix-only (via dev_cli)
    python scripts/lint.py [--check-only | --fix-only]
"""

from __future__ import annotations

import argparse
import importlib.util
import sys

from kourai_common.dev_log import (
    C_GREEN,
    C_RED,
    C_RESET,
    LOG,
    StepFailedError,
    print_header,
    run_step,
)

TY_PATHS = (
    "agents",
    "hosts/cli",
    "hosts/gui",
    "mcp_servers",
    "scripts",
    "shared/src",
    "tests",
)


# Third-party modules ty must resolve to type-check hosts/cli and hosts/gui.
# They only exist in a workspace-wide sync. A venv synced to one package -- or
# the Docker-side `.venv` that uv picks by default on a WSL host -- lacks them,
# and ty then emits 30 unresolved-import errors that name the modules but not
# the cause. CI never hits this: it runs `uv sync --all-packages --dev`.
TY_ENV_MARKERS = ("asyncclick", "prompt_toolkit", "PIL")


def check_ty_environment() -> int:
    """Fail fast when the active venv can't support a type check. 0 = usable."""
    missing = [name for name in TY_ENV_MARKERS if importlib.util.find_spec(name) is None]
    if not missing:
        return 0
    print(f"{C_RED}  x ty environment is incomplete{C_RESET}")
    print(f"    Missing from {sys.prefix}: {', '.join(missing)}")
    print("    These are hosts/cli + hosts/gui dependencies. Without them ty")
    print("    reports unresolved-import errors that look like code defects.")
    print("    Fix:  uv sync --all-packages --dev")
    print("    If that synced the wrong venv, set UV_PROJECT_ENVIRONMENT for")
    print("    your platform -- see docs/getting-started.md. `make` does this")
    print("    for you; a bare `uv run kourai-dev lint` relies on your shell.")
    LOG.event("ERROR", f"ty environment incomplete: missing {', '.join(missing)}")
    return 1


def fix_pass() -> None:
    """Run every auto-fixer. Failures here are real tool errors, not lint findings."""
    print_header("Fix pass")
    run_step(["ruff", "format", "."], label="ruff-format")
    run_step(
        ["ruff", "check", "--fix", "--unsafe-fixes", "--show-fixes", "."],
        label="ruff-fix",
        check=False,
    )


def check_pass() -> int:
    """Run each check. Returns non-zero if anything fails; does not raise."""
    print_header("Check pass")
    rcs: list[tuple[str, int]] = []
    rcs.append(
        (
            "ruff-format --check",
            run_step(["ruff", "format", "--check", "."], label="ruff-format-check", check=False),
        )
    )
    rcs.append(
        (
            "ruff-check",
            run_step(["ruff", "check", "."], label="ruff-check", check=False),
        )
    )
    env_rc = check_ty_environment()
    rcs.append(
        (
            "ty",
            env_rc or run_step(["ty", "check", *TY_PATHS], label="ty-check", check=False),
        )
    )

    print()
    print("  Summary")
    print("=" * 60)
    overall = 0
    for name, rc in rcs:
        mark = f"{C_GREEN}+{C_RESET}" if rc == 0 else f"{C_RED}x{C_RESET}"
        print(f"  {mark} {name} (rc={rc})")
        if rc != 0:
            overall = rc
    print("=" * 60)
    if overall == 0:
        print(f"{C_GREEN}+ All checks passed{C_RESET}\n")
    else:
        print(f"{C_RED}x Some checks failed. Full details: logs/dev-runner-latest.log{C_RESET}\n")
    return overall


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lint", description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--fix-only",
        action="store_true",
        help="Run auto-fixers only; skip the check pass.",
    )
    group.add_argument(
        "--check-only",
        action="store_true",
        help="Run the check pass only; skip auto-fixers.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    LOG.open("lint")
    LOG.session_header("lint", sys.argv[1:])

    overall = 0
    try:
        if not args.check_only:
            fix_pass()
        if not args.fix_only:
            overall = check_pass()
    except StepFailedError as exc:
        LOG.event("ERROR", f"step raised: {exc}")
        overall = exc.returncode
    finally:
        LOG.session_footer(overall)
    return overall


if __name__ == "__main__":
    sys.exit(main())
