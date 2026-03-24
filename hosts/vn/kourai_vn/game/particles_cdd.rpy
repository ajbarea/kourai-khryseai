init python:
    import random
    import math

    class _Ember:
        def __init__(self, w, h):
            self.max_w = w
            self.max_h = h
            self.reset(w, h, initial=True)
            
        def reset(self, max_w, max_h, initial=False):
            self.max_w = max_w
            self.max_h = max_h
            self.x = random.uniform(0, max_w)
            
            # 3 depth layers for parallax:
            # 1: tiny/bg, 2: mid, 3: foreground/large
            roll = random.uniform(0, 100)
            if roll < 50:
                self.layer = 1
            elif roll < 85:
                self.layer = 2
            else:
                self.layer = 3
            
            if self.layer == 1:
                self.radius = random.uniform(1.0, 2.0)
                self.vy = random.uniform(-0.8, -0.4)
                self.max_a = random.uniform(60, 120)
            elif self.layer == 2:
                self.radius = random.uniform(2.5, 4.0)
                self.vy = random.uniform(-1.5, -0.8)
                self.max_a = random.uniform(120, 200)
            else:
                self.radius = random.uniform(4.5, 7.0)
                self.vy = random.uniform(-2.5, -1.5)
                self.max_a = random.uniform(180, 255)
                
            self.vx = random.uniform(-0.2, 0.2)
            
            # Sine wave drift
            self.drift_speed = random.uniform(0.5, 2.0)
            self.drift_amp = random.uniform(0.2, 0.8) * self.layer
            self.seed = random.uniform(0, math.pi * 2)
            
            self.life = 0.0
            
            # Color: Gold / Orange / Ember
            self.r = random.randint(230, 255)
            self.g = random.randint(140, 210)
            self.b = random.randint(20, 50)
            
            if initial:
                self.y = random.uniform(0, max_h)
                self.alpha = random.uniform(0, self.max_a)
            else:
                self.y = random.uniform(max_h, max_h + 50)
                self.alpha = 0.0
            
        def update(self, dt):
            self.life += dt
            # Sine wave horizontal movement
            current_vx = self.vx + math.sin(self.life * self.drift_speed + self.seed) * self.drift_amp
            
            self.x += current_vx * dt * 60
            self.y += self.vy * dt * 60
            
            # Fade in early, stay solid, fade out at top (or randomly die depending on how long it's active)
            if self.y > self.max_h - 150:
                # fading in as they spawn at bottom
                self.alpha = min(self.max_a, self.alpha + dt * 100)
            elif self.y < 200:
                # fading out as they reach the top 200 pixels
                self.alpha -= self.max_a * dt * 0.5
            else:
                # random flicker decay
                self.alpha -= random.uniform(-10.0, 10.0) * dt * 60
                
            self.alpha = max(0, min(self.max_a, self.alpha))
            
            if self.y < -20 or (self.alpha <= 0 and self.y < self.max_h - 150):
                self.reset(self.max_w, self.max_h, initial=False)

    class EmberSystem(renpy.Displayable):
        def __init__(self, count=200, **kwargs):
            super(EmberSystem, self).__init__(**kwargs)
            self.count = count
            self.embers = []
            self.last_st = None
            
        def render(self, width, height, st, at):
            w = width if width > 0 else config.screen_width
            h = height if height > 0 else config.screen_height
            render = renpy.Render(w, h)
            canvas = render.canvas()
            
            if not self.embers:
                for _ in range(self.count):
                    self.embers.append(_Ember(w, h))
                    
            if self.last_st is None:
                dt = 0.0
            else:
                dt = max(st - self.last_st, 0.0)
            self.last_st = st
            
            for e in self.embers:
                e.update(dt)
                if e.alpha > 0:
                    a = int(e.alpha)
                    
                    # Draw optional ambient glow for foreground embers (layer 3)
                    if e.layer == 3 and a > 50:
                        glow_a = int(a * 0.25)
                        glow_r = e.r
                        glow_g = max(0, e.g - 60) # more red/orange glow
                        glow_b = 0
                        canvas.circle((glow_r, glow_g, glow_b, glow_a), (int(e.x), int(e.y)), e.radius * 2.8)
                        
                    canvas.circle((e.r, e.g, e.b, a), (int(e.x), int(e.y)), e.radius)
                    
            renpy.redraw(self, 0)
            return render

image ember_particles = EmberSystem()
