"""Floating golden ember particle system for ambient background effect."""

from __future__ import annotations

import random

import pygame

from .constants import H, W


class Ember:
    """Single golden ember particle drifting upward."""

    __slots__ = ("x", "y", "vx", "vy", "radius", "alpha", "decay", "color")

    x: float
    y: float
    vx: float
    vy: float
    radius: float
    alpha: float
    decay: float
    color: tuple[int, int, int]

    def __init__(self) -> None:
        self.x = 0
        self.y = 0
        self.vx = 0
        self.vy = 0
        self.radius = 0
        self.alpha = 0
        self.decay = 0
        self.color = (0, 0, 0)
        self._reset(W, H)

    def _reset(self, max_w: int, max_h: int) -> None:
        self.x = random.uniform(0, max_w)
        self.y = random.uniform(0, max_h)
        self.vx = random.uniform(-0.25, 0.25)
        self.vy = random.uniform(-0.6, -0.15)
        self.radius = random.uniform(1.0, 2.5)
        self.alpha = random.uniform(60, 180)
        self.decay = random.uniform(0.15, 0.5)
        r, g = random.randint(200, 255), random.randint(140, 200)
        self.color = (r, g, 20)

    def update(self, dt: float) -> bool:
        """Update position; return False when dead."""
        self.x += self.vx * dt * 60
        self.y += self.vy * dt * 60
        self.alpha -= self.decay * dt * 60
        return self.alpha > 0

    def draw(self, surf: pygame.Surface) -> None:
        if self.alpha <= 0:
            return
        s = pygame.Surface((int(self.radius * 2 + 2), int(self.radius * 2 + 2)), pygame.SRCALPHA)
        pygame.draw.circle(
            s,
            (*self.color, int(self.alpha)),
            (int(self.radius + 1), int(self.radius + 1)),
            max(1, int(self.radius)),
        )
        surf.blit(s, (int(self.x - self.radius), int(self.y - self.radius)))


class ParticleSystem:
    MAX = 120

    def __init__(self) -> None:
        self._embers: list[Ember] = [Ember() for _ in range(self.MAX)]

    def update(self, dt: float, screen_w: int = W, screen_h: int = H) -> None:
        for e in self._embers:
            if not e.update(dt):
                e._reset(screen_w, screen_h)

    def draw(self, surf: pygame.Surface) -> None:
        for e in self._embers:
            e.draw(surf)
