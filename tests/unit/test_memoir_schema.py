"""Schema models and gameplay-rule split logic for the Forge Memoir."""

from __future__ import annotations

import pytest

from kourai_common.federation.memoir_schema import SplitDecision


class TestSplitDecision:
    """SplitDecision is a frozen pydantic model with two booleans and an
    invariant that they cannot both be true."""

    def test_shared_eligible_only(self):
        d = SplitDecision(shared_eligible=True, private_only=False)
        assert d.shared_eligible is True
        assert d.private_only is False

    def test_private_only_only(self):
        d = SplitDecision(shared_eligible=False, private_only=True)
        assert d.shared_eligible is False
        assert d.private_only is True

    def test_neither_set_is_valid(self):
        # Used for entries that are still being constructed.
        d = SplitDecision(shared_eligible=False, private_only=False)
        assert d.shared_eligible is False
        assert d.private_only is False

    def test_both_true_is_rejected(self):
        with pytest.raises(ValueError, match="cannot both be true"):
            SplitDecision(shared_eligible=True, private_only=True)
