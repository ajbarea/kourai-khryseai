"""Unit tests for TypewriterFlashIntegration class."""

from hosts.gui.flash_effect import FlashEffect
from hosts.gui.typewriter import TypewriterManager
from hosts.gui.typewriter_flash_integration import TypewriterFlashIntegration


class TestTypewriterFlashIntegrationBasic:
    """Test basic TypewriterFlashIntegration initialization and state."""

    def test_init_default_enabled(self) -> None:
        """Test default initialization with integration enabled."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)
        assert integration.enabled is True
        assert integration._was_paused_before_flash is False

    def test_init_disabled(self) -> None:
        """Test initialization with integration disabled."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash, enabled=False)
        assert integration.enabled is False

    def test_on_flash_start_pauses_typewriter(self) -> None:
        """Test flash start pauses active typewriter."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        # Start typewriter
        typewriter.start("Hello world")
        assert typewriter.paused is False

        # Start flash
        integration.on_flash_start()
        assert typewriter.paused is True

    def test_on_flash_start_when_typewriter_inactive(self) -> None:
        """Test flash start when typewriter is inactive."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        # Don't start typewriter
        assert typewriter.active is False
        integration.on_flash_start()
        assert typewriter.paused is False

    def test_on_flash_complete_resumes_typewriter(self) -> None:
        """Test flash complete resumes typewriter."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        # Start typewriter and pause it via flash
        typewriter.start("Hello world")
        integration.on_flash_start()
        assert typewriter.paused is True

        # Complete flash
        integration.on_flash_complete()
        assert typewriter.paused is False

    def test_on_flash_complete_respects_previous_pause_state(self) -> None:
        """Test flash complete respects previous pause state."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        # Start typewriter and pause it manually
        typewriter.start("Hello world")
        typewriter.pause()
        assert typewriter.paused is True

        # Start flash (should not change pause state)
        integration.on_flash_start()
        assert typewriter.paused is True

        # Complete flash (should not resume since it was already paused)
        integration.on_flash_complete()
        assert typewriter.paused is True


class TestTypewriterFlashIntegrationUpdate:
    """Test update method and automatic pause/resume."""

    def test_update_with_active_flash(self) -> None:
        """Test update with active flash effect."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world")
        flash.trigger(duration_ms=200)
        integration.on_flash_start()

        # Update should not resume yet
        integration.update(0.050)
        assert typewriter.paused is True

    def test_update_completes_flash_and_resumes(self) -> None:
        """Test update completes flash and resumes typewriter."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world")
        flash.trigger(duration_ms=200)
        integration.on_flash_start()
        assert typewriter.paused is True

        # Update multiple times to complete flash
        for _ in range(20):
            integration.update(0.020)

        # Typewriter should be resumed
        assert typewriter.paused is False

    def test_update_when_disabled(self) -> None:
        """Test update when integration is disabled."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash, enabled=False)

        typewriter.start("Hello world")
        flash.trigger(duration_ms=200)
        integration.on_flash_start()

        # Typewriter should not be paused
        assert typewriter.paused is False


class TestTypewriterFlashIntegrationTrigger:
    """Test trigger_flash_with_pause method."""

    def test_trigger_flash_with_pause(self) -> None:
        """Test trigger_flash_with_pause pauses typewriter."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world")
        assert typewriter.paused is False

        integration.trigger_flash_with_pause(duration_ms=300)
        assert typewriter.paused is True
        assert flash.active is True

    def test_trigger_flash_with_pause_default_duration(self) -> None:
        """Test trigger_flash_with_pause with default duration."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world")
        integration.trigger_flash_with_pause()
        assert flash.active is True
        assert flash.current_duration_ms == 350  # Default

    def test_trigger_flash_with_pause_when_disabled(self) -> None:
        """Test trigger_flash_with_pause when integration is disabled."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash, enabled=False)

        typewriter.start("Hello world")
        integration.trigger_flash_with_pause()
        assert typewriter.paused is False
        assert flash.active is False


class TestTypewriterFlashIntegrationEnableDisable:
    """Test enable/disable functionality."""

    def test_set_enabled_true(self) -> None:
        """Test enabling integration."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash, enabled=False)
        integration.set_enabled(True)
        assert integration.enabled is True

    def test_set_enabled_false(self) -> None:
        """Test disabling integration."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)
        integration.set_enabled(False)
        assert integration.enabled is False

    def test_disabled_integration_ignores_flash_start(self) -> None:
        """Test disabled integration ignores flash start."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash, enabled=False)

        typewriter.start("Hello world")
        integration.on_flash_start()
        assert typewriter.paused is False


class TestTypewriterFlashIntegrationReset:
    """Test reset functionality."""

    def test_reset_resumes_typewriter(self) -> None:
        """Test reset resumes typewriter."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world")
        integration.on_flash_start()
        assert typewriter.paused is True

        integration.reset()
        assert typewriter.paused is False

    def test_reset_clears_pause_state(self) -> None:
        """Test reset clears pause state."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world")
        integration.on_flash_start()
        assert integration._was_paused_before_flash is False

        integration.reset()
        assert integration._was_paused_before_flash is False

    def test_reset_when_typewriter_inactive(self) -> None:
        """Test reset when typewriter is inactive."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        integration.reset()
        assert typewriter.paused is False


class TestTypewriterFlashIntegrationSequence:
    """Test complete sequences of typewriter and flash effects."""

    def test_full_sequence_typewriter_then_flash(self) -> None:
        """Test full sequence: start typewriter, trigger flash, complete flash."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        # Start typewriter
        typewriter.start("Hello world", speed_ms=30)
        assert typewriter.active is True
        assert typewriter.paused is False

        # Trigger flash
        integration.trigger_flash_with_pause(duration_ms=200)
        assert typewriter.paused is True
        assert flash.active is True

        # Update to complete flash
        for _ in range(20):
            integration.update(0.020)

        # Typewriter should be resumed
        assert typewriter.paused is False
        assert flash.active is False

    def test_multiple_flash_cycles(self) -> None:
        """Test multiple flash cycles."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world", speed_ms=30)

        # First flash cycle
        integration.trigger_flash_with_pause(duration_ms=200)
        assert typewriter.paused is True
        for _ in range(20):
            integration.update(0.020)
        assert typewriter.paused is False

        # Second flash cycle
        integration.trigger_flash_with_pause(duration_ms=200)
        assert typewriter.paused is True
        for _ in range(20):
            integration.update(0.020)
        assert typewriter.paused is False

    def test_flash_during_typewriter_animation(self) -> None:
        """Test flash triggered during active typewriter animation."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        # Start typewriter
        typewriter.start("Hello world", speed_ms=30)
        typewriter.update(0.050)  # Animate a bit
        assert typewriter.displayed_chars > 0

        # Trigger flash
        integration.trigger_flash_with_pause(duration_ms=200)
        assert typewriter.paused is True
        displayed_before = typewriter.displayed_chars

        # Update during flash
        for _ in range(10):
            integration.update(0.020)

        # Typewriter should not have advanced
        assert typewriter.displayed_chars == displayed_before

        # Complete flash
        for _ in range(10):
            integration.update(0.020)

        # Typewriter should resume and advance
        assert typewriter.paused is False


class TestTypewriterFlashIntegrationEdgeCases:
    """Test edge cases and error conditions."""

    def test_flash_start_when_typewriter_already_paused(self) -> None:
        """Test flash start when typewriter is already paused."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world")
        typewriter.pause()
        assert typewriter.paused is True

        integration.on_flash_start()
        assert typewriter.paused is True
        assert integration._was_paused_before_flash is True

    def test_multiple_flash_starts(self) -> None:
        """Test multiple flash starts without completion."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world")
        integration.on_flash_start()
        assert typewriter.paused is True

        # Start another flash
        integration.on_flash_start()
        assert typewriter.paused is True

    def test_flash_complete_without_start(self) -> None:
        """Test flash complete without start."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world")
        # Don't call on_flash_start
        integration.on_flash_complete()
        assert typewriter.paused is False

    def test_reset_multiple_times(self) -> None:
        """Test reset called multiple times."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world")
        integration.on_flash_start()
        integration.reset()
        integration.reset()
        assert typewriter.paused is False

    def test_integration_with_typewriter_skip(self) -> None:
        """Test integration with typewriter skip."""
        typewriter = TypewriterManager()
        flash = FlashEffect()
        integration = TypewriterFlashIntegration(typewriter, flash)

        typewriter.start("Hello world", speed_ms=30)
        integration.trigger_flash_with_pause(duration_ms=200)
        assert typewriter.paused is True

        # Skip typewriter
        typewriter.skip()
        assert typewriter.active is False

        # Complete flash
        for _ in range(20):
            integration.update(0.020)

        # Typewriter should remain inactive
        assert typewriter.active is False
