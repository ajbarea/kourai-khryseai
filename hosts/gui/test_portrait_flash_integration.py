"""Unit tests for PortraitFlashIntegration class."""

from portrait_flash_integration import PortraitFlashIntegration


class TestPortraitFlashIntegrationBasic:
    """Test basic PortraitFlashIntegration initialization and state."""

    def test_init_default_enabled(self) -> None:
        """Test default initialization with flash enabled."""
        integration = PortraitFlashIntegration()
        assert integration.enabled is True
        assert integration._last_agent is None

    def test_init_disabled(self) -> None:
        """Test initialization with flash disabled."""
        integration = PortraitFlashIntegration(enabled=False)
        assert integration.enabled is False

    def test_on_agent_switch_triggers_flash(self) -> None:
        """Test agent switch triggers flash effect."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        assert integration.is_active() is True
        assert integration._last_agent == "hephaestus"

    def test_on_agent_switch_with_custom_duration(self) -> None:
        """Test agent switch with custom duration."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("metis", duration_ms=300)
        assert integration.flash_effect.current_duration_ms == 300

    def test_on_agent_switch_when_disabled(self) -> None:
        """Test agent switch when flash is disabled."""
        integration = PortraitFlashIntegration(enabled=False)
        integration.on_agent_switch("hephaestus")
        assert integration.is_active() is False

    def test_is_active_initially_false(self) -> None:
        """Test is_active returns False initially."""
        integration = PortraitFlashIntegration()
        assert integration.is_active() is False

    def test_is_active_after_switch(self) -> None:
        """Test is_active returns True after agent switch."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        assert integration.is_active() is True

    def test_reset(self) -> None:
        """Test reset functionality."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        assert integration.is_active() is True
        integration.reset()
        assert integration.is_active() is False
        assert integration._last_agent is None


class TestPortraitFlashIntegrationUpdate:
    """Test update and alpha value handling."""

    def test_update_returns_tuple(self) -> None:
        """Test update returns (active, alpha) tuple."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        result = integration.update(0.016)
        assert isinstance(result, tuple)
        assert len(result) == 2
        active, alpha = result
        assert isinstance(active, bool)
        assert isinstance(alpha, int)

    def test_update_with_zero_delta_time(self) -> None:
        """Test update with zero delta time."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        active, alpha = integration.update(0.0)
        assert active is True
        assert alpha == 150  # Start alpha

    def test_update_alpha_decreases(self) -> None:
        """Test alpha decreases over time."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus", duration_ms=200)
        active1, alpha1 = integration.update(0.050)
        active2, alpha2 = integration.update(0.050)
        assert alpha2 < alpha1

    def test_update_completes_effect(self) -> None:
        """Test update completes effect."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus", duration_ms=200)
        # Update multiple times to complete
        for _ in range(20):
            active, alpha = integration.update(0.020)
        assert active is False
        assert alpha == 0

    def test_get_flash_alpha(self) -> None:
        """Test get_flash_alpha returns current alpha."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        alpha = integration.get_flash_alpha()
        assert 0 <= alpha <= 255

    def test_get_flash_alpha_when_inactive(self) -> None:
        """Test get_flash_alpha when flash is inactive."""
        integration = PortraitFlashIntegration()
        alpha = integration.get_flash_alpha()
        assert alpha == 0


class TestPortraitFlashIntegrationEnableDisable:
    """Test enable/disable functionality."""

    def test_set_enabled_true(self) -> None:
        """Test enabling flash effect."""
        integration = PortraitFlashIntegration(enabled=False)
        integration.set_enabled(True)
        assert integration.enabled is True

    def test_set_enabled_false(self) -> None:
        """Test disabling flash effect."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        assert integration.is_active() is True
        integration.set_enabled(False)
        assert integration.enabled is False
        assert integration.is_active() is False

    def test_set_enabled_false_resets_effect(self) -> None:
        """Test disabling resets the flash effect."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        integration.set_enabled(False)
        assert integration.flash_effect._timer == 0.0
        assert integration.flash_effect.active is False

    def test_disabled_flash_ignores_switches(self) -> None:
        """Test disabled flash ignores agent switches."""
        integration = PortraitFlashIntegration(enabled=False)
        integration.on_agent_switch("hephaestus")
        integration.on_agent_switch("metis")
        assert integration.is_active() is False


class TestPortraitFlashIntegrationMultipleSwitches:
    """Test multiple agent switches."""

    def test_multiple_switches_in_sequence(self) -> None:
        """Test multiple agent switches in sequence."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        assert integration._last_agent == "hephaestus"
        integration.on_agent_switch("metis")
        assert integration._last_agent == "metis"

    def test_switch_resets_timer(self) -> None:
        """Test switch resets the timer."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus", duration_ms=200)
        integration.update(0.050)
        assert integration.flash_effect._timer > 0.0
        integration.on_agent_switch("metis", duration_ms=200)
        assert integration.flash_effect._timer == 0.0

    def test_switch_during_active_flash(self) -> None:
        """Test switching agents during active flash."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus", duration_ms=200)
        integration.update(0.050)
        assert integration.is_active() is True
        # Switch to new agent
        integration.on_agent_switch("metis", duration_ms=200)
        assert integration._last_agent == "metis"
        assert integration.is_active() is True


class TestPortraitFlashIntegrationDuration:
    """Test duration handling."""

    def test_default_duration(self) -> None:
        """Test default duration is used."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        assert integration.flash_effect.current_duration_ms == 350

    def test_custom_duration_200ms(self) -> None:
        """Test custom duration 200ms."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus", duration_ms=200)
        assert integration.flash_effect.current_duration_ms == 200

    def test_custom_duration_500ms(self) -> None:
        """Test custom duration 500ms."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus", duration_ms=500)
        assert integration.flash_effect.current_duration_ms == 500

    def test_duration_affects_fade_speed(self) -> None:
        """Test duration affects fade speed."""
        integration1 = PortraitFlashIntegration()
        integration1.on_agent_switch("hephaestus", duration_ms=200)
        _, alpha1 = integration1.update(0.050)

        integration2 = PortraitFlashIntegration()
        integration2.on_agent_switch("hephaestus", duration_ms=500)
        _, alpha2 = integration2.update(0.050)

        # Shorter duration should fade faster
        assert alpha1 < alpha2


class TestPortraitFlashIntegrationEdgeCases:
    """Test edge cases and error conditions."""

    def test_update_when_disabled(self) -> None:
        """Test update when flash is disabled."""
        integration = PortraitFlashIntegration(enabled=False)
        active, alpha = integration.update(0.016)
        assert active is False
        assert alpha == 0

    def test_multiple_resets(self) -> None:
        """Test multiple resets."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        integration.reset()
        integration.reset()
        assert integration.is_active() is False

    def test_switch_to_same_agent(self) -> None:
        """Test switching to same agent."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus")
        integration.on_agent_switch("hephaestus")
        assert integration._last_agent == "hephaestus"

    def test_very_short_duration(self) -> None:
        """Test very short duration (at minimum)."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus", duration_ms=200)
        active, alpha = integration.update(0.200)
        assert active is False
        assert alpha == 0

    def test_very_long_duration(self) -> None:
        """Test very long duration (at maximum)."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus", duration_ms=500)
        active, alpha = integration.update(0.100)
        assert active is True
        assert alpha > 0

    def test_alpha_range(self) -> None:
        """Test alpha stays within valid range."""
        integration = PortraitFlashIntegration()
        integration.on_agent_switch("hephaestus", duration_ms=200)
        for _ in range(30):
            active, alpha = integration.update(0.010)
            assert 0 <= alpha <= 255
