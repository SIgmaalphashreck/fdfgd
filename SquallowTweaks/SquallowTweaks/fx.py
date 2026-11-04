"""SquallowTweaks - Theme-Effekte: je Theme ein eigenes, dezentes Hintergrund-Feature (ressourcenschonend).

* Alle Effekte zeichnen nur in den Hintergrund (hinter den Karten) und lesen Farben live aus den Design-Tokens.
* Der Timer laeuft nur, wenn das Fenster sichtbar + aktiv ist und ein Effekt gewaehlt ist (Stufe Aus/Reduziert/Voll).
* Keine Bilder, keine Shader: nur wenige QPainter-Primitive pro Frame.
"""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QApplication, QWidget

from theme import C, ThemeManager


def _a(color: str, alpha: int) -> QColor:
    c = QColor(color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


def _blob(p: QPainter, x: float, y: float, r: float, color: str, alpha: int) -> None:
    g = QRadialGradient(QPointF(x, y), r)
    g.setColorAt(0, _a(color, alpha))
    g.setColorAt(1, _a(color, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawEllipse(QPointF(x, y), r, r)


class Effect:
    """Basisklasse. level: 1 = reduziert, 2 = voll."""

    animated = True

    def __init__(self, level: int):
        self.level = level
        self.rng = random.Random(1337)
        self.size = (0, 0)

    def resize(self, w: int, h: int) -> None:
        self.size = (w, h)

    def paint(self, p: QPainter, w: int, h: int, t: float) -> None:  # pragma: no cover - reine Optik
        pass


class Glass(Effect):                 # Black: Glas-Glanz + wandernder Lichtstreif
    def paint(self, p, w, h, t):
        _blob(p, w * (0.25 + 0.1 * math.sin(t * 0.12)), h * 0.18, h * 0.9, "#ffffff", 9)
        _blob(p, w * (0.80 + 0.08 * math.cos(t * 0.10)), h * 0.85, h * 0.8, C.accent, 8)
        ph = (t % 11.0) / 11.0
        x = -w * 0.3 + ph * w * 1.6
        g = QLinearGradient(x - 120, 0, x + 120, h * 0.35)
        g.setColorAt(0, _a("#ffffff", 0))
        g.setColorAt(0.5, _a("#ffffff", 13))
        g.setColorAt(1, _a("#ffffff", 0))
        p.fillRect(QRectF(0, 0, w, h), QBrush(g))
        p.setPen(QPen(_a("#ffffff", 22), 1))
        p.drawLine(QPointF(0, 0.5), QPointF(w, 0.5))


class SoftLight(Effect):             # White: weiche Pastell-Lichtflecken
    def paint(self, p, w, h, t):
        for i, col in enumerate((C.accent, C.secondary, C.tertiary)):
            x = w * (0.2 + 0.6 * (0.5 + 0.5 * math.sin(t * 0.08 + i * 2.1)))
            y = h * (0.2 + 0.6 * (0.5 + 0.5 * math.cos(t * 0.07 + i * 1.7)))
            _blob(p, x, y, h * 0.75, col, 34)


class Neon(Effect):                  # Pink: pulsierender Neon-Rahmen + Glow-Orbs
    def paint(self, p, w, h, t):
        pulse = 0.55 + 0.45 * math.sin(t * 1.6)
        rect = QRectF(6, 6, w - 12, h - 12)
        for width, a in ((14, 10), (8, 18), (4, 30), (1.5, 120)):
            p.setPen(QPen(_a(C.accent, a * (0.5 + pulse * 0.7)), width))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect, 16, 16)
        _blob(p, w * 0.12, h * 0.9, h * 0.6, C.accent, int(26 * pulse))
        _blob(p, w * 0.9, h * 0.1, h * 0.55, C.secondary, int(20 * (1 - pulse * 0.4)))


class Energy(Effect):                # Purple: animierte Lichtlinien
    def __init__(self, level):
        super().__init__(level)
        n = 5 if level < 2 else 8
        self.lines = [(self.rng.random(), self.rng.uniform(0.05, 0.12), self.rng.uniform(0.4, 1.0), self.rng.uniform(140, 300)) for _ in range(n)]

    def paint(self, p, w, h, t):
        _blob(p, w * 0.5, h * 1.05, h * 1.1, C.accent, 20)
        for k, (off, speed, power, length) in enumerate(self.lines):
            ph = (off + t * speed) % 1.0
            x = -length + ph * (w + 2 * length)
            y = h * ((k + 0.5) / len(self.lines))
            g = QLinearGradient(x, y, x + length, y - length * 0.36)
            g.setColorAt(0, _a(C.accent, 0))
            g.setColorAt(0.6, _a(C.accent2, 70 * power))
            g.setColorAt(1, _a(C.accent, 0))
            p.setPen(QPen(QBrush(g), 1.6))
            p.drawLine(QPointF(x, y), QPointF(x + length, y - length * 0.36))


class Matrix(Effect):                # Green: dezenter Code-Regen + Partikel
    GLYPHS = "01ABCDEF<>/{}=+*#$%&"

    def resize(self, w, h):
        super().resize(w, h)
        self.cell = 22 if self.level >= 2 else 34
        n = max(1, w // self.cell)
        self.trail = 9 if self.level >= 2 else 6
        self.cols = [[self.rng.uniform(-h, h) / self.cell, self.rng.uniform(4, 10), [self.rng.choice(self.GLYPHS) for _ in range(self.trail)]] for _ in range(n)]
        self.dots = [(self.rng.random(), self.rng.random(), self.rng.uniform(0.02, 0.06), self.rng.uniform(1, 2.2)) for _ in range(16 if self.level >= 2 else 8)]
        self.last = None

    def paint(self, p, w, h, t):
        if self.size != (w, h):
            self.resize(w, h)
        dt = 0.04 if self.last is None else min(0.2, t - self.last)
        self.last = t
        f = QFont("Consolas")
        f.setPixelSize(13)
        f.setStyleHint(QFont.Monospace)
        p.setFont(f)
        rows = h / self.cell
        for i, col in enumerate(self.cols):
            prev = int(col[0])
            col[0] += col[1] * dt
            if int(col[0]) != prev:
                col[2].insert(0, self.rng.choice(self.GLYPHS))
                col[2].pop()
            if col[0] - self.trail > rows:
                col[0] = self.rng.uniform(-8, 0)
                col[1] = self.rng.uniform(4, 10)
            x = i * self.cell + 4
            for k, ch in enumerate(col[2]):
                y = (col[0] - k) * self.cell
                if y < -self.cell or y > h:
                    continue
                a = 70 if k == 0 else int(46 * (1 - k / self.trail))
                p.setPen(_a(C.accent2 if k == 0 else C.accent, a))
                p.drawText(QPointF(x, y), ch)
        p.setPen(Qt.NoPen)
        for (fx, fy, sp, r) in self.dots:
            y = (fy - t * sp) % 1.0
            p.setBrush(_a(C.accent2, 60))
            p.drawEllipse(QPointF(fx * w, y * h), r, r)


class Holo(Effect):                  # Blue: Hologramm-Raster, Scanlines, Scan-Band
    def resize(self, w, h):
        super().resize(w, h)
        pm = QPixmap(max(1, w), max(1, h))
        pm.fill(Qt.transparent)
        q = QPainter(pm)
        q.setPen(QPen(_a(C.accent2, 9), 1))
        for y in range(0, h, 4):
            q.drawLine(0, y, w, y)
        q.setPen(QPen(_a(C.accent, 14), 1))
        for x in range(0, w, 56):
            q.drawLine(x, 0, x, h)
        for y in range(0, h, 56):
            q.drawLine(0, y, w, y)
        q.end()
        self.cache, self.cache_key = pm, (C.accent, C.accent2)

    def paint(self, p, w, h, t):
        if self.size != (w, h) or self.cache_key != (C.accent, C.accent2):
            self.resize(w, h)
        p.drawPixmap(0, 0, self.cache)
        ph = (t % 7.0) / 7.0
        y = -80 + ph * (h + 160)
        g = QLinearGradient(0, y - 70, 0, y + 70)
        g.setColorAt(0, _a(C.accent2, 0))
        g.setColorAt(0.5, _a(C.accent2, 26))
        g.setColorAt(1, _a(C.accent2, 0))
        p.fillRect(QRectF(0, y - 70, w, 140), QBrush(g))
        _blob(p, w * 0.85, h * 0.15, h * 0.7, C.accent, 18)


class Pulse(Effect):                 # Red: rote Lichtimpulse aus den Ecken
    def paint(self, p, w, h, t):
        for cx, cy, off in ((0, h, 0.0), (w, 0, 0.5)):
            for k in range(2):
                ph = ((t / 3.6) + off + k * 0.5) % 1.0
                r = ph * max(w, h) * 0.9
                p.setBrush(Qt.NoBrush)
                p.setPen(QPen(_a(C.accent, 90 * (1 - ph) ** 1.6), 2 + 5 * (1 - ph)))
                p.drawEllipse(QPointF(cx, cy), r, r)
        _blob(p, 0, h, h * 0.8, C.accent, 24)
        _blob(p, w, 0, h * 0.6, C.secondary, 14)
        x = (t / 5.0 % 1.0) * (w + 400) - 200
        g = QLinearGradient(x - 200, 0, x + 200, 0)
        g.setColorAt(0, _a(C.accent, 0))
        g.setColorAt(0.5, _a(C.accent2, 120))
        g.setColorAt(1, _a(C.accent, 0))
        p.fillRect(QRectF(0, 0, w, 2), QBrush(g))


class Electric(Effect):              # Cyan: kurze elektrische Blitze + Funken
    def __init__(self, level):
        super().__init__(level)
        self.arcs: list = []
        self.next_at = 0.8

    def _new_arc(self, w, h, t):
        x0 = self.rng.choice((0, w)) if self.rng.random() < 0.6 else self.rng.uniform(0, w)
        y0 = self.rng.uniform(0, h) if x0 in (0, w) else self.rng.choice((0, h))
        x1, y1 = w / 2 + self.rng.uniform(-w * .25, w * .25), h / 2 + self.rng.uniform(-h * .25, h * .25)
        pts = [QPointF(x0, y0)]
        n = 9
        for i in range(1, n):
            f = i / n
            pts.append(QPointF(x0 + (x1 - x0) * f * 0.55 + self.rng.uniform(-26, 26), y0 + (y1 - y0) * f * 0.55 + self.rng.uniform(-26, 26)))
        self.arcs.append((t, pts))

    def paint(self, p, w, h, t):
        _blob(p, w * (0.5 + 0.3 * math.sin(t * 0.2)), h * 0.5, h * 0.9, C.accent, 12)
        if t >= self.next_at:
            self._new_arc(w, h, t)
            self.next_at = t + self.rng.uniform(1.2, 3.2 if self.level >= 2 else 4.5)
        alive = []
        for t0, pts in self.arcs:
            age = (t - t0) / 0.45
            if age >= 1:
                continue
            alive.append((t0, pts))
            fade = (1 - age) ** 2
            path = QPainterPath(pts[0])
            for q in pts[1:]:
                path.lineTo(q)
            p.setBrush(Qt.NoBrush)
            for wd, a in ((7, 16), (3.5, 40), (1.3, 150)):
                p.setPen(QPen(_a(C.accent2, a * fade), wd, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.drawPath(path)
        self.arcs = alive


class Stars(Effect):                 # Midnight: Sterne, Nebel, Sternschnuppe
    def resize(self, w, h):
        super().resize(w, h)
        n = 70 if self.level >= 2 else 36
        self.stars = [(self.rng.random(), self.rng.random(), self.rng.uniform(0.6, 1.7), self.rng.uniform(0, 6.28), self.rng.uniform(0.4, 1.6)) for _ in range(n)]
        self.shoot_at = 4.0
        self.shoot = None

    def paint(self, p, w, h, t):
        if self.size != (w, h):
            self.resize(w, h)
        _blob(p, w * (0.22 + 0.03 * math.sin(t * 0.05)), h * 0.30, h * 0.9, C.accent, 18)
        _blob(p, w * 0.82, h * 0.78, h * 0.8, C.secondary, 15)
        _blob(p, w * 0.55, h * 0.1, h * 0.5, C.tertiary, 9)
        p.setPen(Qt.NoPen)
        for sx, sy, r, ph, sp in self.stars:
            tw = 0.5 + 0.5 * math.sin(t * sp + ph)
            p.setBrush(_a("#ffffff", 40 + 150 * tw))
            p.drawEllipse(QPointF(sx * w, sy * h), r, r)
        if t >= self.shoot_at and self.shoot is None:
            self.shoot = (t, self.rng.uniform(0.1, 0.7) * w, self.rng.uniform(0.0, 0.3) * h)
            self.shoot_at = t + self.rng.uniform(6, 12)
        if self.shoot:
            t0, x0, y0 = self.shoot
            age = (t - t0) / 0.9
            if age >= 1:
                self.shoot = None
            else:
                x, y = x0 + age * 360, y0 + age * 180
                g = QLinearGradient(x - 90, y - 45, x, y)
                g.setColorAt(0, _a("#ffffff", 0))
                g.setColorAt(1, _a("#ffffff", 190 * (1 - age)))
                p.setPen(QPen(QBrush(g), 1.6))
                p.drawLine(QPointF(x - 90, y - 45), QPointF(x, y))


class Chromatic(Effect):             # Chromatic: fliessende Farbverlaeufe (Farben kommen vom wandernden Akzent)
    def paint(self, p, w, h, t):
        for i, col in enumerate((C.accent, C.secondary, C.tertiary)):
            x = w * (0.5 + 0.42 * math.sin(t * 0.11 + i * 2.2))
            y = h * (0.5 + 0.38 * math.cos(t * 0.09 + i * 1.6))
            _blob(p, x, y, h * 0.85, col, 36)
        g = QLinearGradient(0, h, w, 0)
        g.setColorAt(0, _a(C.accent, 0))
        g.setColorAt(0.5, _a(C.accent2, 10))
        g.setColorAt(1, _a(C.secondary, 0))
        p.fillRect(QRectF(0, 0, w, h), QBrush(g))


EFFECTS = {"glass": Glass, "softlight": SoftLight, "neon": Neon, "energy": Energy, "matrix": Matrix, "holo": Holo,
           "pulse": Pulse, "electric": Electric, "stars": Stars, "chromatic": Chromatic}


class FxRoot(QWidget):
    """Wurzel-Widget des Fensters: malt Hintergrundfarbe + Effekt; alle Seiten liegen transparent darueber."""

    def __init__(self, manager: ThemeManager):
        super().__init__()
        self.setObjectName("root")
        self.manager = manager
        self.t0 = time.perf_counter()
        self.effect: Effect | None = None
        self._fx_name = ""
        self._level = -1
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        app = QApplication.instance()
        if app:
            app.applicationStateChanged.connect(lambda _s: self.sync())
        self.sync()

    # --- Steuerung ---
    def sync(self) -> None:
        """Effekt/Timer an Theme + Stufe + Sichtbarkeit anpassen."""
        level = self.manager.fx_level
        name = C.fx
        if (name, level) != (self._fx_name, self._level):
            self._fx_name, self._level = name, level
            cls = EFFECTS.get(name)
            self.effect = cls(level) if (cls and level > 0) else None
        app = QApplication.instance()
        active = bool(app and app.applicationState() == Qt.ApplicationActive)
        animate = (self.effect is not None or (C.chromatic and level > 0)) and self.isVisible() and active and level > 0
        interval = 45 if level >= 2 else 85
        if animate:
            if not self.timer.isActive() or self.timer.interval() != interval:
                self.timer.start(interval)
        else:
            self.timer.stop()
        self.update()

    def showEvent(self, e):
        super().showEvent(e)
        self.sync()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.sync()

    def _tick(self) -> None:
        t = time.perf_counter() - self.t0
        if C.chromatic:
            self.manager.chromatic_tick(t / 38.0)       # ~38 s pro Farbkreis
        self.update()

    # --- Zeichnen ---
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(C.bg))
        if self.effect:
            t = time.perf_counter() - self.t0
            p.save()
            p.setClipRect(self.rect())
            try:
                self.effect.paint(p, self.width(), self.height(), t)
            finally:
                p.restore()
