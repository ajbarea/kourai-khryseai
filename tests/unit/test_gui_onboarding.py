# ruff: noqa: E402
from __future__ import annotations

import pygame

pygame.init()
import pygame.freetype

from hosts.gui.onboarding_ui import (
    STEP_DONE,
    STEP_NAME,
    STEP_PRONOUNS,
    STEP_PRONUNCIATION,
    STEP_TITLE,
    STEP_WELCOME,
    OnboardingOverlay,
)
from tests.unit.gui_test_helpers import _surf


class TestOnboardingOverlay:
    def test_init(self):
        o = OnboardingOverlay(800, 600)
        assert o.active is False
        assert o.step == STEP_NAME
        assert o._result is None

    def test_update_layout_repositions_panel(self):
        o = OnboardingOverlay(800, 600)

        o.update_layout(1280, 720)

        assert o.panel_rect.center == (640, 360)

    def test_start(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        assert o.active is True
        assert o.step == STEP_NAME

    def test_get_result_none(self):
        o = OnboardingOverlay(800, 600)
        assert o.get_result() is None

    def test_update(self):
        o = OnboardingOverlay(800, 600)
        o.active = True
        o.update(0.5)
        assert o.alpha > 0

    def test_handle_event_inactive(self):
        o = OnboardingOverlay(800, 600)
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        assert o.handle_event(event) is False

    def test_name_step_typing(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="A")
        o.handle_event(event)
        assert o.name_text == "A"

    def test_name_step_backspace(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.name_text = "AB"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode="\b")
        o.handle_event(event)
        assert o.name_text == "A"

    def test_name_step_enter_advances(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.name_text = "TestName"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        o.handle_event(event)
        assert o.step == STEP_PRONUNCIATION
        assert o.tts_text == "TestName"

    def test_name_step_enter_empty_stays(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.name_text = ""
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        o.handle_event(event)
        assert o.step == STEP_NAME

    def test_pronunciation_step_typing(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_PRONUNCIATION
        o.tts_text = "Test"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_x, unicode="x")
        o.handle_event(event)
        assert o.tts_text == "Testx"

    def test_pronunciation_step_enter_advances(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_PRONUNCIATION
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        o.handle_event(event)
        assert o.step == STEP_TITLE

    def test_title_step_click(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_TITLE
        o.name_text = "Test"
        # Draw to populate _button_rects
        s = _surf()
        o.draw(s)
        if o._button_rects:
            rect = o._button_rects[0]
            o._handle_click((rect.centerx, rect.centery))
            assert o.step == STEP_PRONOUNS

    def test_pronouns_step_click(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_PRONOUNS
        # Draw to populate _button_rects
        s = _surf()
        o.draw(s)
        if o._button_rects:
            rect = o._button_rects[0]
            o._handle_click((rect.centerx, rect.centery))
            assert o.step == STEP_WELCOME

    def test_welcome_step_enter_finalizes(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_WELCOME
        o.name_text = "Player"
        o.tts_text = "Player"
        o.selected_role = "mortal"
        o.selected_title = "artisan"
        o.selected_pronouns = "they/them"
        event = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode="\r")
        o.handle_event(event)
        assert o.step == STEP_DONE
        assert o.active is False
        result = o.get_result()
        assert result is not None
        assert result["display_name"] == "Player"
        assert result["role"] == "mortal"

    def test_welcome_step_click_finalizes(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_WELCOME
        o.name_text = "Player"
        o._handle_click((400, 300))
        assert o.step == STEP_DONE

    def test_finalize_defaults(self):
        o = OnboardingOverlay(800, 600)
        o.name_text = "  Test  "
        o.tts_text = ""
        o._finalize()
        result = o.get_result()
        assert result is not None
        assert result["display_name"] == "Test"
        assert result["tts_name"] == "Test"
        assert result["role"] == "mortal"

    def test_update_hover(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        o.step = STEP_TITLE
        s = _surf()
        o.draw(s)
        if o._button_rects:
            rect = o._button_rects[1]
            o._update_hover((rect.centerx, rect.centery))
            assert o._hovered_option == 1

    def test_mousemotion_consumed(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 255
        event = pygame.event.Event(pygame.MOUSEMOTION, pos=(400, 300))
        assert o.handle_event(event) is True

    def test_draw_all_steps(self):
        o = OnboardingOverlay(800, 600)
        o.start()
        o.alpha = 200.0
        o.name_text = "Test"
        o.tts_text = "Test"
        o.selected_title = "artisan"
        s = _surf()

        for step in [
            STEP_NAME,
            STEP_PRONUNCIATION,
            STEP_TITLE,
            STEP_PRONOUNS,
            STEP_WELCOME,
        ]:
            o.step = step
            o._button_rects.clear()
            o.draw(s)

    def test_draw_hidden(self):
        o = OnboardingOverlay(800, 600)
        o.alpha = 0.0
        s = _surf()
        o.draw(s)
