"""Integration of high contrast mode with the main GUI."""

from .high_contrast_colors import get_color_palette, is_wcag_aa_compliant


class HighContrastGUIIntegration:
    """Manages high contrast mode integration with the GUI."""

    def __init__(self, gui_instance, settings_manager):
        """Initialize high contrast integration.

        Args:
            gui_instance: The main GUI instance.
            settings_manager: The settings manager instance.
        """
        self.gui = gui_instance
        self.settings = settings_manager
        self.high_contrast_enabled = settings_manager.get("high_contrast", False)

    def enable_high_contrast(self) -> None:
        """Enable high contrast mode."""
        self.high_contrast_enabled = True
        self.settings.set("high_contrast", True)
        self.settings.save()
        self._apply_high_contrast()

    def disable_high_contrast(self) -> None:
        """Disable high contrast mode."""
        self.high_contrast_enabled = False
        self.settings.set("high_contrast", False)
        self.settings.save()
        self._apply_standard_contrast()

    def toggle_high_contrast(self) -> None:
        """Toggle high contrast mode."""
        if self.high_contrast_enabled:
            self.disable_high_contrast()
        else:
            self.enable_high_contrast()

    def is_high_contrast_enabled(self) -> bool:
        """Check if high contrast mode is enabled."""
        return self.high_contrast_enabled

    def get_color_palette(self) -> dict[str, tuple[int, int, int]]:
        """Get the current color palette."""
        return get_color_palette(self.high_contrast_enabled)

    def get_color(self, name: str) -> tuple[int, int, int]:
        """Get a specific color from the current palette.

        Args:
            name: Color name.

        Returns:
            RGB tuple for the color.
        """
        palette = self.get_color_palette()
        return palette.get(name, (255, 255, 255))

    def verify_wcag_compliance(
        self, fg: tuple[int, int, int], bg: tuple[int, int, int], large_text: bool = False
    ) -> bool:
        """Verify WCAG 2.2 Level AA compliance for color combination.

        Args:
            fg: Foreground color RGB tuple.
            bg: Background color RGB tuple.
            large_text: Whether text is large (18pt+ or 14pt+ bold).

        Returns:
            True if combination meets WCAG AA standards.
        """
        return is_wcag_aa_compliant(fg, bg, large_text)

    def _apply_high_contrast(self) -> None:
        """Apply high contrast colors to GUI elements."""
        # This would be called by the GUI to update all elements
        # Implementation depends on GUI architecture

    def _apply_standard_contrast(self) -> None:
        """Apply standard colors to GUI elements."""
        # This would be called by the GUI to update all elements
        # Implementation depends on GUI architecture
