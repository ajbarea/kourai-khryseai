"""Accessibility features for WCAG 2.2 Level AA compliance."""

from dataclasses import dataclass


@dataclass
class AccessibilitySettings:
    """Accessibility settings for the GUI."""

    # Font scaling (80% to 200%)
    font_scale: float = 1.0

    # High contrast mode
    high_contrast: bool = False

    # Reduce motion (for users with motion sensitivity)
    reduce_motion: bool = False

    # Screen reader support
    enable_screen_reader: bool = True

    # Keyboard navigation
    enable_keyboard_navigation: bool = True

    # Focus indicators
    show_focus_indicators: bool = True

    # Text alternatives
    show_text_alternatives: bool = True


class AccessibilityFeatures:
    """Manages accessibility features for WCAG 2.2 Level AA compliance."""

    def __init__(self):
        """Initialize accessibility features."""
        self.settings = AccessibilitySettings()
        self.aria_labels: dict[str, str] = {}
        self.keyboard_shortcuts: dict[str, str] = {}

    def set_font_scale(self, scale: float) -> None:
        """Set font scale (80% to 200%).

        Args:
            scale: Font scale factor (0.8 to 2.0).
        """
        self.settings.font_scale = max(0.8, min(2.0, scale))

    def get_font_scale(self) -> float:
        """Get current font scale.

        Returns:
            Font scale factor.
        """
        return self.settings.font_scale

    def set_high_contrast(self, enabled: bool) -> None:
        """Set high contrast mode.

        Args:
            enabled: Whether to enable high contrast mode.
        """
        self.settings.high_contrast = enabled

    def is_high_contrast_enabled(self) -> bool:
        """Check if high contrast mode is enabled.

        Returns:
            True if high contrast is enabled.
        """
        return self.settings.high_contrast

    def set_reduce_motion(self, enabled: bool) -> None:
        """Set reduce motion preference.

        Args:
            enabled: Whether to reduce motion.
        """
        self.settings.reduce_motion = enabled

    def should_reduce_motion(self) -> bool:
        """Check if motion should be reduced.

        Returns:
            True if motion should be reduced.
        """
        return self.settings.reduce_motion

    def set_screen_reader_support(self, enabled: bool) -> None:
        """Set screen reader support.

        Args:
            enabled: Whether to enable screen reader support.
        """
        self.settings.enable_screen_reader = enabled

    def is_screen_reader_enabled(self) -> bool:
        """Check if screen reader support is enabled.

        Returns:
            True if screen reader support is enabled.
        """
        return self.settings.enable_screen_reader

    def set_keyboard_navigation(self, enabled: bool) -> None:
        """Set keyboard navigation.

        Args:
            enabled: Whether to enable keyboard navigation.
        """
        self.settings.enable_keyboard_navigation = enabled

    def is_keyboard_navigation_enabled(self) -> bool:
        """Check if keyboard navigation is enabled.

        Returns:
            True if keyboard navigation is enabled.
        """
        return self.settings.enable_keyboard_navigation

    def set_focus_indicators(self, enabled: bool) -> None:
        """Set focus indicators.

        Args:
            enabled: Whether to show focus indicators.
        """
        self.settings.show_focus_indicators = enabled

    def should_show_focus_indicators(self) -> bool:
        """Check if focus indicators should be shown.

        Returns:
            True if focus indicators should be shown.
        """
        return self.settings.show_focus_indicators

    def add_aria_label(self, element_id: str, label: str) -> None:
        """Add ARIA label for an element.

        Args:
            element_id: ID of the element.
            label: ARIA label text.
        """
        self.aria_labels[element_id] = label

    def get_aria_label(self, element_id: str) -> str:
        """Get ARIA label for an element.

        Args:
            element_id: ID of the element.

        Returns:
            ARIA label text or empty string if not found.
        """
        return self.aria_labels.get(element_id, "")

    def add_keyboard_shortcut(self, shortcut: str, description: str) -> None:
        """Add keyboard shortcut.

        Args:
            shortcut: Keyboard shortcut (e.g., "Ctrl+K").
            description: Description of what the shortcut does.
        """
        self.keyboard_shortcuts[shortcut] = description

    def get_keyboard_shortcuts(self) -> dict[str, str]:
        """Get all keyboard shortcuts.

        Returns:
            Dictionary of shortcuts to descriptions.
        """
        return self.keyboard_shortcuts.copy()

    def get_accessibility_report(self) -> dict:
        """Get accessibility compliance report.

        Returns:
            Dictionary with accessibility metrics.
        """
        return {
            "font_scale": self.settings.font_scale,
            "font_scale_compliant": 0.8 <= self.settings.font_scale <= 2.0,
            "high_contrast": self.settings.high_contrast,
            "reduce_motion": self.settings.reduce_motion,
            "screen_reader_enabled": self.settings.enable_screen_reader,
            "keyboard_navigation_enabled": self.settings.enable_keyboard_navigation,
            "focus_indicators_shown": self.settings.show_focus_indicators,
            "aria_labels_count": len(self.aria_labels),
            "keyboard_shortcuts_count": len(self.keyboard_shortcuts),
            "wcag_aa_compliant": self._check_wcag_aa_compliance(),
        }

    def _check_wcag_aa_compliance(self) -> bool:
        """Check if meeting WCAG 2.2 Level AA compliance.

        Returns:
            True if meeting compliance requirements.
        """
        # Check font scaling (WCAG 2.2 SC 1.4.4)
        if not (0.8 <= self.settings.font_scale <= 2.0):
            return False

        # Check keyboard navigation (WCAG 2.2 SC 2.1.1)
        if not self.settings.enable_keyboard_navigation:
            return False

        # Check focus indicators (WCAG 2.2 SC 2.4.7)
        if not self.settings.show_focus_indicators:
            return False

        # Check screen reader support (WCAG 2.2 SC 4.1.2)
        return self.settings.enable_screen_reader
