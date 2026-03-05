"""Tests for accessibility features."""

from hosts.gui.accessibility_features import AccessibilityFeatures, AccessibilitySettings


class TestAccessibilitySettings:
    """Test AccessibilitySettings dataclass."""

    def test_default_settings(self):
        """Test default accessibility settings."""
        settings = AccessibilitySettings()
        assert settings.font_scale == 1.0
        assert settings.high_contrast is False
        assert settings.reduce_motion is False
        assert settings.enable_screen_reader is True
        assert settings.enable_keyboard_navigation is True
        assert settings.show_focus_indicators is True
        assert settings.show_text_alternatives is True


class TestAccessibilityFeatures:
    """Test AccessibilityFeatures functionality."""

    def test_initialization(self):
        """Test initialization of accessibility features."""
        features = AccessibilityFeatures()
        assert features.settings is not None
        assert len(features.aria_labels) == 0
        assert len(features.keyboard_shortcuts) == 0

    def test_set_font_scale(self):
        """Test setting font scale."""
        features = AccessibilityFeatures()
        features.set_font_scale(1.5)
        assert features.get_font_scale() == 1.5

    def test_font_scale_clamping_min(self):
        """Test font scale clamping at minimum."""
        features = AccessibilityFeatures()
        features.set_font_scale(0.5)
        assert features.get_font_scale() == 0.8

    def test_font_scale_clamping_max(self):
        """Test font scale clamping at maximum."""
        features = AccessibilityFeatures()
        features.set_font_scale(2.5)
        assert features.get_font_scale() == 2.0

    def test_set_high_contrast(self):
        """Test setting high contrast mode."""
        features = AccessibilityFeatures()
        features.set_high_contrast(True)
        assert features.is_high_contrast_enabled() is True

    def test_set_reduce_motion(self):
        """Test setting reduce motion."""
        features = AccessibilityFeatures()
        features.set_reduce_motion(True)
        assert features.should_reduce_motion() is True

    def test_set_screen_reader_support(self):
        """Test setting screen reader support."""
        features = AccessibilityFeatures()
        features.set_screen_reader_support(False)
        assert features.is_screen_reader_enabled() is False

    def test_set_keyboard_navigation(self):
        """Test setting keyboard navigation."""
        features = AccessibilityFeatures()
        features.set_keyboard_navigation(False)
        assert features.is_keyboard_navigation_enabled() is False

    def test_set_focus_indicators(self):
        """Test setting focus indicators."""
        features = AccessibilityFeatures()
        features.set_focus_indicators(False)
        assert features.should_show_focus_indicators() is False

    def test_add_aria_label(self):
        """Test adding ARIA label."""
        features = AccessibilityFeatures()
        features.add_aria_label("button_1", "Submit button")
        assert features.get_aria_label("button_1") == "Submit button"

    def test_get_aria_label_nonexistent(self):
        """Test getting non-existent ARIA label."""
        features = AccessibilityFeatures()
        assert features.get_aria_label("nonexistent") == ""

    def test_add_keyboard_shortcut(self):
        """Test adding keyboard shortcut."""
        features = AccessibilityFeatures()
        features.add_keyboard_shortcut("Ctrl+K", "Focus input bar")
        assert "Ctrl+K" in features.get_keyboard_shortcuts()

    def test_get_keyboard_shortcuts(self):
        """Test getting all keyboard shortcuts."""
        features = AccessibilityFeatures()
        features.add_keyboard_shortcut("Ctrl+K", "Focus input bar")
        features.add_keyboard_shortcut("Ctrl+L", "Clear input bar")

        shortcuts = features.get_keyboard_shortcuts()
        assert len(shortcuts) == 2
        assert shortcuts["Ctrl+K"] == "Focus input bar"
        assert shortcuts["Ctrl+L"] == "Clear input bar"

    def test_get_accessibility_report(self):
        """Test getting accessibility report."""
        features = AccessibilityFeatures()
        features.set_font_scale(1.2)
        features.set_high_contrast(True)
        features.add_aria_label("button_1", "Submit")
        features.add_keyboard_shortcut("Ctrl+K", "Focus")

        report = features.get_accessibility_report()

        assert report["font_scale"] == 1.2
        assert report["font_scale_compliant"] is True
        assert report["high_contrast"] is True
        assert report["aria_labels_count"] == 1
        assert report["keyboard_shortcuts_count"] == 1

    def test_wcag_aa_compliance_default(self):
        """Test WCAG AA compliance with default settings."""
        features = AccessibilityFeatures()
        report = features.get_accessibility_report()
        assert report["wcag_aa_compliant"] is True

    def test_wcag_aa_compliance_disabled_keyboard_nav(self):
        """Test WCAG AA compliance with keyboard navigation disabled."""
        features = AccessibilityFeatures()
        features.set_keyboard_navigation(False)
        report = features.get_accessibility_report()
        assert report["wcag_aa_compliant"] is False

    def test_wcag_aa_compliance_disabled_focus_indicators(self):
        """Test WCAG AA compliance with focus indicators disabled."""
        features = AccessibilityFeatures()
        features.set_focus_indicators(False)
        report = features.get_accessibility_report()
        assert report["wcag_aa_compliant"] is False

    def test_wcag_aa_compliance_disabled_screen_reader(self):
        """Test WCAG AA compliance with screen reader disabled."""
        features = AccessibilityFeatures()
        features.set_screen_reader_support(False)
        report = features.get_accessibility_report()
        assert report["wcag_aa_compliant"] is False

    def test_wcag_aa_compliance_invalid_font_scale(self):
        """Test WCAG AA compliance with invalid font scale."""
        features = AccessibilityFeatures()
        features.set_font_scale(0.5)  # Will be clamped to 0.8
        report = features.get_accessibility_report()
        assert report["wcag_aa_compliant"] is True  # Clamped value is valid

    def test_keyboard_shortcuts_copy(self):
        """Test that get_keyboard_shortcuts returns a copy."""
        features = AccessibilityFeatures()
        features.add_keyboard_shortcut("Ctrl+K", "Focus")

        shortcuts = features.get_keyboard_shortcuts()
        shortcuts["Ctrl+L"] = "Clear"

        # Original should not be modified
        assert len(features.get_keyboard_shortcuts()) == 1
