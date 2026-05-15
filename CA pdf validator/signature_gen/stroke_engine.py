"""
stroke_engine.py
Core handwriting stroke simulation.
Generates bezier-curve based strokes with:
- pressure-sensitive width variation
- velocity-based tapering
- micro hand-tremor
- ink gap artifacts
- realistic pen lift simulation
"""
import numpy as np
import cv2
from typing import List, Tuple

Point = Tuple[float, float]


class StrokeEngine:
    def __init__(self, rng: np.random.Generator, style: dict):
        self.rng = rng
        self.style = style

    # ── Bezier helpers ─────────────────────────────────────────────────────────
    def cubic_bezier(self, p0, p1, p2, p3, steps=60):
        """Return points along a cubic bezier curve."""
        t = np.linspace(0, 1, steps)
        t2, t3 = t**2, t**3
        mt, mt2, mt3 = (1-t), (1-t)**2, (1-t)**3
        x = mt3*p0[0] + 3*mt2*t*p1[0] + 3*mt*t2*p2[0] + t3*p3[0]
        y = mt3*p0[1] + 3*mt2*t*p1[1] + 3*mt*t2*p2[1] + t3*p3[1]
        return list(zip(x, y))

    def quadratic_bezier(self, p0, p1, p2, steps=40):
        t = np.linspace(0, 1, steps)
        mt = 1-t
        x = mt**2*p0[0] + 2*mt*t*p1[0] + t**2*p2[0]
        y = mt**2*p0[1] + 2*mt*t*p1[1] + t**2*p2[1]
        return list(zip(x, y))

    # ── Tremor ─────────────────────────────────────────────────────────────────
    def add_tremor(self, points: List[Point], amount: float) -> List[Point]:
        """Add micro hand-tremor to a point list."""
        if amount <= 0:
            return points
        result = []
        prev_dx, prev_dy = 0.0, 0.0
        for x, y in points:
            # Correlated noise (smooth tremor, not white noise)
            dx = prev_dx * 0.7 + self.rng.normal(0, amount) * 0.3
            dy = prev_dy * 0.7 + self.rng.normal(0, amount) * 0.3
            prev_dx, prev_dy = dx, dy
            result.append((x + dx, y + dy))
        return result

    # ── Pressure profile ───────────────────────────────────────────────────────
    def pressure_profile(self, n: int, base_width: float,
                         taper_start: bool = True, taper_end: bool = True) -> np.ndarray:
        """
        Generate a pressure (width) profile for n points.
        Tapers at start/end to simulate pen pickup.
        """
        profile = np.ones(n) * base_width
        taper_len = max(1, int(n * 0.18))

        if taper_start:
            for i in range(taper_len):
                profile[i] *= (i / taper_len) ** 0.6

        if taper_end:
            for i in range(taper_len):
                profile[n - 1 - i] *= (i / taper_len) ** 0.4

        # Random pressure bumps (pen pressing harder mid-stroke)
        bumps = self.rng.integers(1, 4)
        for _ in range(bumps):
            pos = self.rng.integers(taper_len, n - taper_len) if n > 2 * taper_len else n // 2
            width = max(1, self.rng.integers(n // 8, n // 3))
            strength = self.rng.uniform(0.05, 0.18)
            x = np.arange(n)
            profile += base_width * strength * np.exp(-((x - pos)**2) / (2 * (width/2)**2))

        # Add fine-grain ink density variation
        noise = self.rng.normal(1.0, 0.06, n)
        profile *= np.clip(noise, 0.75, 1.25)

        return np.clip(profile, 0.3, base_width * 2.2)

    # ── Draw stroke ────────────────────────────────────────────────────────────
    def draw_stroke(self, canvas: np.ndarray, points: List[Point],
                    base_width: float,
                    taper_start=True, taper_end=True,
                    ink_color=(0, 0, 0),
                    gap_probability=0.0):
        """
        Draw a variable-width stroke onto canvas.
        canvas: H×W×3 uint8 BGR image
        """
        if len(points) < 2:
            return

        pts = self.add_tremor(points, self.style.get('tremor', 0.4))
        profile = self.pressure_profile(len(pts), base_width, taper_start, taper_end)

        for i in range(len(pts) - 1):
            # Random ink gap (pen slightly lifts)
            if gap_probability > 0 and self.rng.random() < gap_probability:
                continue

            x1, y1 = int(pts[i][0]),   int(pts[i][1])
            x2, y2 = int(pts[i+1][0]), int(pts[i+1][1])
            w = max(1, int(round((profile[i] + profile[i+1]) / 2)))

            # Slight color variation (ink density)
            density = self.rng.uniform(0.88, 1.0)
            c = tuple(int(v * density) for v in ink_color)

            cv2.line(canvas, (x1, y1), (x2, y2), c, w, lineType=cv2.LINE_AA)

            # Extra thick dot for pressure simulation
            if w > 2 and self.rng.random() < 0.12:
                cv2.circle(canvas, (x1, y1), max(1, w // 2),
                           tuple(int(v * 0.9) for v in ink_color), -1, lineType=cv2.LINE_AA)

    # ── Letter stroke generators ───────────────────────────────────────────────
    def make_loop(self, cx, cy, rx, ry, start_angle=0, clockwise=True) -> List[Point]:
        """Oval/loop for letters like o, e, 0, etc."""
        angles = np.linspace(start_angle, start_angle + 2*np.pi, 50)
        if not clockwise:
            angles = angles[::-1]
        x = cx + rx * np.cos(angles)
        y = cy + ry * np.sin(angles)
        return list(zip(x, y))

    def make_arch(self, x0, y0, x1, y1, arch_height: float) -> List[Point]:
        """Arch curve (for n, m, h humps)."""
        mx = (x0 + x1) / 2
        my = (y0 + y1) / 2 - arch_height
        return self.quadratic_bezier((x0, y0), (mx, my), (x1, y1), steps=35)

    def make_down_stroke(self, x, y_top, y_bot, lean: float = 0.0) -> List[Point]:
        """Vertical downstroke with optional lean."""
        steps = 30
        t = np.linspace(0, 1, steps)
        xs = x + lean * t
        ys = y_top + (y_bot - y_top) * t
        return list(zip(xs, ys))

    def connect(self, p0: Point, p1: Point, droop: float = 0.0) -> List[Point]:
        """Connecting stroke between two points with optional droop."""
        cx = (p0[0] + p1[0]) / 2
        cy = (p0[1] + p1[1]) / 2 + droop
        return self.quadratic_bezier(p0, (cx, cy), p1, steps=25)