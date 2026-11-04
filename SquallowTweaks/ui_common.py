"""SquallowTweaks - Farben, Stylesheet und Widgets (mit animierten Hover-Effekten)."""
from __future__ import annotations

import math
import os
import time
from collections import deque
from typing import Optional

from PySide6.QtCore import (Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QBrush, QColor, QCursor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QPolygonF, QRadialGradient)
from PySide6.QtWidgets import (QAbstractButton, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QSizePolicy, QVBoxLayout, QWidget)

from theme import C, contrast_text  # noqa: E402  (zentrale Design-Tokens)

EVIDENCE_TEXT = {"belegt": "Wirkung laut Tests belegt", "klein": "Kleine/systemabhängige Wirkung", "schwach": "Wirkung kaum belegt (optional)"}


def tag_color(tag: str) -> str:
    return {"FPS": C.accent2, "LATENZ": C.secondary, "PING": C.green, "FRAMETIME": C.tertiary}.get(tag, C.muted)


def evidence_color(ev: str) -> str:
    return {"belegt": C.green, "klein": C.yellow, "schwach": C.dim}.get(ev, C.dim)


def build_qss() -> str:
    """Stylesheet aus den aktuellen Design-Tokens. Wird bei jedem Theme-Wechsel neu gebaut."""
    return f"""
* {{ font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", sans-serif; font-size: 13px; color: {C.text}; }}
QMainWindow {{ background: {C.bg}; }}
QWidget {{ background: transparent; }}
#sidebar {{ background: {C.sidebar}; border-right: 1px solid {C.border}; }}
QLabel#h1 {{ font-size: 26px; font-weight: 700; }}
QLabel#h2 {{ font-size: 15px; font-weight: 600; }}
QLabel#muted {{ color: {C.muted}; }}
QLabel#dim {{ color: {C.dim}; font-size: 11px; }}
QLabel#section {{ color: {C.dim}; font-size: 10px; font-weight: 700; letter-spacing: 2px; }}
QLabel#big {{ font-size: 26px; font-weight: 700; }}
QLabel#pill {{ border-radius: 8px; padding: 2px 8px; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
QLineEdit {{ background: {C.card}; border: 1px solid {C.border}; border-radius: 10px; padding: 9px 12px; selection-background-color: {C.accent}; selection-color: {C.on_accent}; }}
QLineEdit:hover {{ border-color: {C.border_hi}; }}
QLineEdit:focus {{ border-color: {C.accent}; background: {C.input_focus}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; border: none; }}
QScrollBar::handle:vertical {{ background: {C.scroll}; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: {C.scroll_h}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; width: 0px; background: none; border: none; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{ height: 0px; background: none; border: none; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
QProgressBar {{ background: {C.card2}; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; }}
QProgressBar::chunk {{ border-radius: 3px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {C.accent}, stop:1 {C.secondary}); }}
QToolTip {{ background: {C.tooltip_bg}; color: {C.text}; border: 1px solid {C.tooltip_border}; padding: 8px; border-radius: 6px; }}
QTableView {{ background: transparent; border: none; gridline-color: transparent; outline: 0; }}
QHeaderView::section {{ background: transparent; color: {C.dim}; border: none; padding: 6px 10px; font-size: 10px; font-weight: 700; letter-spacing: 2px; }}
QComboBox {{ background: {C.card}; border: 1px solid {C.border}; border-radius: 10px; padding: 7px 12px; }}
QComboBox:hover {{ border-color: {C.accent}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {C.card2}; border: 1px solid {C.border_hi}; selection-background-color: {C.chip_on}; selection-color: {C.text}; outline: 0; padding: 4px; }}
QMenu {{ background: {C.card2}; border: 1px solid {C.border_hi}; border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 7px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {C.chip_on}; }}
QSlider::groove:horizontal {{ height: 6px; background: {C.card2}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {C.accent}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: #ffffff; width: 14px; height: 14px; margin: -5px 0; border-radius: 8px; border: 2px solid {C.accent}; }}
QDialog, QMessageBox {{ background: {C.card}; }}
QMessageBox QPushButton, QDialog QPushButton {{ background: {C.card2}; border: 1px solid {C.border}; border-radius: 8px; padding: 7px 16px; min-width: 70px; }}
QMessageBox QPushButton:hover, QDialog QPushButton:hover {{ border-color: {C.accent}; background: {C.ghost_h}; }}
"""


def lerp(a, b, t: float) -> QColor:
    a, b = QColor(a), QColor(b)
    t = max(0.0, min(1.0, t))
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t), int(a.alpha() + (b.alpha() - a.alpha()) * t))


def alpha(color, a: int) -> QColor:
    c = QColor(color)
    c.setAlpha(a)
    return c


class HoverValue:
    """Animierter Wert 0..1 fuer Hover-Effekte (sanfter Uebergang statt Sprung)."""

    def __init__(self, widget: QWidget, duration: int = 160):
        self.v = 0.0
        self.widget = widget
        self.anim = QVariantAnimation(widget)
        self.anim.setDuration(duration)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.valueChanged.connect(self._tick)

    def _tick(self, x):
        self.v = float(x)
        self.widget.update()

    def to(self, end: float):
        self.anim.stop()
        self.anim.setStartValue(self.v)
        self.anim.setEndValue(float(end))
        self.anim.start()


def pointer_inside(w: QWidget) -> bool:
    return w.rect().contains(w.mapFromGlobal(QCursor.pos()))


# ---------------------------------------------------------------------------
# Icons (gezeichnet)
# ---------------------------------------------------------------------------
def draw_icon(p: QPainter, name: str, rect: QRectF, color) -> None:
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(rect.topLeft())
    s = rect.width()
    c = QColor(color)
    p.setPen(QPen(c, max(1.6, s * 0.085), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    if name == "dashboard":
        g = s * 0.14
        w = (s - 3 * g) / 2
        for r in range(2):
            for q in range(2):
                p.drawRoundedRect(QRectF(g + q * (w + g), g + r * (w + g), w, w), 3, 3)
    elif name == "bolt":
        poly = QPolygonF([QPointF(s * .58, s * .08), QPointF(s * .22, s * .56), QPointF(s * .47, s * .56),
                          QPointF(s * .40, s * .92), QPointF(s * .78, s * .42), QPointF(s * .52, s * .42)])
        p.setBrush(c)
        p.drawPolygon(poly)
    elif name == "target":
        p.drawEllipse(QRectF(s * .14, s * .14, s * .72, s * .72))
        p.drawEllipse(QRectF(s * .36, s * .36, s * .28, s * .28))
        for a, b, c2, d in ((.5, .02, .5, .2), (.5, .8, .5, .98), (.02, .5, .2, .5), (.8, .5, .98, .5)):
            p.drawLine(QPointF(s * a, s * b), QPointF(s * c2, s * d))
    elif name == "bench":
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        for i, h in enumerate((0.34, 0.62, 0.9)):
            p.drawRoundedRect(QRectF(s * (0.12 + i * 0.3), s * .94 - s * h, s * .2, s * h), 2, 2)
    elif name == "wifi":
        for r in (0.20, 0.36, 0.52):
            p.drawArc(QRectF(s * .5 - s * r, s * .78 - s * r, 2 * s * r, 2 * s * r), 45 * 16, 90 * 16)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(s * .5, s * .78), s * .06, s * .06)
    elif name == "list":
        for i in range(3):
            y = s * (0.22 + i * 0.28)
            p.drawLine(QPointF(s * .30, y), QPointF(s * .92, y))
            p.setBrush(c)
            p.drawEllipse(QPointF(s * .12, y), 1.4, 1.4)
            p.setBrush(Qt.NoBrush)
    elif name == "trash":
        p.drawLine(QPointF(s * .18, s * .26), QPointF(s * .82, s * .26))
        p.drawLine(QPointF(s * .40, s * .26), QPointF(s * .40, s * .14))
        p.drawLine(QPointF(s * .40, s * .14), QPointF(s * .60, s * .14))
        p.drawLine(QPointF(s * .60, s * .14), QPointF(s * .60, s * .26))
        path = QPainterPath()
        path.moveTo(s * .26, s * .26)
        path.lineTo(s * .30, s * .88)
        path.lineTo(s * .70, s * .88)
        path.lineTo(s * .74, s * .26)
        p.drawPath(path)
        p.drawLine(QPointF(s * .44, s * .42), QPointF(s * .44, s * .72))
        p.drawLine(QPointF(s * .56, s * .42), QPointF(s * .56, s * .72))
    elif name == "gear":
        p.drawEllipse(QRectF(s * .30, s * .30, s * .40, s * .40))
        for i in range(8):
            a = math.radians(i * 45)
            p.drawLine(QPointF(s * .5 + math.cos(a) * s * .30, s * .5 + math.sin(a) * s * .30),
                       QPointF(s * .5 + math.cos(a) * s * .44, s * .5 + math.sin(a) * s * .44))
    elif name == "discord":
        body = QPainterPath()
        body.addRoundedRect(QRectF(s * .10, s * .20, s * .80, s * .56), s * .22, s * .22)
        tail = QPainterPath()
        tail.addPolygon(QPolygonF([QPointF(s * .30, s * .70), QPointF(s * .22, s * .90), QPointF(s * .46, s * .76)]))
        tail2 = QPainterPath()
        tail2.addPolygon(QPolygonF([QPointF(s * .70, s * .70), QPointF(s * .78, s * .90), QPointF(s * .54, s * .76)]))
        shape = body.united(tail).united(tail2)
        for cx in (.35, .65):
            eye = QPainterPath()
            eye.addEllipse(QPointF(s * cx, s * .47), s * .085, s * .105)
            shape = shape.subtracted(eye)
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawPath(shape)
    elif name == "cpu":
        p.drawRoundedRect(QRectF(s * .24, s * .24, s * .52, s * .52), 3, 3)
        p.drawRoundedRect(QRectF(s * .38, s * .38, s * .24, s * .24), 1.5, 1.5)
        for i in range(3):
            t = s * (0.34 + i * 0.16)
            p.drawLine(QPointF(t, s * .08), QPointF(t, s * .24))
            p.drawLine(QPointF(t, s * .76), QPointF(t, s * .92))
            p.drawLine(QPointF(s * .08, t), QPointF(s * .24, t))
            p.drawLine(QPointF(s * .76, t), QPointF(s * .92, t))
    elif name == "gpu":
        p.drawRoundedRect(QRectF(s * .08, s * .26, s * .84, s * .48), 3, 3)
        p.drawEllipse(QPointF(s * .36, s * .50), s * .13, s * .13)
        p.drawEllipse(QPointF(s * .70, s * .50), s * .08, s * .08)
        p.drawLine(QPointF(s * .16, s * .74), QPointF(s * .16, s * .86))
    elif name == "ram":
        p.drawRoundedRect(QRectF(s * .08, s * .28, s * .84, s * .38), 3, 3)
        for i in range(4):
            x = s * (0.22 + i * 0.18)
            p.drawLine(QPointF(x, s * .38), QPointF(x, s * .56))
        for i in range(5):
            x = s * (0.16 + i * 0.17)
            p.drawLine(QPointF(x, s * .66), QPointF(x, s * .78))
    elif name == "disk":
        p.drawRoundedRect(QRectF(s * .12, s * .30, s * .76, s * .40), 4, 4)
        p.drawLine(QPointF(s * .22, s * .60), QPointF(s * .48, s * .60))
        p.setBrush(c)
        p.drawEllipse(QPointF(s * .76, s * .56), s * .035, s * .035)
    elif name == "check":
        p.drawPolyline(QPolygonF([QPointF(s * .20, s * .52), QPointF(s * .42, s * .74), QPointF(s * .80, s * .28)]))
    elif name == "clock":
        p.drawEllipse(QRectF(s * .14, s * .14, s * .72, s * .72))
        p.drawLine(QPointF(s * .5, s * .5), QPointF(s * .5, s * .28))
        p.drawLine(QPointF(s * .5, s * .5), QPointF(s * .66, s * .58))
    elif name == "therm":
        p.drawRoundedRect(QRectF(s * .42, s * .10, s * .16, s * .56), s * .08, s * .08)
        p.setBrush(c)
        p.drawEllipse(QPointF(s * .5, s * .76), s * .15, s * .15)
        p.drawLine(QPointF(s * .5, s * .30), QPointF(s * .5, s * .70))
    elif name == "palette":
        p.drawEllipse(QRectF(s * .10, s * .12, s * .80, s * .76))
        p.setBrush(c)
        for cx, cy in ((.34, .36), (.58, .30), (.70, .52), (.38, .60)):
            p.drawEllipse(QPointF(s * cx, s * cy), s * .055, s * .055)
    p.restore()


def tinted_pixmap(path: str, size: int) -> QPixmap:
    return QPixmap(path).scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------
def label(text: str = "", name: str = "", wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def pill(text: str, color: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("pill")
    c = QColor(color)
    lab.setStyleSheet(f"QLabel#pill {{ color: {color}; background: rgba({c.red()},{c.green()},{c.blue()},38); }}")
    lab.setAlignment(Qt.AlignCenter)
    lab.setFixedHeight(20)
    lab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return lab


class ElidedLabel(QLabel):
    def __init__(self, text: str = "", name: str = ""):
        super().__init__(text)
        if name:
            self.setObjectName(name)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(40)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _e):
        p = QPainter(self)
        fm = QFontMetrics(self.font())
        p.setPen(self.palette().color(self.foregroundRole()))
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignVCenter | Qt.AlignLeft, fm.elidedText(self.text(), Qt.ElideRight, self.width()))


def resolve(x):
    """Token-Name ("accent") oder Hex-Farbe -> Hex. So koennen Widgets Farben beim Zeichnen live aus dem Theme lesen."""
    return getattr(C, x) if isinstance(x, str) and not x.startswith("#") and hasattr(C, x) else x


class HoverFrame(QFrame):
    """Karte mit animiertem Hover: weicher Schatten (hebt die Karte an), leuchtender Rand und Akzent-Linie oben.
    base/hover/border/hborder sind Token-Namen und werden beim Zeichnen aufgeloest (Theme-Wechsel wirkt sofort)."""

    LIFT = 3     # Platz unter der Karte fuer den Schatten

    def __init__(self, radius: int = 14, base: str = "card", hover: str = "card2", border: str = "border", hborder: str = "accent",
                 hover_on: bool = True):
        super().__init__()
        self.radius, self.base, self.hover, self.border, self.hborder, self.hover_on = radius, base, hover, border, hborder, hover_on
        self.hv = HoverValue(self)

    def enterEvent(self, e):
        if self.hover_on:
            self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if self.hover_on and not pointer_inside(self):
            self.hv.to(0)
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.hv.v
        body = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5 - self.LIFT)
        base, hover, border, hb = resolve(self.base), resolve(self.hover), resolve(self.border), resolve(self.hborder)
        if h > 0.02:
            outside = QPainterPath()
            outside.setFillRule(Qt.OddEvenFill)
            outside.addRect(QRectF(self.rect()))
            outside.addRoundedRect(body, self.radius, self.radius)
            p.save()
            p.setClipPath(outside)
            p.setPen(Qt.NoPen)
            for i, a in ((3, 16), (2, 24), (1, 34)):
                p.setBrush(QColor(0, 0, 0, int(a * h * (0.55 if C.light else 1.0))))
                p.drawRoundedRect(body.translated(0, i * h).adjusted(-0.4 * i * h, 0, 0.4 * i * h, 0), self.radius, self.radius)
            p.restore()
        p.setPen(QPen(lerp(border, hb, h * 0.9), 1 + h * 0.6))
        fill = lerp(base, hover, h)
        fill.setAlpha(C.glass)
        p.setBrush(fill)
        p.drawRoundedRect(body, self.radius, self.radius)
        if h > 0.02:
            g = QLinearGradient(body.left(), 0, body.right(), 0)
            g.setColorAt(0, alpha(hb, 0))
            g.setColorAt(0.5, alpha(hb, int(200 * h)))
            g.setColorAt(1, alpha(C.secondary, 0))
            p.setPen(QPen(QBrush(g), 1.6))
            p.drawLine(QPointF(body.left() + self.radius, body.top() + 0.8), QPointF(body.right() - self.radius, body.top() + 0.8))


class Card(HoverFrame):
    def __init__(self, name: str = "card"):
        if name == "hero":
            super().__init__(16, "hero_a", "hero_b", "hero_border", "accent2")
        else:
            super().__init__(14)


class AnimButton(QPushButton):
    """Button mit animiertem Hover. variant: accent | ghost | danger | chip."""

    def __init__(self, text: str, variant: str = "ghost"):
        super().__init__(text)
        self.variant = variant
        self.hv = HoverValue(self)
        self.setCursor(Qt.PointingHandCursor)
        self.setCheckable(variant == "chip")
        self.setFocusPolicy(Qt.NoFocus)
        self._fx: Optional[QGraphicsDropShadowEffect] = None
        self.setMinimumWidth(self.sizeHint().width())
        if variant == "accent":
            self._fx = QGraphicsDropShadowEffect(self)
            self._fx.setOffset(0, 4)
            self._fx.setBlurRadius(24)
            self._fx.setColor(alpha(C.accent, 100))
            self.setGraphicsEffect(self._fx)
            self.hv.anim.valueChanged.connect(self._glow)

    def _glow(self, v):
        if self._fx:
            self._fx.setBlurRadius(24 + 18 * float(v))
            self._fx.setColor(alpha(C.accent, int(100 + 110 * float(v))))

    def sizeHint(self) -> QSize:
        f = QFont(self.font())
        f.setBold(True)
        f.setPixelSize(15 if self.variant == "accent" else 13)
        w = QFontMetrics(f).horizontalAdvance(self.text())
        return QSize(w + {"accent": 56, "chip": 30}.get(self.variant, 34), {"accent": 48, "chip": 32}.get(self.variant, 38))

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hv.to(0)
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.hv.v
        v = self.variant
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5) if v != "accent" else QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = 12 if v == "accent" else (r.height() / 2 if v == "chip" else 10)
        txt = QColor(C.text)
        if h > 0.02 and self.isEnabled() and v in ("ghost", "danger", "chip"):
            p.setPen(QPen(alpha(C.red if v == "danger" else C.accent, int(46 * h)), 3))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(-0.6, -0.6, 0.6, 0.6), rad, rad)
        if not self.isEnabled():
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C.btn_off))
            p.drawRoundedRect(r, rad, rad)
            txt = QColor(C.dim)
        elif v == "accent":
            g = QLinearGradient(r.left(), 0, r.right(), 0)
            g.setColorAt(0, lerp(C.btn_a, C.btn_a_h, h))
            g.setColorAt(1, lerp(C.btn_b, C.btn_b_h, h))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, rad, rad)
            txt = QColor(C.on_accent)
        elif v == "danger":
            p.setPen(QPen(lerp(C.danger_border, C.red, h), 1))
            p.setBrush(lerp(C.danger_bg, C.danger_bg_h, h))
            p.drawRoundedRect(r, rad, rad)
            txt = QColor(C.red)
        elif v == "chip":
            on = self.isChecked()
            p.setPen(QPen(QColor(C.accent) if on else lerp(C.border, C.border_hi, h), 1))
            p.setBrush(QColor(C.chip_on) if on else lerp(C.card, C.card2, h))
            p.drawRoundedRect(r, rad, rad)
            txt = QColor(C.text) if on else lerp(C.muted, C.text, h)
        else:
            p.setPen(QPen(lerp(C.border, C.accent, h), 1))
            p.setBrush(lerp(C.card2, C.ghost_h, h))
            p.drawRoundedRect(r, rad, rad)
        p.setPen(txt)
        f = QFont(self.font())
        f.setBold(True)
        f.setPixelSize(15 if v == "accent" else 13)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignCenter, self.text())


class NavButton(QPushButton):
    """Sidebar-Eintrag: Icon-Kachel + Text, weicher Auswahl-Uebergang, Akzent-Balken waechst aus der Mitte."""

    def __init__(self, text: str, icon: str):
        super().__init__(text)
        self.icon_name = icon
        self.hv = HoverValue(self, 140)
        self.sel = HoverValue(self, 220)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)
        self.setFocusPolicy(Qt.NoFocus)
        self.toggled.connect(lambda on: self.sel.to(1 if on else 0))

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hv.to(0)
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h, sel = self.hv.v, self.sel.v
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if sel > 0.01:
            g = QLinearGradient(r.left(), 0, r.right(), 0)
            g.setColorAt(0, alpha(C.nav_on_a, int(255 * sel)))
            g.setColorAt(1, alpha(C.nav_on_b, int(255 * sel)))
            p.setPen(QPen(alpha(C.accent, int(60 * sel)), 1))
            p.setBrush(QBrush(g))
            p.drawRoundedRect(r, 12, 12)
            bh = r.height() * (0.18 + 0.42 * sel)
            p.setPen(Qt.NoPen)
            p.setBrush(alpha(C.accent2, int(255 * sel)))
            p.drawRoundedRect(QRectF(0, (self.height() - bh) / 2, 3.5, bh), 2, 2)
        if h > 0.01 and sel < 0.99:
            p.setPen(Qt.NoPen)
            p.setBrush(alpha(C.nav_hover, int(255 * h * (1 - sel))))
            p.drawRoundedRect(r, 12, 12)
        # Icon-Kachel
        box = QRectF(12 + 1.5 * h, (self.height() - 28) / 2, 28, 28)
        tile = lerp(alpha(C.card2, 0), alpha(C.accent, 46), max(sel, h * 0.5))
        p.setPen(Qt.NoPen)
        p.setBrush(tile)
        p.drawRoundedRect(box, 9, 9)
        col = lerp(lerp(C.muted, C.text, h), C.accent2, sel)
        draw_icon(p, self.icon_name, QRectF(box.left() + 5, box.top() + 5, 18, 18), col)
        p.setPen(lerp(lerp(C.muted, C.text, h), C.text, sel))
        f = QFont(self.font())
        f.setPixelSize(14)
        f.setWeight(QFont.DemiBold if sel > 0.5 else QFont.Medium)
        p.setFont(f)
        p.drawText(QRectF(52 + 1.5 * h, 0, self.width() - 60, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class IconButton(QPushButton):
    """Runder/abgerundeter Icon-Button (Settings, Discord ...) mit Glow, Hover-Anhebung und dezenter Icon-Animation."""

    def __init__(self, icon: str, text: str = "", tooltip: str = "", brand: bool = False, size: int = 40):
        super().__init__(text)
        self.icon_name, self.brand = icon, brand
        self.hv = HoverValue(self, 170)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setToolTip(tooltip)
        self.setFixedHeight(size)
        f = QFont(self.font())
        f.setBold(True)
        f.setPixelSize(13)
        w = QFontMetrics(f).horizontalAdvance(text) + 52 if text else size
        self.setFixedWidth(w)

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hv.to(0)
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.hv.v
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        rad = r.height() / 2 if self.text() else 12
        if h > 0.02:
            p.setPen(QPen(alpha(C.accent, int(70 * h)), 4))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(-0.5, -0.5, 0.5, 0.5), rad, rad)
        if self.brand:
            g = QLinearGradient(r.left(), 0, r.right(), 0)
            g.setColorAt(0, lerp(C.btn_a, C.btn_a_h, h))
            g.setColorAt(1, lerp(C.btn_b, C.btn_b_h, h))
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(g))
            fg = QColor(C.on_accent)
        else:
            p.setPen(QPen(lerp(C.border, C.accent, h), 1))
            p.setBrush(lerp(C.card2, C.ghost_h, h))
            fg = lerp(C.muted, C.text, h)
        p.drawRoundedRect(r, rad, rad)
        isz = 18
        cx = r.left() + (14 if self.text() else (r.width() - isz) / 2)
        p.save()
        c = QPointF(cx + isz / 2, r.center().y())
        p.translate(c)
        if self.icon_name == "gear":
            p.rotate(60 * h)
        else:
            sc = 1 + 0.10 * h
            p.scale(sc, sc)
        p.translate(-c)
        draw_icon(p, self.icon_name, QRectF(cx, r.center().y() - isz / 2, isz, isz), fg)
        p.restore()
        if self.text():
            p.setPen(fg)
            f = QFont(self.font())
            f.setBold(True)
            f.setPixelSize(13)
            p.setFont(f)
            p.drawText(QRectF(cx + isz + 8, 0, r.width() - isz - 26, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.text())


class IconTile(QWidget):
    """Kleine abgerundete Kachel mit Icon (Kategorie-Koepfe, Hardware-Karten)."""

    def __init__(self, icon: str, size: int = 34, color: str = "accent2"):
        super().__init__()
        self.icon_name, self.color = icon, color
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(QPen(alpha(C.accent, 60), 1))
        p.setBrush(alpha(C.accent, 38))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)
        pad = r.width() * 0.24
        draw_icon(p, self.icon_name, QRectF(pad, pad, r.width() - 2 * pad, r.height() - 2 * pad), resolve(self.color))


class GradientLine(QWidget):
    """Duenne Akzentlinie mit wanderndem Lichtreflex."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(3)
        self.pos = -0.3
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(5200)
        self.anim.setStartValue(-0.3)
        self.anim.setEndValue(1.3)
        self.anim.setLoopCount(-1)
        self.anim.valueChanged.connect(self._t)
        self.anim.start()

    def _t(self, v):
        self.pos = float(v)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        g = QLinearGradient(0, 0, self.width(), 0)
        g.setColorAt(0, QColor(C.accent))
        g.setColorAt(1, QColor(C.secondary))
        p.fillRect(self.rect(), QBrush(g))
        s = QLinearGradient(self.width() * (self.pos - 0.15), 0, self.width() * (self.pos + 0.15), 0)
        s.setColorAt(0, QColor(255, 255, 255, 0))
        s.setColorAt(0.5, QColor(255, 255, 255, 150))
        s.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(self.rect(), QBrush(s))


class Toggle(QAbstractButton):
    def __init__(self):
        super().__init__()
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(46, 26)
        self._pos = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)
        self.hv = HoverValue(self, 120)

    def _get(self) -> float:
        return self._pos

    def _set(self, v: float) -> None:
        self._pos = v
        self.update()

    offset = Property(float, _get, _set)

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hv.to(0)
        super().leaveEvent(e)

    def _animate(self, on: bool):
        self._anim.stop()
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def set_checked_silent(self, on: bool):
        self.blockSignals(True)
        self.setChecked(on)
        self.blockSignals(False)
        self._anim.stop()
        self._pos = 1.0 if on else 0.0
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        t = self._pos
        col = lerp(lerp(C.toggle_off, C.toggle_off_h, self.hv.v), C.accent, t)
        if not self.isEnabled():
            col.setAlpha(110)
        if self.hv.v > 0.02 and self.isEnabled() and t > 0.5:
            p.setPen(QPen(alpha(C.accent2, int(90 * self.hv.v)), 3))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(-0.5, -0.5, 0.5, 0.5), r.height() / 2, r.height() / 2)
        p.setPen(Qt.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.left() + 3 + (r.width() - d - 6) * t
        p.setBrush(QColor(C.knob if self.isEnabled() else C.knob_off))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class Chips(QWidget):
    changed = Signal(str)

    def __init__(self, names: list[str], current: Optional[str] = None):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.buttons: dict[str, AnimButton] = {}
        for n in names:
            b = AnimButton(n, "chip")
            b.clicked.connect(lambda _c=False, name=n: self.select(name))
            lay.addWidget(b)
            self.buttons[n] = b
        lay.addStretch(1)
        self.current = names[0]
        self.select(current or names[0], emit=False)

    def select(self, name: str, emit: bool = True):
        for n, b in self.buttons.items():
            b.setChecked(n == name)
            b.update()
        self.current = name
        if emit:
            self.changed.emit(name)


class RingGauge(QWidget):
    def __init__(self, c1: str = "accent", c2: str = "secondary", minimum: int = 140):
        super().__init__()
        self.c1, self.c2 = c1, c2
        self._target = 0.0
        self._shown = 0.0
        self.text = "–"
        self.sub = ""
        self.setMinimumSize(minimum, minimum)
        self._anim = QPropertyAnimation(self, b"shown", self)
        self._anim.setDuration(450)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def _g(self) -> float:
        return self._shown

    def _s(self, v: float) -> None:
        self._shown = v
        self.update()

    shown = Property(float, _g, _s)

    def set_value(self, frac: Optional[float], text: str, sub: str = ""):
        self.text, self.sub = text, sub
        frac = max(0.0, min(1.0, frac or 0.0))
        if abs(frac - self._target) > 0.004:
            self._target = frac
            self._anim.stop()
            self._anim.setStartValue(self._shown)
            self._anim.setEndValue(frac)
            self._anim.start()
        else:
            self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height())
        th = max(10, side * 0.085)
        r = QRectF((self.width() - side) / 2 + th, (self.height() - side) / 2 + th, side - 2 * th, side - 2 * th)
        p.setPen(QPen(QColor(C.track), th, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, 0, 360 * 16)
        t = self._shown
        col = lerp(resolve(self.c1), resolve(self.c2), t)
        if t > 0.8:
            col = lerp(col, C.red, (t - 0.8) / 0.2)
        if t > 0.004:
            p.setPen(QPen(alpha(col, 50), th * 1.9, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(r, 90 * 16, int(-360 * 16 * t))
            p.setPen(QPen(col, th, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(r, 90 * 16, int(-360 * 16 * t))
        p.setPen(QColor(C.text))
        f = QFont(self.font())
        f.setPixelSize(int(side * 0.22))
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(r.left(), r.top() + r.height() * 0.22, r.width(), r.height() * 0.36), Qt.AlignCenter, self.text)
        f.setPixelSize(max(10, int(side * 0.085)))
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(C.muted))
        p.drawText(QRectF(r.left(), r.top() + r.height() * 0.56, r.width(), r.height() * 0.2), Qt.AlignCenter, self.sub)


class LineChart(QWidget):
    def __init__(self, vmax: Optional[float] = 100.0, unit: str = "%", maxlen: int = 90, show_legend: bool = True):
        super().__init__()
        self.vmax, self.unit, self.maxlen, self.show_legend = vmax, unit, maxlen, show_legend
        self.series: dict[str, tuple[QColor, deque]] = {}
        self.setMinimumHeight(120)

    def add_series(self, name: str, color: str):
        self.series[name] = (QColor(color), deque(maxlen=self.maxlen))

    def push(self, name: str, value: Optional[float]):
        self.series[name][1].append(value)

    def set_data(self, name: str, values: list):
        self.series[name][1].clear()
        self.series[name][1].extend(values)
        self.update()

    def clear(self):
        for _c, d in self.series.values():
            d.clear()
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        top_pad, bot_pad = (30 if self.show_legend else 8), 8
        plot_h = max(10, h - top_pad - bot_pad)
        vals = [v for _c, d in self.series.values() for v in d if v is not None]
        vmax = self.vmax or max(max(vals, default=1.0) * 1.25, 1.0)
        p.setPen(QPen(QColor(C.grid), 1))
        for i in range(5):
            y = top_pad + plot_h * i / 4
            p.drawLine(QPointF(0, y), QPointF(w, y))
        p.setPen(QColor(C.dim))
        f = QFont(self.font())
        f.setPixelSize(10)
        p.setFont(f)
        p.drawText(QRectF(w - 70, top_pad - 14, 66, 12), Qt.AlignRight, f"{vmax:.0f}{self.unit}")
        x = 4
        for name, (col, data) in self.series.items():
            if self.show_legend:
                p.setBrush(col)
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(x + 4, 14), 4, 4)
                p.setPen(QColor(C.muted))
                f2 = QFont(self.font())
                f2.setPixelSize(12)
                p.setFont(f2)
                p.drawText(QPointF(x + 14, 18), name)
                x += 24 + QFontMetrics(f2).horizontalAdvance(name)
            pts = list(data)
            if len(pts) < 2:
                continue
            step = w / max(1, self.maxlen - 1)
            x0 = w - step * (len(pts) - 1)
            path = QPainterPath()
            started = False
            for i, v in enumerate(pts):
                px = x0 + i * step
                if v is None:
                    p.setPen(QPen(QColor(C.red), 2))
                    p.drawLine(QPointF(px, h - bot_pad), QPointF(px, h - bot_pad - 14))
                    started = False
                    continue
                py = top_pad + plot_h * (1 - min(1.0, v / vmax))
                if not started:
                    path.moveTo(px, py)
                    started = True
                else:
                    path.lineTo(px, py)
            if started and len(self.series) == 1:
                fill = QPainterPath(path)
                fill.lineTo(QPointF(w, h - bot_pad))
                fill.lineTo(QPointF(x0, h - bot_pad))
                g = QLinearGradient(0, top_pad, 0, h)
                g.setColorAt(0, alpha(col, 70))
                g.setColorAt(1, alpha(col, 0))
                p.setPen(Qt.NoPen)
                p.setBrush(g)
                p.drawPath(fill)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(alpha(col, 60), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)
            p.setPen(QPen(col, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(path)


class Sparkline(QWidget):
    """Kleine Verlaufslinie fuer Metrik-Karten."""

    def __init__(self, color: str = "accent", maxlen: int = 60, vmax: Optional[float] = 100.0):
        super().__init__()
        self.color_src, self.maxlen, self.vmax = color, maxlen, vmax
        self.data: deque = deque(maxlen=maxlen)
        self.setFixedHeight(46)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def push(self, v: float):
        self.data.append(v)
        self.update()

    def paintEvent(self, _e):
        if len(self.data) < 2:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        self.color = QColor(resolve(self.color_src))
        vmax = self.vmax or max(max(self.data), 1.0) * 1.2
        step = w / (self.maxlen - 1)
        x0 = w - step * (len(self.data) - 1)
        path = QPainterPath()
        for i, v in enumerate(self.data):
            x, y = x0 + i * step, h - 3 - (h - 8) * min(1.0, v / vmax)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        fill = QPainterPath(path)
        fill.lineTo(w, h)
        fill.lineTo(x0, h)
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, alpha(self.color, 80))
        g.setColorAt(1, alpha(self.color, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawPath(fill)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(self.color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(path)


class OrbBanner(Card):
    """Hero-Banner mit langsam wandernden Farb-Orbs (animiert nur, solange sichtbar)."""

    def __init__(self):
        super().__init__("hero")
        self.t0 = time.time()
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.update)

    def showEvent(self, e):
        self.timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self.timer.stop()
        super().hideEvent(e)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), self.radius, self.radius)
        p.setClipPath(path)
        t = time.time() - self.t0
        w, h = self.width(), self.height()
        for col, sp, ph in ((C.accent, 0.35, 0.0), (C.secondary, 0.27, 2.1), (C.tertiary, 0.21, 4.2)):
            cx = w * (0.25 + 0.5 * (0.5 + 0.5 * math.sin(t * sp + ph)))
            cy = h * (0.35 + 0.3 * math.sin(t * sp * 1.3 + ph))
            g = QRadialGradient(cx, cy, h * 1.1)
            g.setColorAt(0, alpha(col, 46))
            g.setColorAt(1, alpha(col, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(QPointF(cx, cy), h * 1.1, h * 1.1)


class StatTile(Card):
    def __init__(self, title: str, color: str = ""):
        super().__init__()
        color = resolve(color) if color else C.text
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(2)
        self.title = label(title.upper(), "dim")
        self.value = label("–", "big")
        self.value.setStyleSheet(f"color:{color};")
        self.sub = label("", "muted")
        for w in (self.title, self.value, self.sub):
            w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            lay.addWidget(w)

    def set(self, value: str, sub: str = ""):
        self.value.setText(value)
        self.sub.setText(sub)


class TweakRow(HoverFrame):
    """Eine Zeile: Wirkungs-Punkt, Name, EIN Satz, Tags, Schalter. Details im Tooltip."""
    toggled = Signal(str, bool)

    def __init__(self, tweak, admin_ok: bool):
        super().__init__(12)
        self.tweak = tweak
        self.locked = tweak.admin and not admin_ok
        self.unavailable = False
        self.setFixedHeight(68)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 16, 8)
        lay.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(8)
        if tweak.evidence:
            dot = QLabel()
            dot.setFixedSize(9, 9)
            dot.setStyleSheet(f"background:{evidence_color(tweak.evidence)};border-radius:4px;")
            dot.setToolTip(EVIDENCE_TEXT.get(tweak.evidence, ""))
            head.addWidget(dot)
        name = QLabel(tweak.name)
        name.setStyleSheet("font-size:14px;font-weight:600;")
        name.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        head.addWidget(name)
        if tweak.recommended:
            star = QLabel("★")
            star.setStyleSheet(f"color:{C.accent2};")
            star.setToolTip("Wird von Auto Optimize gesetzt")
            head.addWidget(star)
        head.addStretch(1)
        col.addLayout(head)
        col.addWidget(ElidedLabel(tweak.description, "muted"))
        lay.addLayout(col, 1)
        tags = QHBoxLayout()
        tags.setSpacing(6)
        for t in tweak.tags:
            tags.addWidget(pill(t, tag_color(t)))
        if tweak.risk != "niedrig":
            tags.addWidget(pill("RISIKO", C.yellow))
        if tweak.admin:
            tags.addWidget(pill("ADMIN", C.red if self.locked else C.dim))
        lay.addLayout(tags)
        self.toggle = Toggle()
        lay.addWidget(self.toggle)
        self.toggle.clicked.connect(lambda c: self.toggled.emit(self.tweak.id, bool(c)))
        tip = f"{tweak.description}\n\n{tweak.impact}"
        if tweak.evidence:
            tip += f"\n\n{EVIDENCE_TEXT.get(tweak.evidence, '')}"
        if tweak.restart and tweak.restart != "Nein":
            tip += f"\nWirksam: {tweak.restart}"
        if tweak.risk != "niedrig":
            tip += f"\nRisiko: {tweak.risk}"
        if self.locked:
            tip += "\n\nBraucht Administratorrechte."
            self.toggle.setEnabled(False)
        self.setToolTip(tip)

    def set_state(self, state: str, msg: str = ""):
        from engine import STATUS_ACTIVE, STATUS_UNKNOWN
        self.toggle.set_checked_silent(state == STATUS_ACTIVE)
        self.toggle.setEnabled(state != STATUS_UNKNOWN and not self.locked)
        self.unavailable = state == STATUS_UNKNOWN
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if self.unavailable:
            p = QPainter(self)
            p.setPen(Qt.NoPen)
            p.setBrush(alpha(C.overlay, 120))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1 - self.LIFT), 12, 12)


def make_scroll(widget: QWidget) -> QScrollArea:
    """Ganze Seite scrollt als Einheit; ein Mausrad-Schritt = etwa eine Zeile (normales Windows-Gefuehl)."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setWidget(widget)
    area.verticalScrollBar().setSingleStep(34)
    return area


def _colorref(h: str) -> int:
    c = QColor(h)
    return c.red() | (c.green() << 8) | (c.blue() << 16)


def apply_dark_titlebar(win: QWidget) -> None:
    """Titelleiste (Windows 10/11) passend zum aktiven Theme einfaerben; hell/dunkel folgt dem Theme."""
    if os.name != "nt":
        return
    try:
        import ctypes
        hwnd = int(win.winId())
        dwm = ctypes.windll.dwmapi

        def put(attr: int, val: int):
            v = ctypes.c_int(val)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
        dark = 0 if C.light else 1
        put(20, dark)                       # DWMWA_USE_IMMERSIVE_DARK_MODE
        put(19, dark)                       # aeltere Windows-10-Builds
        put(35, _colorref(C.sidebar))       # Titelleistenfarbe (Windows 11)
        put(36, _colorref(C.text))          # Titeltext
        put(34, _colorref(C.sidebar))       # Rahmenfarbe
    except Exception:  # noqa: BLE001
        pass
