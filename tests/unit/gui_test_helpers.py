import pygame
import pygame.freetype


def _surf(w: int = 800, h: int = 600) -> pygame.Surface:
    return pygame.Surface((w, h), pygame.SRCALPHA)


def _font() -> pygame.freetype.Font:
    return pygame.freetype.SysFont("arial", 14)
