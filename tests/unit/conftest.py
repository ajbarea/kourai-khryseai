"""Test isolation for ``hosts.gui.constants`` module-level state.

The constants module owns three mutable singletons that bleed across tests
under ``pytest -n auto``:

- ``_font_scale``: ``GUIComponentsIntegration._load_settings`` calls
  ``set_font_scale(...)`` at construction time, so any test that
  instantiates the integration with a non-default saved scale (e.g.
  ``test_load_settings_font_scale``) leaves ``_font_scale`` mutated for
  the rest of the worker.
- ``_font_scale_listeners``: ``on_font_scale_change`` only ever appends.
  ``test_listener_exception_does_not_break_others`` registers a
  perpetually-throwing lambda that fires on every subsequent
  ``set_font_scale`` call on the worker.
- ``_font_proxy_registry``: ``FontProxy.__init__`` only ever appends.

This autouse fixture snapshots the three on entry and restores them on
exit so collection-order accidents can't surface as test failures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _isolate_gui_constants_state() -> Iterator[None]:
    try:
        from hosts.gui import constants
    except ImportError:
        # pygame missing in this environment — nothing to isolate.
        yield
        return

    saved_scale = constants._font_scale
    saved_listeners = list(constants._font_scale_listeners)
    saved_registry = list(constants._font_proxy_registry)
    try:
        yield
    finally:
        constants._font_scale = saved_scale
        constants._font_scale_listeners[:] = saved_listeners
        constants._font_proxy_registry[:] = saved_registry
