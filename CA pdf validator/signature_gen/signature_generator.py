"""
signature_generator.py — v5
Reference-quality realistic signatures.

Key improvements:
- Large initial capital flourish (loop, swash, or crossing stroke)
- Continuous connected cursive flow
- Long sweeping ending stroke
- Pressure-variable thick→thin strokes
- Natural baseline drift
- Style-specific visual DNA
"""
import numpy as np
import cv2
from typing import Optional, List, Tuple
from stroke_engine import StrokeEngine
from flourish_engine import FlourishEngine

# ── Style definitions ──────────────────────────────────────────────────────────
STYLES = {
    "Executive": {
        "slant": -0.12, "chaos": 0.12, "compress": 0.78,
        "h_scale": 1.05, "width": 2.6, "gap": 0.52,
        "flourish": True, "ending": "sweep_long", "initial": "loop_cross",
    },
    "Fast Scribble": {
        "slant": -0.32, "chaos": 0.88, "compress": 0.40,
        "h_scale": 0.70, "width": 2.0, "gap": 0.22,
        "flourish": False, "ending": "flat_dash", "initial": "slash",
    },
    "Elegant Legal": {
        "slant": -0.06, "chaos": 0.05, "compress": 0.92,
        "h_scale": 1.28, "width": 2.3, "gap": 0.68,
        "flourish": True, "ending": "loop_below", "initial": "tall_loop",
    },
    "Doctor Style": {
        "slant": -0.38, "chaos": 0.95, "compress": 0.32,
        "h_scale": 0.58, "width": 2.5, "gap": 0.16,
        "flourish": False, "ending": "flat_dash", "initial": "slash",
    },
    "Minimal Initial": {
        "slant": -0.08, "chaos": 0.25, "compress": 0.60,
        "h_scale": 0.90, "width": 2.1, "gap": 0.42,
        "flourish": True, "ending": "uptick", "initial": "simple",
    },
    "Heavy Cursive": {
        "slant": -0.18, "chaos": 0.32, "compress": 0.74,
        "h_scale": 1.12, "width": 4.2, "gap": 0.52,
        "flourish": True, "ending": "sweep_long", "initial": "loop_cross",
    },
    "Clear Print": {
        "slant": -0.02, "chaos": 0.00, "compress": 0.88,
        "h_scale": 1.20, "width": 3.0, "gap": 0.65,
        "flourish": True, "ending": "uptick", "initial": "simple",
    },
}
STYLE_NAMES = list(STYLES.keys())

# ── Name form selection ────────────────────────────────────────────────────────
def _pick_name(first, last, rng, force_full=False):
    first = (first or "").strip().upper()
    last  = (last  or "").strip().upper()
    if not first and not last: return "SIGN"
    if not first: return last
    if not last:  return first
    if force_full: return first + " " + last
    c = int(rng.integers(0, 4))
    if c == 0: return first
    elif c == 1: return last
    elif c == 2: return first + " " + last
    else: return first[0] + last


class SignatureGenerator:
    W, H   = 680, 260
    MARGIN = 60

    def __init__(self, style_name=None, randomness=0.5, intensity=0.5, seed=None):
        self.rng = np.random.default_rng(seed)
        if style_name not in STYLES:
            style_name = STYLE_NAMES[int(self.rng.integers(0, len(STYLE_NAMES)))]
        self.style_name = style_name
        self._s = STYLES[style_name]
        self.randomness = float(np.clip(randomness, 0, 1))
        self.intensity  = float(np.clip(intensity,  0, 1))

        # Derived params
        s = self._s
        tremor_base = {"Executive":0.08,"Fast Scribble":0.65,"Elegant Legal":0.04,
                       "Doctor Style":1.40,"Minimal Initial":0.18,"Heavy Cursive":0.28,
                       "Clear Print":0.03}.get(style_name, 0.15)
        self.tremor     = tremor_base + self.intensity * 1.6 + self.randomness * 0.5
        self.chaos      = s["chaos"] * (0.35 + self.randomness * 0.65)
        self.base_width = s["width"] * (0.45 + self.intensity * 1.1)
        self.slant      = s["slant"] + self.rng.uniform(-0.04, 0.04) * self.randomness
        self.compress   = s["compress"]
        self.gap        = s["gap"]
        self.hscale     = s["h_scale"]

        self.stroke    = StrokeEngine(self.rng, {"tremor": self.tremor})
        self.fl        = FlourishEngine(self.stroke, self.rng)

    # ── Canvas ─────────────────────────────────────────────────────────────────
    def _canvas(self, paper=False):
        c = np.ones((self.H, self.W, 3), dtype=np.uint8) * 255
        if paper:
            n = self.rng.integers(0, int(6 + self.randomness * 20), (self.H, self.W, 3), dtype=np.uint8)
            c = np.clip(c.astype(np.int16) - n, 218, 255).astype(np.uint8)
            for _ in range(int(self.randomness * 8)):
                x0,y0 = int(self.rng.integers(0,self.W)), int(self.rng.integers(0,self.H))
                cv2.line(c,(x0,y0),(x0+int(self.rng.integers(-60,60)),y0+int(self.rng.integers(-3,3))),(215,210,205),1,cv2.LINE_AA)
        return c

    def _ink(self):
        base = max(0, int(38 - self.intensity * 34))
        return (max(0,base+int(self.rng.integers(-4,8))),
                max(0,base+int(self.rng.integers(-3,5))),
                max(0,base+int(self.rng.integers(-2,12))))

    # ── Initial capital flourish ───────────────────────────────────────────────
    def _draw_initial(self, canvas, cx, cy, scale, bw, ink):
        """Draw a large realistic initial capital flourish."""
        kind = self._s["initial"]
        rng  = self.rng

        if kind == "loop_cross":
            # Big loop then cross stroke (like image 1 'P' or 'J')
            r = rng.uniform(18, 30) * scale
            # Upward loop
            loop_pts = []
            for a in np.linspace(np.pi*0.5, np.pi*2.5, 60):
                loop_pts.append((cx + r*0.7*np.cos(a), cy - r + r*np.sin(a)))
            self.stroke.draw_stroke(canvas, loop_pts, bw*1.1, ink_color=ink,
                                    taper_start=True, taper_end=False)
            # Diagonal cross through the loop
            p0 = (cx - r*0.5, cy - r*1.6)
            p1 = (cx + r*0.4, cy + r*0.3)
            cross = self.stroke.cubic_bezier(
                p0, (p0[0]+r*0.2, p0[1]+r*0.5),
                (p1[0]-r*0.2, p1[1]-r*0.5), p1)
            self.stroke.draw_stroke(canvas, cross, bw*0.7, ink_color=ink,
                                    taper_start=True, taper_end=True)
            return cx + r*0.6

        elif kind == "tall_loop":
            # Tall elegant loop upward
            h = rng.uniform(35, 55) * scale
            w = rng.uniform(14, 22) * scale
            pts = self.stroke.cubic_bezier(
                (cx, cy),
                (cx - w*0.8, cy - h*0.6),
                (cx - w*0.2, cy - h*1.1),
                (cx + w*0.5, cy - h*0.85))
            pts2 = self.stroke.cubic_bezier(
                (cx + w*0.5, cy - h*0.85),
                (cx + w*1.1, cy - h*0.6),
                (cx + w*0.8, cy - h*0.1),
                (cx + w*0.4, cy))
            self.stroke.draw_stroke(canvas, pts + pts2, bw*1.0, ink_color=ink,
                                    taper_start=True, taper_end=False)
            return cx + w*0.5

        elif kind == "slash":
            # Fast diagonal slash (doctor/scribble style)
            h = rng.uniform(28, 45) * scale
            w = rng.uniform(12, 20) * scale
            pts = self.stroke.cubic_bezier(
                (cx - w*0.3, cy - h*0.9),
                (cx - w*0.1, cy - h*0.5),
                (cx + w*0.2, cy - h*0.2),
                (cx + w*0.5, cy))
            self.stroke.draw_stroke(canvas, pts, bw*1.2, ink_color=ink,
                                    taper_start=True, taper_end=False)
            return cx + w*0.4

        else:  # simple
            # Simple capital-like upstroke
            h = rng.uniform(22, 35) * scale
            pts = self.stroke.cubic_bezier(
                (cx, cy),
                (cx - 6*scale, cy - h*0.5),
                (cx - 2*scale, cy - h*0.9),
                (cx + 4*scale, cy - h))
            pts2 = self.stroke.cubic_bezier(
                (cx + 4*scale, cy - h),
                (cx + 8*scale, cy - h*0.8),
                (cx + 6*scale, cy - h*0.3),
                (cx + 8*scale, cy))
            self.stroke.draw_stroke(canvas, pts + pts2, bw, ink_color=ink,
                                    taper_start=True, taper_end=False)
            return cx + 9*scale

    # ── Ending strokes (long sweeping) ─────────────────────────────────────────
    def _draw_ending(self, canvas, x, y, scale, bw, ink):
        kind = self._s["ending"]
        rng  = self.rng

        if kind == "sweep_long":
            # Long rightward sweep then curves back — like image 1,2
            length = rng.uniform(60, 110) * scale
            # First: sweep right and slightly down
            p0 = (x, y)
            p1 = (x + length*0.35, y + rng.uniform(4, 12)*scale)
            p2 = (x + length*0.70, y + rng.uniform(6, 18)*scale)
            p3 = (x + length,      y + rng.uniform(2,  8)*scale)
            pts = self.stroke.cubic_bezier(p0, p1, p2, p3, steps=80)
            self.stroke.draw_stroke(canvas, pts, bw*0.65, ink_color=ink,
                                    taper_start=False, taper_end=True)
            # Optional: loop back underneath
            if rng.random() < 0.6:
                loop_w = rng.uniform(40, 70) * scale
                lp0 = (x + length*0.2, y + rng.uniform(12,22)*scale)
                lp1 = (x + length*0.6, y + rng.uniform(16,28)*scale)
                lp2 = (x + length*0.9, y + rng.uniform(10,20)*scale)
                lp3 = (x + length*1.05, y + rng.uniform(4,12)*scale)
                loop_pts = self.stroke.cubic_bezier(lp0, lp1, lp2, lp3, steps=60)
                self.stroke.draw_stroke(canvas, loop_pts, bw*0.45, ink_color=ink,
                                        taper_start=True, taper_end=True)

        elif kind == "loop_below":
            # Big oval loop below (like elegant style)
            rx = rng.uniform(35, 55) * scale
            ry = rng.uniform(12, 20) * scale
            cy2 = y + ry + rng.uniform(4, 10)*scale
            angles = np.linspace(np.pi*1.1, np.pi*3.1, 70)
            pts = [(x - rx + rx*1.1*np.cos(a), cy2 + ry*np.sin(a)) for a in angles]
            self.stroke.draw_stroke(canvas, pts, bw*0.55, ink_color=ink,
                                    taper_start=True, taper_end=True)

        elif kind == "flat_dash":
            # Quick flat rightward dash (fast/doctor style)
            length = rng.uniform(25, 50) * scale
            p0 = (x, y)
            p1 = (x+length*0.5, y+rng.uniform(-3,5)*scale)
            p2 = (x+length, y+rng.uniform(-2,4)*scale)
            pts = self.stroke.quadratic_bezier(p0, p1, p2, steps=35)
            self.stroke.draw_stroke(canvas, pts, bw*0.55, ink_color=ink,
                                    taper_start=False, taper_end=True)

        elif kind == "uptick":
            length = rng.uniform(20, 40) * scale
            p0 = (x, y)
            p1 = (x+length*0.6, y+rng.uniform(2,8)*scale)
            p2 = (x+length, y-rng.uniform(5,14)*scale)
            pts = self.stroke.quadratic_bezier(p0, p1, p2, steps=40)
            self.stroke.draw_stroke(canvas, pts, bw*0.6, ink_color=ink,
                                    taper_start=False, taper_end=True)

    # ── Letter drawing ─────────────────────────────────────────────────────────
    def _draw_letter(self, canvas, char, cx, cy, scale, bw, ink, is_first):
        char = char.upper()
        cy  += self.rng.uniform(-2, 2) * self.randomness

        if self.style_name == "Clear Print":
            pass
        elif not is_first and self.rng.random() < self.chaos:
            return self._blob(canvas, cx, cy, scale, bw, ink)

        if char not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            return self._blob(canvas, cx, cy, scale, bw, ink)

        fn = getattr(self, f'_L_{char}', self._blob)
        nx = fn(canvas, cx, cy, scale, bw, ink)
        return nx if nx else cx + 24*scale*self.compress

    def _blob(self, canvas, cx, cy, scale, bw, ink):
        """Style-specific abstract blob."""
        w = 20*scale*self.compress
        s = self.style_name

        if s in ("Doctor Style", "Fast Scribble"):
            # Jagged fast stroke
            n = int(self.rng.integers(3, 6))
            pts = [(cx + i*w/n + self.rng.uniform(-5,5)*scale,
                    cy + self.rng.uniform(-10,10)*scale) for i in range(n)]
            self.stroke.draw_stroke(canvas, pts, bw, ink_color=ink, gap_probability=0.04)
            return cx + w

        if s == "Heavy Cursive":
            r = self.rng.uniform(6, 14)*scale
            self.stroke.draw_stroke(canvas, self.stroke.make_loop(cx+r, cy-r*0.3, r, r*0.75),
                                    bw, ink_color=ink)
            return cx + w

        k = int(self.rng.integers(0, 4))
        if k == 0:
            r = self.rng.uniform(5,9)*scale
            self.stroke.draw_stroke(canvas, self.stroke.make_loop(cx+r,cy,r,r*.6),
                                    bw, ink_color=ink, gap_probability=0.01)
        elif k == 1:
            self.stroke.draw_stroke(canvas,
                self.stroke.make_arch(cx,cy,cx+w,cy,self.rng.uniform(8,16)*scale), bw, ink_color=ink)
        elif k == 2:
            pts=self.stroke.cubic_bezier((cx,cy+4),(cx+w*.3,cy-10*scale),(cx+w*.7,cy+10*scale),(cx+w,cy-4))
            self.stroke.draw_stroke(canvas, pts, bw, ink_color=ink)
        else:
            mid=cx+w/2
            self.stroke.draw_stroke(canvas,
                self.stroke.make_arch(cx,cy,mid,cy,self.rng.uniform(7,13)*scale)+
                self.stroke.make_arch(mid,cy,cx+w,cy,self.rng.uniform(6,12)*scale), bw, ink_color=ink)
        return cx + w

    # ── Letters ───────────────────────────────────────────────────────────────
    def _h(self): return self.hscale
    def _c(self): return self.compress

    def _L_A(self,cv,cx,cy,sc,bw,ink):
        h=32*sc*self._h();w=24*sc
        p=self.stroke.cubic_bezier((cx,cy),(cx+w*.2,cy-h*.6),(cx+w*.5,cy-h),(cx+w*.5,cy-h))
        q=self.stroke.quadratic_bezier((cx+w*.5,cy-h),(cx+w*.8,cy-h*.5),(cx+w,cy))
        self.stroke.draw_stroke(cv,p+q,bw,ink_color=ink)
        self.fl.t_crossbar(cv,cx+w*.5,cy-h*.44,w*.65*self.rng.uniform(.8,1.2),bw*.72)
        return cx+w*self._c()
    def _L_B(self,cv,cx,cy,sc,bw,ink):
        h=30*sc*self._h();w=22*sc
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx,cy-h,cy,lean=2*sc),bw,ink_color=ink,taper_start=False)
        self.stroke.draw_stroke(cv,self.stroke.make_arch(cx,cy-h,cx+w*.88,cy-h*.5,-h*.23),bw*.88,ink_color=ink)
        self.stroke.draw_stroke(cv,self.stroke.make_arch(cx,cy-h*.5,cx+w,cy,-h*.28),bw*.92,ink_color=ink)
        return cx+w*self._c()
    def _L_C(self,cv,cx,cy,sc,bw,ink):
        h=26*sc*self._h();w=22*sc
        a=np.linspace(np.pi*.22,np.pi*1.88,58)
        self.stroke.draw_stroke(cv,[(cx+w/2+w/2*np.cos(v),cy-h/2+h/2*np.sin(v)) for v in a],bw,ink_color=ink)
        return cx+w*.72*self._c()
    def _L_D(self,cv,cx,cy,sc,bw,ink):
        h=30*sc*self._h();w=24*sc
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx,cy-h,cy),bw,ink_color=ink,taper_start=False)
        self.stroke.draw_stroke(cv,self.stroke.quadratic_bezier((cx,cy-h),(cx+w*1.25,cy-h*.5),(cx,cy)),bw*.92,ink_color=ink)
        return cx+w*self._c()
    def _L_E(self,cv,cx,cy,sc,bw,ink):
        h=28*sc*self._h();w=20*sc
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx,cy-h,cy),bw,ink_color=ink,taper_start=False)
        for by,bw2 in [(cy-h,w),(cy-h*.5,w*.72),(cy,w*.88)]:
            self.stroke.draw_stroke(cv,self.stroke.connect((cx,by+self.rng.uniform(-1.5,1.5)),(cx+bw2,by+self.rng.uniform(-1.5,1.5)),self.rng.uniform(-1,2)),bw*.72,ink_color=ink)
        return cx+w*self._c()
    def _L_F(self,cv,cx,cy,sc,bw,ink):
        h=30*sc*self._h();w=20*sc
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx,cy-h,cy),bw,ink_color=ink,taper_start=False)
        self.stroke.draw_stroke(cv,self.stroke.connect((cx,cy-h),(cx+w,cy-h+self.rng.uniform(-2,2))),bw*.72,ink_color=ink)
        self.stroke.draw_stroke(cv,self.stroke.connect((cx,cy-h*.52),(cx+w*.82,cy-h*.52+self.rng.uniform(-2,2))),bw*.68,ink_color=ink)
        return cx+w*self._c()
    def _L_G(self,cv,cx,cy,sc,bw,ink):
        h=26*sc*self._h();w=22*sc
        a=np.linspace(np.pi*.1,np.pi*1.85,58)
        self.stroke.draw_stroke(cv,[(cx+w/2+w/2*np.cos(v),cy-h/2+h/2*np.sin(v)) for v in a],bw,ink_color=ink)
        self.stroke.draw_stroke(cv,self.stroke.connect((cx+w*.5,cy-h*.5),(cx+w*.92,cy-h*.5+self.rng.uniform(-2,2))),bw*.7,ink_color=ink)
        return cx+w*self._c()
    def _L_H(self,cv,cx,cy,sc,bw,ink):
        h=30*sc*self._h();w=22*sc
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx,cy-h,cy),bw,ink_color=ink,taper_start=False)
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx+w,cy-h,cy,lean=-1*sc),bw,ink_color=ink,taper_start=False)
        self.stroke.draw_stroke(cv,self.stroke.connect((cx,cy-h*.52+self.rng.uniform(-2,2)),(cx+w,cy-h*.48+self.rng.uniform(-2,2)),self.rng.uniform(-3,3)),bw*.78,ink_color=ink)
        return cx+w*self._c()
    def _L_I(self,cv,cx,cy,sc,bw,ink):
        h=28*sc*self._h();w=14*sc
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx+w*.5,cy-h,cy,lean=self.rng.uniform(0,3)*sc),bw,ink_color=ink)
        return cx+w*self._c()
    def _L_J(self,cv,cx,cy,sc,bw,ink):
        h=30*sc*self._h();w=18*sc
        self.stroke.draw_stroke(cv,self.stroke.cubic_bezier((cx+w*.5,cy-h),(cx+w*.6,cy-h*.08),(cx+w*.3,cy+h*.14),(cx,cy+h*.06)),bw,ink_color=ink)
        return cx+w*self._c()
    def _L_K(self,cv,cx,cy,sc,bw,ink):
        h=30*sc*self._h();w=22*sc
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx,cy-h,cy),bw,ink_color=ink,taper_start=False)
        self.stroke.draw_stroke(cv,self.stroke.quadratic_bezier((cx,cy-h*.48),(cx+w*.55,cy-h*.75),(cx+w,cy-h)),bw*.82,ink_color=ink)
        self.stroke.draw_stroke(cv,self.stroke.quadratic_bezier((cx,cy-h*.48),(cx+w*.55,cy-h*.22),(cx+w,cy)),bw*.82,ink_color=ink)
        return cx+w*self._c()
    def _L_L(self,cv,cx,cy,sc,bw,ink):
        h=32*sc*self._h();w=18*sc
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx+w*.1,cy-h,cy,lean=1),bw,ink_color=ink,taper_start=False)
        self.stroke.draw_stroke(cv,self.stroke.quadratic_bezier((cx,cy),(cx+w*.6,cy+2),(cx+w,cy)),bw*.75,ink_color=ink)
        return cx+w*self._c()
    def _L_M(self,cv,cx,cy,sc,bw,ink):
        h=28*sc*self._h();w=30*sc
        seg=(self.stroke.make_down_stroke(cx,cy,cy-h*.88)+
             self.stroke.cubic_bezier((cx,cy-h*.88),(cx+w*.2,cy-h*1.12),(cx+w*.4,cy-h),(cx+w*.5,cy-h*.52))+
             self.stroke.cubic_bezier((cx+w*.5,cy-h*.52),(cx+w*.6,cy-h),(cx+w*.8,cy-h*1.12),(cx+w,cy-h*.88))+
             self.stroke.make_down_stroke(cx+w,cy-h*.88,cy))
        self.stroke.draw_stroke(cv,seg,bw,ink_color=ink)
        return cx+w*self._c()
    def _L_N(self,cv,cx,cy,sc,bw,ink):
        h=28*sc*self._h();w=24*sc
        seg=(self.stroke.make_down_stroke(cx,cy,cy-h*.92)+
             self.stroke.cubic_bezier((cx,cy-h*.92),(cx+w*.3,cy-h*.38),(cx+w*.7,cy-h*.62),(cx+w,cy))+
             list(reversed(self.stroke.make_down_stroke(cx+w,cy,cy-h*.92))))
        self.stroke.draw_stroke(cv,seg,bw,ink_color=ink)
        return cx+w*self._c()
    def _L_O(self,cv,cx,cy,sc,bw,ink):
        h=26*sc*self._h();w=22*sc
        self.stroke.draw_stroke(cv,self.stroke.make_loop(cx+w/2,cy-h/2,w/2,h/2,start_angle=np.pi*.08),bw,ink_color=ink)
        return cx+w*self._c()
    def _L_P(self,cv,cx,cy,sc,bw,ink):
        h=30*sc*self._h();w=20*sc
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx,cy-h,cy),bw,ink_color=ink,taper_start=False)
        self.stroke.draw_stroke(cv,self.stroke.make_arch(cx,cy-h,cx+w*.9,cy-h*.5,-h*.28),bw*.88,ink_color=ink)
        return cx+w*self._c()
    def _L_R(self,cv,cx,cy,sc,bw,ink):
        h=29*sc*self._h();w=22*sc
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx,cy-h,cy),bw,ink_color=ink,taper_start=False)
        self.stroke.draw_stroke(cv,self.stroke.make_arch(cx,cy-h,cx+w*.88,cy-h*.5,-h*.27),bw*.86,ink_color=ink)
        self.stroke.draw_stroke(cv,self.stroke.cubic_bezier((cx+w*.52,cy-h*.5),(cx+w*.72,cy-h*.24),(cx+w,cy-h*.04),(cx+w+3,cy)),bw*.82,ink_color=ink)
        return cx+w*self._c()
    def _L_S(self,cv,cx,cy,sc,bw,ink):
        h=26*sc*self._h();w=20*sc
        top=self.stroke.cubic_bezier((cx+w*.88,cy-h*.9),(cx+w*.18,cy-h*1.06),(cx,cy-h*.72),(cx+w*.42,cy-h*.5))
        bot=self.stroke.cubic_bezier((cx+w*.42,cy-h*.5),(cx+w,cy-h*.3),(cx+w*.82,cy-h*.04),(cx+w*.14,cy))
        self.stroke.draw_stroke(cv,top+bot,bw,ink_color=ink)
        return cx+w*self._c()
    def _L_T(self,cv,cx,cy,sc,bw,ink):
        h=30*sc*self._h();w=24*sc
        self.stroke.draw_stroke(cv,self.stroke.make_down_stroke(cx+w*.5,cy-h,cy,lean=self.rng.uniform(0,2)),bw,ink_color=ink,taper_start=False)
        self.fl.t_crossbar(cv,cx+w*.5,cy-h*.9,w*1.1,bw*.82)
        return cx+w*self._c()
    def _L_U(self,cv,cx,cy,sc,bw,ink):
        h=26*sc*self._h();w=20*sc
        self.stroke.draw_stroke(cv,self.stroke.cubic_bezier((cx,cy-h),(cx,cy+h*.1),(cx+w,cy+h*.1),(cx+w,cy-h)),bw,ink_color=ink)
        return cx+w*self._c()
    def _L_V(self,cv,cx,cy,sc,bw,ink):
        h=26*sc*self._h();w=22*sc;mid=cx+w/2
        pts=(self.stroke.cubic_bezier((cx,cy-h),(cx+w*.35,cy-h*.1),(mid-1,cy+2),(mid,cy))+
             self.stroke.cubic_bezier((mid,cy),(mid+1,cy+2),(cx+w*.65,cy-h*.1),(cx+w,cy-h)))
        self.stroke.draw_stroke(cv,pts,bw,ink_color=ink)
        return cx+w*self._c()
    def _L_W(self,cv,cx,cy,sc,bw,ink):
        h=24*sc*self._h();w=30*sc
        s1=self.stroke.quadratic_bezier((cx,cy-h*.82),(cx+w*.18,cy+2),(cx+w*.34,cy-h*.4))
        s2=self.stroke.quadratic_bezier((cx+w*.34,cy-h*.4),(cx+w*.5,cy+2),(cx+w*.66,cy-h*.4))
        s3=self.stroke.quadratic_bezier((cx+w*.66,cy-h*.4),(cx+w*.82,cy+2),(cx+w,cy-h*.82))
        self.stroke.draw_stroke(cv,s1+s2+s3,bw,ink_color=ink)
        return cx+w*self._c()
    def _L_X(self,cv,cx,cy,sc,bw,ink):
        h=26*sc*self._h();w=20*sc
        self.stroke.draw_stroke(cv,self.stroke.cubic_bezier((cx,cy-h),(cx+w*.35,cy-h*.55),(cx+w*.65,cy-h*.45),(cx+w,cy)),bw,ink_color=ink)
        self.stroke.draw_stroke(cv,self.stroke.cubic_bezier((cx+w,cy-h),(cx+w*.65,cy-h*.55),(cx+w*.35,cy-h*.45),(cx,cy)),bw,ink_color=ink)
        return cx+w*self._c()
    def _L_Y(self,cv,cx,cy,sc,bw,ink):
        h=30*sc*self._h();w=22*sc
        left=self.stroke.quadratic_bezier((cx,cy-h),(cx+w*.45,cy-h*.42),(cx+w*.5,cy-h*.38))
        right=self.stroke.quadratic_bezier((cx+w,cy-h),(cx+w*.55,cy-h*.42),(cx+w*.5,cy-h*.38))
        self.stroke.draw_stroke(cv,left+right+self.stroke.make_down_stroke(cx+w*.5,cy-h*.38,cy,lean=self.rng.uniform(0,2)*sc),bw,ink_color=ink)
        return cx+w*self._c()
    def _L_Z(self,cv,cx,cy,sc,bw,ink):
        h=26*sc*self._h();w=20*sc
        self.stroke.draw_stroke(cv,
            self.stroke.connect((cx,cy-h),(cx+w,cy-h),self.rng.uniform(-2,1))+
            self.stroke.cubic_bezier((cx+w,cy-h),(cx+w*.6,cy-h*.5),(cx+w*.4,cy-h*.5),(cx,cy))+
            self.stroke.connect((cx,cy),(cx+w,cy),self.rng.uniform(-1,2)),bw,ink_color=ink)
        return cx+w*self._c()

    # ── Public API ─────────────────────────────────────────────────────────────
    def generate(self, name: str, paper_texture=False):
        parts = name.strip().upper().split()
        first = parts[0]  if len(parts)>=1 else ""
        last  = parts[-1] if len(parts)>=2 else ""
        force = self.style_name == "Clear Print"
        display = _pick_name(first, last, self.rng, force_full=force)
        return self._render(display, paper_texture)

    def generate_transparent(self, name: str):
        parts = name.strip().upper().split()
        first = parts[0]  if len(parts)>=1 else ""
        last  = parts[-1] if len(parts)>=2 else ""
        force = self.style_name == "Clear Print"
        display = _pick_name(first, last, self.rng, force_full=force)
        bgr  = self._render(display, False)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        _, alpha = cv2.threshold(gray, 228, 255, cv2.THRESH_BINARY_INV)
        alpha = cv2.GaussianBlur(alpha, (3,3), 0.6)
        bgra  = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
        bgra[:,:,3] = alpha
        return bgra

    def _render(self, display, paper_texture):
        canvas = self._canvas(paper_texture)
        ink    = self._ink()

        if not display: display = "SIGN"

        # Scale to fill canvas
        n_chars = sum(0.45 if c==' ' else 1 for c in display)
        char_w  = 26 * self.compress
        avail   = self.W - 2*self.MARGIN - 80  # reserve 80px for ending stroke
        fit_sc  = min(1.4, avail / max(n_chars * char_w, 1))

        # Center + slight random offset
        actual_w = n_chars * char_w * fit_sc
        start_x  = (self.W - actual_w - 60) / 2 + self.rng.uniform(-8,8)*self.randomness
        start_x  = max(self.MARGIN*0.4, start_x)
        base_y   = self.H * 0.58 + self.rng.uniform(-8,8)*self.randomness

        cx = start_x
        end_x = cx; end_y = base_y

        for i, ch in enumerate(display):
            if ch == ' ':
                cx += 14*fit_sc*self.compress*self.rng.uniform(0.8,1.2)
                continue

            is_first = (i==0 or display[i-1]==' ')
            cy_cur   = base_y + (cx - start_x)*self.slant*self.rng.uniform(0.9,1.1)
            bw       = self.base_width * fit_sc

            if is_first:
                # Draw large initial flourish INSTEAD of the plain letter
                nx = self._draw_initial(canvas, cx, cy_cur, fit_sc, bw*1.2, ink)
                # Skip the letter shape itself — flourish IS the first letter
            else:
                nx = self._draw_letter(canvas, ch, cx, cy_cur, fit_sc, bw, ink, False)

            end_x = nx; end_y = cy_cur
            cx = nx + self.gap*4*fit_sc*self.rng.uniform(0.85,1.15)

        # Draw long ending stroke
        self._draw_ending(canvas, end_x, end_y, fit_sc, self.base_width*fit_sc, ink)

        canvas = cv2.GaussianBlur(canvas, (3,3), 0.35)
        return canvas