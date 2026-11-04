"""SquallowTweaks - DESIGN-Einstellungen: Theme-Auswahl, eigener Farbwaehler (HEX, Live-Vorschau), eigene Themes speichern."""
from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLineEdit, QVBoxLayout, QWidget

import service as svc
import theme
from theme import C, FX_LABELS, FX_LEVELS, FX_NAMES, ThemeManager
from ui_common import AnimButton, Card, Chips, HoverValue, alpha, label, lerp, pointer_inside, resolve

_MANAGER: Optional[ThemeManager] = None


def get_manager() -> ThemeManager:
    """Einziger ThemeManager der App (laedt beim ersten Aufruf die gespeicherten Einstellungen)."""
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = ThemeManager(svc.APP_DIR / "theme.json")
    return _MANAGER


# --------------------------------------------------------------------------
# Vorschau
# --------------------------------------------------------------------------
def _motif(p: QPainter, r: QRectF, t: dict) -> None:
    """Kleines statisches Erkennungsmerkmal je Effekt (damit Themes auf einen Blick unterscheidbar sind)."""
    fx, acc, acc2 = t["fx"], t["accent"], t["accent2"]
    p.save()
    p.setClipRect(r)
    p.setBrush(Qt.NoBrush)
    if fx == "matrix":
        p.setPen(QPen(alpha(acc, 120), 1.4, Qt.DotLine))
        for i in range(7):
            x = r.left() + r.width() * (0.08 + i * 0.14)
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.top() + r.height() * (0.35 + 0.5 * ((i * 37) % 10) / 10)))
    elif fx == "stars":
        p.setPen(Qt.NoPen)
        p.setBrush(alpha("#ffffff", 200))
        for i in range(14):
            p.drawEllipse(QPointF(r.left() + r.width() * ((i * 53 % 97) / 97), r.top() + r.height() * ((i * 29 % 89) / 89)), 0.9, 0.9)
    elif fx == "neon":
        p.setPen(QPen(alpha(acc, 60), 5))
        p.drawRoundedRect(r.adjusted(2, 2, -2, -2), 8, 8)
        p.setPen(QPen(alpha(acc2, 230), 1.2))
        p.drawRoundedRect(r.adjusted(2, 2, -2, -2), 8, 8)
    elif fx == "electric":
        path = QPainterPath(QPointF(r.left() + 4, r.bottom() - 6))
        for i, (dx, dy) in enumerate(((.18, -.4), (.30, .1), (.46, -.5), (.60, .0), (.78, -.55))):
            path.lineTo(QPointF(r.left() + r.width() * dx, r.bottom() - r.height() * (0.3 - dy * 0.5)))
        p.setPen(QPen(alpha(acc2, 70), 4))
        p.drawPath(path)
        p.setPen(QPen(alpha(acc2, 230), 1.2))
        p.drawPath(path)
    elif fx == "pulse":
        for k, a in ((0.5, 150), (0.8, 90), (1.1, 45)):
            p.setPen(QPen(alpha(acc, a), 1.4))
            p.drawEllipse(QPointF(r.left(), r.bottom()), r.height() * k, r.height() * k)
    elif fx == "energy":
        for i in range(4):
            y = r.top() + r.height() * (0.2 + i * 0.2)
            g = QLinearGradient(r.left(), y, r.right(), y - 18)
            g.setColorAt(0, alpha(acc, 0))
            g.setColorAt(0.6, alpha(acc2, 190))
            g.setColorAt(1, alpha(acc, 0))
            p.setPen(QPen(QBrush(g), 1.4))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y - 18))
    elif fx == "holo":
        p.setPen(QPen(alpha(acc2, 55), 1))
        for i in range(int(r.height() / 4)):
            p.drawLine(QPointF(r.left(), r.top() + i * 4), QPointF(r.right(), r.top() + i * 4))
        g = QLinearGradient(0, r.top() + r.height() * 0.35, 0, r.top() + r.height() * 0.6)
        g.setColorAt(0, alpha(acc2, 0))
        g.setColorAt(0.5, alpha(acc2, 120))
        g.setColorAt(1, alpha(acc2, 0))
        p.fillRect(QRectF(r.left(), r.top() + r.height() * 0.35, r.width(), r.height() * 0.25), QBrush(g))
    elif fx == "glass":
        g = QLinearGradient(r.left(), r.top(), r.right(), r.bottom())
        g.setColorAt(0, alpha("#ffffff", 0))
        g.setColorAt(0.45, alpha("#ffffff", 44))
        g.setColorAt(0.6, alpha("#ffffff", 0))
        p.fillRect(r, QBrush(g))
    elif fx in ("softlight", "chromatic"):
        for i, col in enumerate((acc, t["secondary"], t["tertiary"])):
            c = QPointF(r.left() + r.width() * (0.2 + 0.3 * i), r.top() + r.height() * (0.3 + 0.25 * (i % 2)))
            g = QRadialGradient(c, r.height() * 0.8)
            g.setColorAt(0, alpha(col, 90))
            g.setColorAt(1, alpha(col, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(c, r.height() * 0.8, r.height() * 0.8)
    p.restore()


class ThemePreview(QWidget):
    """Miniatur der App (Sidebar, Karten, Button, Schalter, Diagramm) im uebergebenen Theme."""

    def __init__(self, tokens: dict, size: tuple[int, int] = (168, 100)):
        super().__init__()
        self.t = tokens
        self.setMinimumSize(*size)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def set_tokens(self, tokens: dict) -> None:
        self.t = tokens
        self.update()

    def paintEvent(self, _e):
        t = self.t
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        clip = QPainterPath()
        clip.addRoundedRect(r, 10, 10)
        p.setClipPath(clip)
        p.fillRect(r, QColor(t["bg"]))
        _motif(p, r, t)
        side = QRectF(r.left(), r.top(), r.width() * 0.2, r.height())
        p.fillRect(side, QColor(t["sidebar"]))
        for i in range(4):
            y = r.top() + 10 + i * 13
            on = i == 0
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(t["nav_on_a"]) if on else QColor(t["card2"]))
            p.drawRoundedRect(QRectF(side.left() + 5, y, side.width() - 10, 8), 3, 3)
            if on:
                p.setBrush(QColor(t["accent2"]))
                p.drawRoundedRect(QRectF(side.left() + 1, y + 1, 2, 6), 1, 1)
        x0 = side.right() + 8
        w = r.right() - x0 - 8
        card = QRectF(x0, r.top() + 10, w, r.height() * 0.34)
        p.setPen(QPen(QColor(t["border"]), 1))
        fill = QColor(t["hero_a"])
        p.setBrush(fill)
        p.drawRoundedRect(card, 7, 7)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t["text"]))
        p.drawRoundedRect(QRectF(card.left() + 7, card.top() + 7, card.width() * 0.4, 4), 2, 2)
        p.setBrush(QColor(t["muted"]))
        p.drawRoundedRect(QRectF(card.left() + 7, card.top() + 15, card.width() * 0.6, 3), 1.5, 1.5)
        g = QLinearGradient(card.left(), 0, card.right(), 0)
        g.setColorAt(0, QColor(t["btn_a"]))
        g.setColorAt(1, QColor(t["btn_b"]))
        p.setBrush(g)
        p.drawRoundedRect(QRectF(card.left() + 7, card.bottom() - 11, card.width() * 0.3, 6), 3, 3)
        c2 = QRectF(x0, card.bottom() + 7, w, r.bottom() - card.bottom() - 15)
        p.setPen(QPen(QColor(t["border"]), 1))
        p.setBrush(QColor(t["card"]))
        p.drawRoundedRect(c2, 7, 7)
        path = QPainterPath()
        for i in range(8):
            px = c2.left() + 7 + (c2.width() - 14) * i / 7
            py = c2.bottom() - 6 - (c2.height() - 12) * (0.3 + 0.55 * abs(math.sin(i * 1.3 + 0.4)))
            path.moveTo(px, py) if i == 0 else path.lineTo(px, py)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(t["accent2"]), 1.6))
        p.drawPath(path)
        tg = QRectF(c2.right() - 24, c2.top() + 5, 17, 9)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t["accent"]))
        p.drawRoundedRect(tg, 4.5, 4.5)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(tg.right() - 4.5, tg.center().y()), 3, 3)


class ThemeCard(QWidget):
    """Klickbare Theme-Kachel (Vorschau + Name + Effekt). Optional mit Loesch-Kreuz fuer eigene Themes."""
    picked = Signal(str)
    deleted = Signal(str)

    def __init__(self, name: str, tokens: dict, selected: bool, deletable: bool = False):
        super().__init__()
        self.name, self.t, self.selected, self.deletable = name, tokens, selected, deletable
        self.hv = HoverValue(self, 150)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(148)
        self.setMinimumWidth(150)
        v = QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(4)
        self.prev = ThemePreview(tokens)
        v.addWidget(self.prev, 1)
        row = QHBoxLayout()
        nm = label(name, "h2")
        nm.setStyleSheet("font-size:13px;font-weight:700;")
        nm.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        fx = label(FX_LABELS.get(tokens["fx"], ""), "dim")
        fx.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row.addWidget(nm)
        row.addStretch(1)
        row.addWidget(fx)
        v.addLayout(row)

    def enterEvent(self, e):
        self.hv.to(1)
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not pointer_inside(self):
            self.hv.to(0)
        super().leaveEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.hv.v
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(C.accent) if self.selected else lerp(C.border, C.accent, h * 0.8), 2 if self.selected else 1))
        p.setBrush(lerp(C.card, C.card2, h))
        p.drawRoundedRect(r, 12, 12)
        if self.deletable:
            p.setPen(QPen(QColor(C.red if h > 0.5 else C.muted), 1.6, Qt.SolidLine, Qt.RoundCap))
            cx, cy = r.right() - 16, r.top() + 16
            p.setBrush(alpha(C.card, 220))
            p.drawEllipse(QPointF(cx, cy), 9, 9)
            p.drawLine(QPointF(cx - 3, cy - 3), QPointF(cx + 3, cy + 3))
            p.drawLine(QPointF(cx - 3, cy + 3), QPointF(cx + 3, cy - 3))

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self.rect().contains(e.position().toPoint()):
            return
        pos = e.position()
        if self.deletable and pos.x() > self.width() - 30 and pos.y() < 30:
            self.deleted.emit(self.name)
        else:
            self.picked.emit(self.name)


# --------------------------------------------------------------------------
# Farbwaehler
# --------------------------------------------------------------------------
class ColorPicker(QWidget):
    """Visueller Farbwaehler: Saettigung/Helligkeit-Feld + Farbton-Leiste. Signal changed(hex) bei Mausbedienung."""
    changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.h, self.s, self.v = 0.7, 0.6, 0.9
        self._drag: Optional[str] = None
        self.setMinimumSize(240, 190)
        self.setCursor(Qt.CrossCursor)

    def set_color(self, hex_color: str) -> None:
        hh, ss, vv = theme.to_hsv(hex_color)
        if ss > 0.001 and vv > 0.001:
            self.h = hh
        self.s, self.v = ss, vv
        self.update()

    def color(self) -> str:
        return theme.from_hsv(self.h, self.s, self.v)

    def _sv(self) -> QRectF:
        return QRectF(0, 0, self.width(), self.height() - 28)

    def _hue(self) -> QRectF:
        return QRectF(0, self.height() - 16, self.width(), 14)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        sv, hu = self._sv(), self._hue()
        clip = QPainterPath()
        clip.addRoundedRect(sv, 10, 10)
        p.save()
        p.setClipPath(clip)
        p.fillRect(sv, QColor(theme.from_hsv(self.h, 1, 1)))
        g1 = QLinearGradient(sv.left(), 0, sv.right(), 0)
        g1.setColorAt(0, QColor(255, 255, 255, 255))
        g1.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(sv, QBrush(g1))
        g2 = QLinearGradient(0, sv.top(), 0, sv.bottom())
        g2.setColorAt(0, QColor(0, 0, 0, 0))
        g2.setColorAt(1, QColor(0, 0, 0, 255))
        p.fillRect(sv, QBrush(g2))
        p.restore()
        cx, cy = sv.left() + self.s * sv.width(), sv.top() + (1 - self.v) * sv.height()
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 160), 3))
        p.drawEllipse(QPointF(cx, cy), 8, 8)
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.drawEllipse(QPointF(cx, cy), 8, 8)
        hg = QLinearGradient(hu.left(), 0, hu.right(), 0)
        for i in range(7):
            hg.setColorAt(i / 6, QColor(theme.from_hsv(i / 6, 1, 1)))
        p.setPen(Qt.NoPen)
        p.setBrush(hg)
        p.drawRoundedRect(hu, 7, 7)
        hx = hu.left() + self.h * hu.width()
        p.setPen(QPen(QColor(0, 0, 0, 160), 3))
        p.setBrush(QColor(theme.from_hsv(self.h, 1, 1)))
        p.drawEllipse(QPointF(hx, hu.center().y()), 8, 8)
        p.setPen(QPen(QColor("#ffffff"), 2))
        p.drawEllipse(QPointF(hx, hu.center().y()), 8, 8)

    def _apply(self, pos: QPointF) -> None:
        if self._drag == "sv":
            r = self._sv()
            self.s = max(0.0, min(1.0, (pos.x() - r.left()) / r.width()))
            self.v = 1.0 - max(0.0, min(1.0, (pos.y() - r.top()) / r.height()))
        elif self._drag == "hue":
            r = self._hue()
            self.h = max(0.0, min(0.999, (pos.x() - r.left()) / r.width()))
        self.update()
        self.changed.emit(self.color())

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        self._drag = "hue" if e.position().y() >= self.height() - 24 else "sv"
        self._apply(e.position())

    def mouseMoveEvent(self, e):
        if self._drag:
            self._apply(e.position())

    def mouseReleaseEvent(self, _e):
        self._drag = None


class ColorField(QWidget):
    """Eine Farbe: Beschriftung, Farbfeld (waehlt sie fuer den Picker) und HEX-Eingabe."""
    selected = Signal(int)
    edited = Signal(int, str)

    def __init__(self, index: int, title: str, color: str):
        super().__init__()
        self.index, self.color, self.active = index, color, False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(54)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(46, 6, 8, 6)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(label(title.upper(), "dim"))
        self.edit = QLineEdit(color.upper())
        self.edit.setMaxLength(7)
        self.edit.setFixedHeight(28)
        self.edit.setStyleSheet("padding:3px 8px;border-radius:7px;font-family:Consolas,monospace;")
        self.edit.textEdited.connect(self._typed)
        col.addWidget(self.edit)
        lay.addLayout(col, 1)

    def _typed(self, text: str) -> None:
        hx = theme.norm_hex(text if text.startswith("#") else "#" + text)
        ok = hx is not None and len(text.lstrip("#")) in (3, 6)
        self.edit.setStyleSheet("padding:3px 8px;border-radius:7px;font-family:Consolas,monospace;" + ("" if ok else f"color:{C.red};"))
        if ok:
            self.selected.emit(self.index)
            self.set_color(hx, from_user=True)
            self.edited.emit(self.index, hx)

    def set_color(self, hx: str, from_user: bool = False) -> None:
        self.color = hx
        if not from_user:
            self.edit.setText(hx.upper())
        self.update()

    def set_active(self, on: bool) -> None:
        self.active = on
        self.update()

    def mousePressEvent(self, e):
        self.selected.emit(self.index)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(C.accent) if self.active else QColor(C.border), 1.5 if self.active else 1))
        p.setBrush(QColor(C.card2) if self.active else QColor(C.card))
        p.drawRoundedRect(r, 10, 10)
        p.setPen(QPen(QColor(C.border_hi), 1))
        p.setBrush(QColor(self.color))
        p.drawRoundedRect(QRectF(10, (self.height() - 28) / 2, 28, 28), 8, 8)


# --------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------
class DesignPanel(QWidget):
    LABELS = ("Primary", "Secondary", "Accent", "Background")

    def __init__(self):
        super().__init__()
        self.mgr = get_manager()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        # --- Themes
        lay.addWidget(label("Themes", "h2"))
        lay.addWidget(label("Ein Klick wechselt das komplette Aussehen sofort und wird für den nächsten Start gespeichert.", "muted", True))
        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        self.cards: dict[str, ThemeCard] = {}
        names = self.mgr.names()
        for i, n in enumerate(names):
            self._add_card(i, n, deletable=n in self.mgr.saved)
        if self.mgr.current == "Custom":
            self._add_card(len(names), "Custom", deletable=False)
        lay.addLayout(self.grid)

        # --- Effekte
        fxrow = Card()
        fl = QHBoxLayout(fxrow)
        fl.setContentsMargins(20, 14, 20, 14)
        col = QVBoxLayout()
        col.addWidget(label("Theme-Effekte", "h2"))
        col.addWidget(label("Animierte Hintergrund-Effekte je Theme. „Reduziert“ spart Leistung, „Aus“ zeigt nur Farben.", "muted", True))
        fl.addLayout(col, 1)
        self.fx_chips = Chips(list(FX_LEVELS.values()), FX_LEVELS[self.mgr.fx_level])
        self.fx_chips.changed.connect(self._fx_level)
        fl.addWidget(self.fx_chips)
        lay.addWidget(fxrow)

        # --- Eigener Farbwaehler
        lay.addWidget(label("Eigene Farben", "h2"))
        box = Card()
        box.hover_on = False
        bl = QHBoxLayout(box)
        bl.setContentsMargins(20, 18, 20, 18)
        bl.setSpacing(20)
        left = QVBoxLayout()
        left.setSpacing(8)
        cur = self.mgr.custom
        start = (cur["primary"], cur["secondary"], cur["accent"], cur["background"])
        self.colors = list(start)
        self.fields: list[ColorField] = []
        for i, nm in enumerate(self.LABELS):
            f = ColorField(i, nm, start[i])
            f.selected.connect(self._select)
            f.edited.connect(self._hex_edited)
            left.addWidget(f)
            self.fields.append(f)
        self.picker = ColorPicker()
        self.picker.changed.connect(self._picked)
        left.addSpacing(4)
        left.addWidget(self.picker)
        bl.addLayout(left, 2)
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(label("Live-Vorschau", "h2"))
        self.preview = ThemePreview(self.mgr.preview_tokens(*self.colors, fx=cur.get("fx", "glass")), (300, 180))
        right.addWidget(self.preview, 1)
        right.addWidget(label("Effekt für dein Theme", "dim"))
        fx_list = [FX_LABELS[f] for f in FX_NAMES]
        self.fx_pick = Chips(fx_list[:6], FX_LABELS.get(cur.get("fx", "glass"), "Glas"))
        self.fx_pick2 = Chips(fx_list[6:], None)
        for b in self.fx_pick2.buttons.values():
            b.setChecked(False)
        self.custom_fx = cur.get("fx", "glass")
        self.fx_pick.changed.connect(lambda n: self._custom_fx(n, 1))
        self.fx_pick2.changed.connect(lambda n: self._custom_fx(n, 2))
        right.addWidget(self.fx_pick)
        right.addWidget(self.fx_pick2)
        btns = QHBoxLayout()
        btns.setSpacing(10)
        apply_btn = AnimButton("Anwenden", "accent")
        apply_btn.clicked.connect(self._apply)
        btns.addWidget(apply_btn)
        reset = AnimButton("Zurücksetzen", "ghost")
        reset.clicked.connect(self._reset)
        btns.addWidget(reset)
        btns.addStretch(1)
        right.addLayout(btns)
        save = QHBoxLayout()
        save.setSpacing(10)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Name für dein Theme …")
        self.name_edit.setMaxLength(24)
        save.addWidget(self.name_edit, 1)
        sb = AnimButton("Theme speichern", "ghost")
        sb.clicked.connect(self._save)
        save.addWidget(sb)
        right.addLayout(save)
        self.msg = label("", "muted", True)
        right.addWidget(self.msg)
        bl.addLayout(right, 3)
        lay.addWidget(box)
        self.active = 0
        self._select(0)

    # --- Karten
    def _add_card(self, i: int, name: str, deletable: bool) -> None:
        c = ThemeCard(name, self.mgr.tokens_of(name), name == self.mgr.current, deletable)
        c.picked.connect(self._choose)
        c.deleted.connect(self._delete)
        self.grid.addWidget(c, i // 5, i % 5)
        self.cards[name] = c

    def _choose(self, name: str) -> None:
        self.mgr.set_theme(name)

    def _delete(self, name: str) -> None:
        self.mgr.delete_saved(name)

    def _fx_level(self, label_text: str) -> None:
        for k, v in FX_LEVELS.items():
            if v == label_text:
                self.mgr.set_fx_level(k)

    # --- Editor
    def _select(self, i: int) -> None:
        self.active = i
        for k, f in enumerate(self.fields):
            f.set_active(k == i)
        self.picker.set_color(self.colors[i])

    def _picked(self, hx: str) -> None:
        self.colors[self.active] = hx
        self.fields[self.active].set_color(hx)
        self._refresh_preview()

    def _hex_edited(self, i: int, hx: str) -> None:
        self.colors[i] = hx
        if i == self.active:
            self.picker.set_color(hx)
        self._refresh_preview()

    def _custom_fx(self, label_text: str, row: int) -> None:
        for fx, lab in FX_LABELS.items():
            if lab == label_text:
                self.custom_fx = fx
        other = self.fx_pick2 if row == 1 else self.fx_pick
        for b in other.buttons.values():
            b.setChecked(False)
            b.update()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        self.preview.set_tokens(self.mgr.preview_tokens(*self.colors, fx=self.custom_fx))

    def _reset(self) -> None:
        spec = self.mgr.spec_of(self.mgr.current)
        base = (spec["accent"], spec["secondary"], spec["accent2"], spec["bg"])
        self.colors = list(base)
        for f, c in zip(self.fields, base):
            f.set_color(c)
        self._select(self.active)
        self._refresh_preview()
        self.msg.setText("Farben vom aktuellen Theme übernommen.")

    def _apply(self) -> None:
        if self.mgr.set_custom(*self.colors, fx=self.custom_fx, activate=True):
            self.msg.setText("Eigenes Theme angewendet und gespeichert.")
        else:
            self.msg.setText("Ungültige Farbe. Bitte HEX wie #8B7CF6 eingeben.")

    def _save(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            self.msg.setText("Bitte zuerst einen Namen eingeben.")
            return
        if not self.mgr.set_custom(*self.colors, fx=self.custom_fx, activate=False):
            self.msg.setText("Ungültige Farbe.")
            return
        if self.mgr.save_custom_as(name) is None:
            self.msg.setText("Dieser Name ist nicht erlaubt (Standard-Themes sind geschützt).")
