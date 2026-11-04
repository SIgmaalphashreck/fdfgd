"""SquallowTweaks - Hauptfenster (Sidebar, Seiten, Live-Theme-Wechsel)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QApplication, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget)

import pages_a
import pages_b
import service as svc
from design_page import get_manager
from fx import FxRoot
from theme import C
from ui_common import (GradientLine, IconButton, NavButton, apply_dark_titlebar, build_qss, label, make_scroll, pill, tinted_pixmap)

APP_NAME = "SquallowTweaks"
VERSION = "1.2.0"


def asset(name: str) -> str:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return str(base / "assets" / name)


class FadeStack(QStackedWidget):
    """Seitenwechsel mit kurzem Fade-In (nur waehrend der Animation aktiv, danach kein Effekt mehr = keine Dauerlast)."""

    def __init__(self):
        super().__init__()
        self._anim = None

    def fade_to(self, widget: QWidget) -> None:
        if widget is self.currentWidget():
            return
        self.setCurrentWidget(widget)
        eff = QGraphicsOpacityEffect(widget)
        eff.setOpacity(0.0)
        widget.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", widget)
        anim.setDuration(150)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda w=widget: w.setGraphicsEffect(None))
        self._anim = anim
        anim.start()


class MainWindow(QMainWindow):
    # (Bereich, [(Name, Icon)]) - der Ping-Monitor ("Netzwerk") bleibt als Unterseite der Tweaks erreichbar
    NAV = (("ÜBERSICHT", (("Dashboard", "dashboard"),)),
           ("OPTIMIERUNG", (("Tweaks", "bolt"), ("Fortnite", "target"), ("Benchmark", "bench"))),
           ("SYSTEM", (("Prozesse", "list"), ("Bereinigung", "trash"), ("Einstellungen", "gear"))))
    SCROLLING = ("Tweaks", "Fortnite", "Benchmark", "Netzwerk", "Bereinigung", "Einstellungen")
    PARENT_NAV = {"Netzwerk": "Tweaks"}

    def __init__(self):
        super().__init__()
        self.mgr = get_manager()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(asset("bird.png")))
        self.resize(1320, 840)
        self.setMinimumSize(1120, 720)
        self.service = svc.Service()
        self._current = "Dashboard"
        self._rebuild_pending = False
        self._theme_key = self._key()
        self.setCentralWidget(self._build_ui())
        self.sampler = svc.Sampler()
        self.sampler.sample.connect(self.on_sample)
        self.sampler.procs.connect(self._on_procs)
        self.sampler.start()
        self.service.refresh_states()
        self.go("Dashboard")
        self.mgr.subscribe(self._theme_changed)

    # ------------------------------------------------------------------ Aufbau
    def _build_ui(self) -> QWidget:
        root = FxRoot(self.mgr)
        self.root = root
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(GradientLine())
        body = QHBoxLayout()
        body.setSpacing(0)
        outer.addLayout(body, 1)
        body.addWidget(self._sidebar())
        self.stack = FadeStack()
        s = self.service
        self.pages = {
            "Dashboard": pages_a.DashboardPage(s), "Tweaks": pages_a.TweaksPage(s), "Fortnite": pages_a.FortnitePage(s),
            "Benchmark": pages_a.BenchmarkPage(s), "Prozesse": pages_b.ProcessesPage(s), "Netzwerk": pages_b.NetworkPage(s),
            "Bereinigung": pages_b.CleanPage(s), "Einstellungen": pages_b.SettingsPage(s),
        }
        self.holders = {}
        for name, page in self.pages.items():
            page.navigate.connect(self.go)
            holder = make_scroll(page) if name in self.SCROLLING else page
            self.holders[name] = holder
            self.stack.addWidget(holder)
        body.addWidget(self.stack, 1)
        return root

    def _sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(236)
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 20, 14, 16)
        v.setSpacing(3)
        logo = QHBoxLayout()
        logo.setContentsMargins(6, 0, 0, 12)
        logo.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(tinted_pixmap(asset("bird.png"), 44))
        logo.addWidget(icon)
        name = QVBoxLayout()
        name.setSpacing(0)
        t1 = QLabel(f"Squallow<span style='color:{C.accent2};'>Tweaks</span>")
        t1.setTextFormat(Qt.RichText)
        t1.setStyleSheet("font-size:15px;font-weight:700;")
        name.addWidget(t1)
        name.addWidget(label(f"v{VERSION}", "dim"))
        logo.addLayout(name)
        logo.addStretch(1)
        v.addLayout(logo)
        self.nav_buttons: dict[str, NavButton] = {}
        for section, items in self.NAV:
            sec = label(section, "section")
            sec.setContentsMargins(10, 14, 0, 6)
            v.addWidget(sec)
            for text, ico in items:
                b = NavButton(text, ico)
                b.clicked.connect(lambda _c=False, n=text: self.go(n))
                v.addWidget(b)
                self.nav_buttons[text] = b
        v.addStretch(1)
        dc = QHBoxLayout()
        dc.setContentsMargins(0, 0, 0, 6)
        self.side_discord = IconButton("discord", "Discord beitreten", "Squallow Discord öffnen", brand=True, size=42)
        self.side_discord.setFixedWidth(206)
        self.side_discord.clicked.connect(lambda: __import__("webbrowser").open(pages_a.DISCORD_URL))
        dc.addWidget(self.side_discord)
        v.addLayout(dc)
        row = QHBoxLayout()
        row.setContentsMargins(6, 0, 0, 0)
        row.addWidget(pill("ADMIN" if self.service.admin else "KEIN ADMIN", C.green if self.service.admin else C.red))
        row.addWidget(pill(self.mgr.current.upper(), C.accent2))
        row.addStretch(1)
        v.addLayout(row)
        return side

    # ------------------------------------------------------------------ Navigation
    def go(self, name: str):
        self._current = name
        active = self.PARENT_NAV.get(name, name)
        for n, b in self.nav_buttons.items():
            b.setChecked(n == active)
        self.stack.fade_to(self.holders[name])
        self.sampler.want_procs = name == "Prozesse"
        if name == "Fortnite":
            self.pages["Fortnite"].refresh()
        if name == "Netzwerk":
            if not self.pages["Netzwerk"].monitor:
                self.pages["Netzwerk"].start()
        else:
            self.pages["Netzwerk"].stop()

    # ------------------------------------------------------------------ Theme live wechseln
    def _key(self) -> str:
        spec = self.mgr.spec_of(self.mgr.current)
        spec.pop("glass", None)
        return json.dumps([self.mgr.current, spec], sort_keys=True)

    def _theme_changed(self) -> None:
        key = self._key()
        if key == self._theme_key:                 # z. B. nur Effekt-Stufe geaendert
            self.root.sync()
            return
        self._theme_key = key
        if not self._rebuild_pending:
            self._rebuild_pending = True
            QTimer.singleShot(0, self._rebuild)    # erst nach dem Klick-Handler, damit kein Widget im eigenen Slot geloescht wird

    def _rebuild(self) -> None:
        if self.service.busy:                      # laufende Tweak-Aktion nicht stoeren
            QTimer.singleShot(400, self._rebuild)
            return
        self._rebuild_pending = False
        try:
            self.pages["Netzwerk"].shutdown()
        except Exception:  # noqa: BLE001
            pass
        QApplication.instance().setStyleSheet(build_qss())
        self.setCentralWidget(self._build_ui())     # alte Oberflaeche wird von Qt geloescht
        apply_dark_titlebar(self)
        self.go(self._current)
        self.update()

    # ------------------------------------------------------------------ Messwerte
    def _on_procs(self, rows):
        self.pages["Prozesse"].on_procs(rows)

    def on_sample(self, d: dict):
        self.service.fortnite_running = bool(d.get("fn"))
        self.pages["Dashboard"].on_sample(d)
        self.pages["Prozesse"].on_sample(d)
        self.sampler.auto_high = self.pages["Fortnite"].prio_on
        if self.stack.currentWidget() is self.holders["Fortnite"]:
            self.pages["Fortnite"].refresh()

    def showEvent(self, e):
        super().showEvent(e)
        apply_dark_titlebar(self)

    def closeEvent(self, e):
        self.sampler.stop()
        self.pages["Netzwerk"].shutdown()
        self.sampler.wait(2500)
        super().closeEvent(e)
