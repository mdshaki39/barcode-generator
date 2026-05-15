"""
flourish_engine.py
Generates realistic signature flourishes:
- underline sweeps
- ending loop strokes
- initial caps flourish
- crossing strokes (t-bar, f-bar)
- natural signature endings
"""
import numpy as np
from typing import List, Tuple
from stroke_engine import StrokeEngine

Point = Tuple[float, float]


class FlourishEngine:
    def __init__(self, stroke: StrokeEngine, rng: np.random.Generator):
        self.stroke = stroke
        self.rng = rng

    def underline_sweep(self, canvas, x_start, x_end, y_base,
                        base_width=1.8, style='wave'):
        """
        Draw a realistic underline sweep beneath the signature.
        Styles: 'wave', 'straight', 'uptick', 'loop_end'
        """
        if style == 'wave':
            # Slight wave underline
            points = []
            n = 80
            for i in range(n):
                t = i / (n-1)
                x = x_start + (x_end - x_start) * t
                wave = np.sin(t * np.pi * 2.5) * self.rng.uniform(1.5, 3.5)
                y = y_base + wave
                points.append((x, y))
            self.stroke.draw_stroke(canvas, points, base_width,
                                    taper_start=True, taper_end=True)

        elif style == 'straight':
            # Slightly curved straight line
            mid_y = y_base + self.rng.uniform(-2, 2)
            p0 = (x_start, y_base + self.rng.uniform(-1, 1))
            p1 = ((x_start + x_end) / 2, mid_y)
            p2 = (x_end, y_base + self.rng.uniform(-1, 1))
            points = self.stroke.quadratic_bezier(p0, p1, p2, steps=60)
            self.stroke.draw_stroke(canvas, points, base_width,
                                    taper_start=True, taper_end=True)

        elif style == 'uptick':
            # Underline ending with upward tick
            p0 = (x_start, y_base)
            p1 = (x_end - 10, y_base + self.rng.uniform(-1, 2))
            p2 = (x_end,      y_base)
            p3 = (x_end + 8,  y_base - 12)
            points = self.stroke.cubic_bezier(p0, p1, p2, p3, steps=70)
            self.stroke.draw_stroke(canvas, points, base_width,
                                    taper_start=True, taper_end=True)

        elif style == 'loop_end':
            # Underline ending in small loop
            p0 = (x_start, y_base)
            p1 = (x_end - 15, y_base + 2)
            p2 = (x_end,      y_base)
            line = self.stroke.quadratic_bezier(p0, p1, p2, steps=50)
            # Small ending loop
            loop_r = self.rng.uniform(6, 10)
            loop = self.stroke.make_loop(x_end + loop_r, y_base - loop_r/2,
                                         loop_r, loop_r * 0.7,
                                         start_angle=np.pi)
            self.stroke.draw_stroke(canvas, line + loop, base_width,
                                    taper_start=True, taper_end=True)

    def ending_stroke(self, canvas, x, y, direction='right', base_width=1.6):
        """Natural ending stroke after last letter."""
        if direction == 'right':
            length = self.rng.uniform(20, 45)
            droop  = self.rng.uniform(3, 12)
            p0 = (x, y)
            p1 = (x + length * 0.4, y + droop * 0.3)
            p2 = (x + length * 0.7, y + droop * 0.7)
            p3 = (x + length, y + droop)
            pts = self.stroke.cubic_bezier(p0, p1, p2, p3, steps=50)
            self.stroke.draw_stroke(canvas, pts, base_width,
                                    taper_start=False, taper_end=True)

        elif direction == 'loop_back':
            # Loop back upward
            length = self.rng.uniform(25, 50)
            p0 = (x, y)
            p1 = (x + length * 0.6, y + 8)
            p2 = (x + length,       y + 3)
            p3 = (x + length * 0.7, y - 15)
            pts = self.stroke.cubic_bezier(p0, p1, p2, p3, steps=55)
            self.stroke.draw_stroke(canvas, pts, base_width,
                                    taper_start=False, taper_end=True)

        elif direction == 'curl_down':
            length = self.rng.uniform(20, 40)
            p0 = (x, y)
            p1 = (x + length * 0.5, y + 5)
            p2 = (x + length,       y + 18)
            p3 = (x + length - 8,   y + 28)
            pts = self.stroke.cubic_bezier(p0, p1, p2, p3, steps=50)
            self.stroke.draw_stroke(canvas, pts, base_width,
                                    taper_start=False, taper_end=True)

    def initial_flourish(self, canvas, x, y, base_width=2.2):
        """Upward flourish before first capital letter."""
        kind = self.rng.integers(0, 3)
        if kind == 0:
            # Rising loop entry
            p0 = (x - 18, y + 15)
            p1 = (x - 22, y - 8)
            p2 = (x - 8,  y - 18)
            p3 = (x,      y)
            pts = self.stroke.cubic_bezier(p0, p1, p2, p3, steps=45)
            self.stroke.draw_stroke(canvas, pts, base_width,
                                    taper_start=True, taper_end=False,
                                    gap_probability=0.02)
        elif kind == 1:
            # Simple lead-in swash
            p0 = (x - 20, y + 8)
            p1 = (x - 10, y - 5)
            p2 = (x,      y)
            pts = self.stroke.quadratic_bezier(p0, p1, p2, steps=35)
            self.stroke.draw_stroke(canvas, pts, base_width * 0.7,
                                    taper_start=True, taper_end=False)
        else:
            # Overhead loop
            p0 = (x - 5,  y)
            p1 = (x - 20, y - 20)
            p2 = (x + 5,  y - 25)
            p3 = (x + 2,  y)
            pts = self.stroke.cubic_bezier(p0, p1, p2, p3, steps=45)
            self.stroke.draw_stroke(canvas, pts, base_width * 0.8,
                                    taper_start=True, taper_end=False)

    def t_crossbar(self, canvas, x_center, y, width, base_width=1.4):
        """Realistic t-bar crossing stroke."""
        x0 = x_center - width / 2 + self.rng.uniform(-3, 3)
        x1 = x_center + width / 2 + self.rng.uniform(-3, 3)
        y0 = y + self.rng.uniform(-2, 2)
        y1 = y + self.rng.uniform(-2, 2)
        mid_y = (y0 + y1) / 2 + self.rng.uniform(-2, 2)
        pts = self.stroke.quadratic_bezier((x0, y0), ((x0+x1)/2, mid_y), (x1, y1))
        self.stroke.draw_stroke(canvas, pts, base_width,
                                taper_start=True, taper_end=True)