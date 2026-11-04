"""SquallowTweaks - Einstiegspunkt."""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

if "--selftest" in sys.argv or "--shots" in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

import app as appmod
import service as svc
from design_page import get_manager
from ui_common import build_qss


def make_app() -> QApplication:
    qt = QApplication.instance() or QApplication(sys.argv)
    qt.setApplicationName(appmod.APP_NAME)
    qt.setWindowIcon(QIcon(appmod.asset("bird.png")))
    get_manager()                       # gespeichertes Theme laden, bevor das Stylesheet gebaut wird
    qt.setStyleSheet(build_qss())
    return qt


def pump(qt: QApplication, seconds: float) -> None:
    import time
    end = time.time() + seconds
    while time.time() < end:
        qt.processEvents()
        time.sleep(0.01)


def selftest() -> int:
    """Baut das komplette Fenster unsichtbar, rendert jede Seite und beendet sich (CI-Test der gebauten EXE)."""
    lines, problems = [], []
    try:
        qt = make_app()
        win = appmod.MainWindow()
        win.show()
        for name in win.pages:
            win.go(name)
            qt.processEvents()
            pm = win.grab()
            lines.append(f"OK    Seite {name}: {pm.width()}x{pm.height()}")
        # jedes Theme live anwenden (komplette UI wird neu aufgebaut) und alle Seiten rendern
        original = win.mgr.current
        for tname in win.mgr.names():
            win.mgr.set_theme(tname, persist=False)
            pump(qt, 0.25)
            if tname == "Chromatic":
                for _ in range(5):
                    win.root._tick()
            for name in list(win.pages):
                win.go(name)
                qt.processEvents()
                win.grab()
            lines.append(f"OK    Theme {tname}: alle {len(win.pages)} Seiten gerendert")
        win.go("Einstellungen")
        win.pages["Einstellungen"]._tab("Design")
        pump(qt, 0.1)
        win.grab()
        lines.append("OK    Design-Seite gerendert")
        dash = win.pages["Dashboard"]
        lines.append(f"OK    Applied-Counter: {dash.applied.value.text()} | Discord-URL: {dash.discord_btn is not None}")
        win.mgr.set_theme(original, persist=False)
        pump(qt, 0.25)
        win.close()
    except Exception:  # noqa: BLE001
        problems.append("ui")
        lines.append("FAIL  " + traceback.format_exc())
    try:
        svc.APP_DIR.mkdir(parents=True, exist_ok=True)
        (svc.APP_DIR / "selftest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    print("\n".join(lines))
    return 2 if problems else 0


def shots(out: str) -> int:
    """Entwickler-Hilfe: PNG-Screenshots aller Seiten."""
    from PySide6.QtCore import QTimer
    qt = make_app()
    win = appmod.MainWindow()
    win.show()
    Path(out).mkdir(parents=True, exist_ok=True)
    import time
    for name in win.pages:
        win.go(name)
        end = time.time() + (2.6 if name in ("Dashboard", "Prozesse") else 0.4)
        while time.time() < end:
            qt.processEvents()
            time.sleep(0.02)
        win.grab().save(str(Path(out) / f"{name}.png"))
    for tname in win.mgr.names():
        win.mgr.set_theme(tname, persist=False)
        pump(qt, 0.8)
        for name in ("Dashboard", "Tweaks"):
            win.go(name)
            pump(qt, 0.5)
            win.grab().save(str(Path(out) / f"Theme_{tname}_{name}.png"))
    win.go("Einstellungen")
    win.pages["Einstellungen"]._tab("Design")
    pump(qt, 0.5)
    win.grab().save(str(Path(out) / "Design.png"))
    win.close()
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    if "--shots" in sys.argv:
        return shots(sys.argv[sys.argv.index("--shots") + 1])
    qt = make_app()
    try:
        win = appmod.MainWindow()
    except Exception as exc:  # noqa: BLE001
        svc.log(f"Startfehler: {exc!r}\n{traceback.format_exc()}")
        QMessageBox.critical(None, appmod.APP_NAME, f"Start fehlgeschlagen:\n{exc}\n\nLog: {svc.LOG_FILE}")
        return 1
    win.show()
    return qt.exec()


if __name__ == "__main__":
    raise SystemExit(main())
