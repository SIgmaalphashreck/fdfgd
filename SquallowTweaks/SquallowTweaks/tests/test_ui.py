"""UI-Smoke-Test: baut das komplette Fenster unsichtbar und rendert jede Seite."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
_tmp = tempfile.mkdtemp()
os.environ["LOCALAPPDATA"] = _tmp          # Testdaten nicht in den echten Benutzerordner schreiben
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from PySide6.QtWidgets import QApplication
    HAVE_QT = True
except Exception:  # noqa: BLE001
    HAVE_QT = False


@unittest.skipUnless(HAVE_QT, "PySide6 nicht installiert")
class UiSmoke(unittest.TestCase):
    def test_all_pages_render_and_filters_work(self):
        import service as svc
        svc.IS_WINDOWS = False                 # Fake-Registry statt echter Registry
        import app as appmod
        from main import make_app
        qt = make_app()
        win = appmod.MainWindow()
        win.show()
        for name in win.pages:
            win.go(name)
            qt.processEvents()
            self.assertGreater(win.grab().width(), 800, name)
        tw = win.pages["Tweaks"].list
        for f in ("Empfohlen", "Belegt", "FPS", "Latenz", "Ping", "Aktiv", "Alle"):
            tw._f(f)
        tw._q("vollbild")
        visible = [r.tweak.id for r in tw.rows.values() if not r.isHidden()]
        self.assertTrue(visible and all("vollbild" in (r.tweak.name + r.tweak.description + " ".join(r.tweak.tags)).lower()
                                        for r in tw.rows.values() if not r.isHidden()))
        pr = win.pages["Prozesse"]
        procs = [("chrome.exe", 10, 5.0, 300.0, 20), ("chrome.exe", 11, 3.0, 200.0, 10), ("Fortnite.exe", 12, 20.0, 4000.0, 90)]
        rows = {r["name"]: r for r in pr.build_rows(procs)}
        self.assertEqual(rows["chrome.exe"]["count"], 2)
        self.assertAlmostEqual(rows["chrome.exe"]["cpu"], 8.0)
        self.assertEqual(rows["chrome.exe"]["cat"], "browser")
        self.assertEqual(rows["Fortnite.exe"]["cat"], "game")
        pr.group_chips.select("Einzeln")
        self.assertEqual(len(pr.build_rows(procs)), 3)
        win.close()

    def test_themes_dashboard_network_integration_and_buttons(self):
        import service as svc
        svc.IS_WINDOWS = False
        import app as appmod
        import pages_a
        from main import make_app, pump
        qt = make_app()
        win = appmod.MainWindow()
        win.show()
        # Netzwerk-Tweaks sind im Tweaks-Tab gruppiert; separater Network-Tab ist aus der Sidebar entfernt
        self.assertNotIn("Netzwerk", win.nav_buttons)
        head, ids = win.pages["Tweaks"].list.groups["Netzwerk"]
        self.assertEqual(set(ids), {"net_adapter_stable", "net_throttle_off", "delivery_opt_off", "net_interrupt_mod_off"})
        # alle Themes live wechseln
        for name in win.mgr.names():
            win.mgr.set_theme(name, persist=False)
            pump(qt, 0.15)
            win.go("Dashboard")
            qt.processEvents()
            self.assertGreater(win.grab().width(), 800, name)
        # Applied-Counter
        dash = win.pages["Dashboard"]
        self.assertTrue(dash.applied.value.text())
        # Settings-Button oeffnet die vorhandene Settings-Seite
        dash.settings_btn.click()
        self.assertEqual(win._current, "Einstellungen")
        # Discord-Button oeffnet den Einladungslink
        import webbrowser
        opened = []
        orig = webbrowser.open
        webbrowser.open = lambda url, *a, **k: opened.append(url)
        try:
            win.go("Dashboard")
            win.pages["Dashboard"].discord_btn.click()
        finally:
            webbrowser.open = orig
        self.assertEqual(opened, ["https://discord.gg/6dDvaPA2n"])
        self.assertEqual(pages_a.DISCORD_URL, "https://discord.gg/6dDvaPA2n")
        win.close()


if __name__ == "__main__":
    unittest.main()
