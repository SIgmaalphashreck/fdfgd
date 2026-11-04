# Phase 2 + 3 + Teil 17 – Änderungsprotokoll (v1.1.0 → v1.2.0)

## Neue Dateien
| Datei | Inhalt |
|---|---|
| `theme.py` | Qt-freies Theme-System: 51 Design-Tokens, `derive()` leitet alles aus 4–5 Basisfarben ab, 10 Standard-Themes, Custom-Themes, JSON-Speicherung (`%LOCALAPPDATA%\SquallowTweaks\theme.json`), `ThemeManager` |
| `fx.py` | `FxRoot` (Fenster-Hintergrund) + 10 Effekte, je Theme eigenes Merkmal; Stufen Aus / Reduziert / Voll |
| `design_page.py` | Settings → **Design**: Theme-Kacheln mit Mini-Vorschau, Farbwähler (Sättigung/Helligkeit + Farbton), HEX-Eingabe, 4 Farben, Live-Vorschau, Effekt-Wahl, eigene Themes speichern/löschen |
| `sysinfo.py` | CPU-/GPU-/RAM-Erkennung, Temperaturen (nichts erfunden → „Nicht verfügbar") |
| `tests/test_theme_sysinfo.py`, `tests/test_integrity.py`, `tests/baseline_tweaks.json` | 22 neue Tests; Integritätstest vergleicht alle 39 Tweaks + Profile mit dem Originalstand |

## Geänderte Dateien
- `ui_common.py`: alle festen Farben → Tokens; Stylesheet jetzt `build_qss()`; **Scrollbar-Artefakt behoben** (Spur transparent); neue Dropdown-/Menü-/Slider-/Dialog-/Tooltip-Styles; Karten mit Hover-Anhebung (Schatten, Glow-Linie); Buttons mit dezentem Glow; neue Widgets `IconButton`, `IconTile`; neue Icons (discord, cpu, gpu, ram, disk, check, clock, therm, palette); Windows-Titelleiste folgt dem Theme.
- `app.py`: neue Sidebar (Icon-Kacheln, animierter Auswahl-Balken, Discord-Button, Theme-/Admin-Status), Fade beim Seitenwechsel, **Live-Theme-Wechsel ohne Neustart** (UI wird neu aufgebaut, laufende Tweak-Aktionen werden nicht gestört).
- `pages_a.py`: Dashboard mit Kopfzeile (Discord + Settings oben rechts), **Applied-Tweaks-Karte** (live aus dem echten Tweak-Status), Hardware-Karten CPU/GPU/RAM/Laufwerk; Tweaks-Seite nach Kategorien gruppiert, **Netzwerk-Tweaks als Gruppe „Netzwerk“**.
- `pages_b.py`: Tokens statt fester Farben; Settings mit Tabs Allgemein/Design; Network-Seite ohne Tweak-Liste (Ping-Monitor bleibt, erreichbar über Tweaks → Netzwerk → „Ping-Monitor“).
- `service.py`: Sampler liest Hardwaredaten in eigenem Thread (Modelle einmalig, Temperaturen alle 6 s), liefert freien RAM.
- `main.py`: Selftest rendert jetzt alle 10 Themes × alle Seiten; `--shots` erzeugt Screenshots je Theme.
- Workflow: neue Module im Syntax-Check, Screenshot-Artefakt `SquallowTweaks-Screenshots`.

## Unverändert (per SHA-256 geprüft)
`engine.py`, `catalog.py`, `cleaner.py`, `netlab.py`, `fnmon.py` – Tweaks, Registry-Werte, Backup/Undo, Profile.

## Hardware-Anzeige – was zuverlässig ist
- CPU-Modell: Registry `ProcessorNameString`, Ausweich CIM; sonst „Nicht verfügbar".
- GPU-Modell: NVIDIA/AMD/Intel über Win32_VideoController (virtuelle Adapter ausgefiltert). GPU-Temperatur und VRAM: NVIDIA über `nvidia-smi` (wie bisher).
- CPU-Temperatur: Windows liefert sie **nicht** ohne Sensor-Treiber. Wir lesen LibreHardwareMonitor/OpenHardwareMonitor (falls laufen), sonst die ACPI-Systemzone (im Tooltip als ungefähr gekennzeichnet), sonst „Nicht verfügbar".

## Themes und ihr Merkmal
Black = Glas-Glanz · White = Softlight · Pink = Neon-Rahmen · Purple = Energie-Linien · Green = Code-Regen + Partikel · Blue = Hologramm/Scanlines · Red = Lichtimpulse · Cyan = elektrische Blitze · Midnight = Sterne/Sternschnuppen · Chromatic = wandernde Farbverläufe (Akzent wechselt langsam).
Performance: Effekte nur im Hintergrund, 22 fps (Reduziert 12 fps), pausieren bei inaktivem/minimiertem Fenster, in Design → Theme-Effekte abschaltbar.

## Bekannte Grenzen
- In der Entwicklungsumgebung stand kein PySide6/Windows zur Verfügung: Theme-/Sysinfo-Logik und Tweak-Integrität sind getestet (82 Tests grün); die Qt-Oberfläche wird erst vom GitHub-Build (Unit-Tests + EXE-Selbsttest + Screenshots) geprüft.
- Chromatic: Qt-Stylesheet-Elemente (Eingabefelder, Progressbar) behalten die Basisfarbe; gezeichnete Elemente animieren.
