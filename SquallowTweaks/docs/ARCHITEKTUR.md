# Squallow Tweaks – Architektur-Analyse (Phase 1)

Stand: Originalstand v1.1.0, unverändert. Backup: `SquallowTweaks_BACKUP_original.zip`.

## Technik
- Python 3.12, **PySide6** (Qt Widgets), `psutil`. Keine Webtechnik, kein Framework außer Qt.
- Build: GitHub Actions (`build-windows.yml`) → PyInstaller `--onefile --windowed --uac-admin`, Self-Test der EXE (`--selftest`), optional PresentMon.
- ~5.460 Zeilen, 8 Testdateien (59 Tests, alle grün; UI-Tests brauchen PySide6).

## Schichten
| Datei | Aufgabe |
|---|---|
| `main.py` | Einstieg, `--selftest`, `--shots`, globales QSS |
| `app.py` | `MainWindow`: Sidebar (feste 232 px, Sektionen ÜBERSICHT/OPTIMIERUNG/SYSTEM), `QStackedWidget`, Seiten-Wechsel |
| `pages_a.py` | Dashboard, `TweaksList`, `TweaksPage`, Fortnite, Benchmark |
| `pages_b.py` | Prozesse, Netzwerk, Bereinigung, Einstellungen |
| `ui_common.py` | Farbkonstanten, QSS, selbstgezeichnete Widgets (Card, AnimButton, NavButton, Toggle, Chips, RingGauge, LineChart, TweakRow, Icons per `QPainter`) |
| `service.py` | `Sampler` (QThread, 1 s: CPU/RAM/Disk/Netz/GPU/Ping/Fortnite), `Service` (Tweak-Status, Auto-Optimize, Cleanup, Undo-All) |
| `engine.py` | `TweakEngine` + `Tweak`-Dataclass; Backends `WinRegBackend`/`MemoryBackend`; Backup/Undo je Tweak (`tweak_state.json`) |
| `catalog.py` | 39 Tweaks, Profile (safe/competitive/maxfps), Empfehlungslogik |
| `netlab.py` | Ping, Jitter, DNS, Netzwerk-Konfiguration |
| `cleaner.py`, `fnmon.py` | Bereinigung, PresentMon-Auswertung |

Kinds: `registry`, `power`, `powersetting` (5), `ini` (7), `netadapter` (2). Alle Schreibzugriffe laufen über die Engine mit Backup → Undo ist bereits vorhanden.

## Befunde zu deinen Aufgaben
1. **CPU-Name:** Er wird nirgends ausgelesen. `Sampler._cpu_name` ist ein leeres, ungenutztes Feld; die CPU-Karte zeigt nur „X Kerne · Y Threads". Es gibt also keinen kaputten Code, sondern fehlende Funktion. Plan: Registry `HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0\ProcessorNameString` (+ `VendorIdentifier`), Fallback `Get-CimInstance Win32_Processor`, einmalig beim Start gecacht, sonst „Unbekannte CPU" statt Raten.
2. **Network-Tab:** Der Tab besteht aus Ping-Monitor + `TweaksList` gefiltert nach Tag `PING`. Die vier Netzwerk-Tweaks (`net_adapter_stable`, `net_throttle_off`, `delivery_opt_off`, `net_interrupt_mod_off`) sind **bereits** im Katalog (Kategorie „Netzwerk") und damit schon in der Tweaks-Liste vorhanden. Integration ist also eine reine UI-Gruppierung; der Ping-Monitor ist kein Tweak und wird zunächst nicht angefasst.
3. **Tweak-Tab:** Flache Liste mit Suche/Filter-Chips, keine Kategorie-Gruppierung, obwohl `categories` am Tweak existiert (Gaming/Fortnite/Latenz/Netzwerk/System).
4. **Theme:** Farben sind Modul-Konstanten in `ui_common.py` (importiert per `from ui_common import …`) und werden beim Import in das QSS-f-String eingebacken. ~40 Hex-Werte in `ui_common.py`, 5 in `pages_b.py` (Delegate), dazu Titelleiste (`apply_dark_titlebar`) und Icons. Für Live-Theming muss das auf ein zentrales Token-Objekt mit Neuaufbau des QSS und Repaint umgestellt werden.
5. **Scrollbar-Artefakt (dein Screenshot):** Die gestreifte/gepunktete Leiste rechts kommt sehr wahrscheinlich aus dem QSS: `QScrollBar:vertical` und der Handle sind gestylt, aber `add-page`/`sub-page` (die Spur) nicht. Qt zeichnet dann ein Standardmuster. Fix: `QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }`. Wird in Phase 2 behoben.
6. **Kleinigkeiten:** `build_catalog` ist zweimal definiert (Wrapper-Muster, funktioniert, aber verwirrend); Version steht nur in `app.py`.

## Was die Umgebung hier erlaubt
- Windows-Registry, PySide6 und GUI sind in meiner Sandbox nicht verfügbar (kein Internet, kein Windows). Logik, Server, Bot-Logik, Lizenzserver und Tests kann ich ausführen. Die Qt-UI kann ich schreiben und syntaktisch prüfen, aber nicht visuell testen; das übernimmt dein GitHub-Actions-Build (Selftest rendert jede Seite).

## Offene Entscheidungen / Zugangsdaten (später)
- Lemon Squeezy: Store-ID, API-Key, Variant-IDs, Webhook-Secret.
- Discord: Bot-Token, Server-ID, Rollen-ID Premium.
- Domain/Subdomain für HTTPS auf dem VPS.
