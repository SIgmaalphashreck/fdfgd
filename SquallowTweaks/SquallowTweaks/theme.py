"""SquallowTweaks - zentrales Theme-System (Design-Tokens, ohne Qt-Abhaengigkeit, voll testbar).

Aufbau:
  * Ein Theme ist ein kleines Dict aus Basisfarben (bg, accent, accent2, secondary, tertiary) + Effekt-Name.
  * `derive()` leitet daraus alle ~50 Design-Tokens ab (Karten, Rahmen, Text, Buttons, Hover ...).
    Neue Farben/Themes brauchen deshalb nur 4-5 Basisfarben.
  * `C` ist das globale Token-Objekt, das die UI beim Zeichnen liest. `ThemeManager` ueberschreibt es in-place.
"""
from __future__ import annotations

import colorsys
import json
import re
from pathlib import Path
from typing import Callable, Optional

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6}|[0-9a-fA-F]{3})$")
WHITE, BLACK = "#ffffff", "#000000"

# --------------------------------------------------------------------------
# Farb-Helfer (alles als "#rrggbb"-Strings)
# --------------------------------------------------------------------------
def norm_hex(value) -> Optional[str]:
    """'#abc' / 'ABCDEF' -> '#aabbcc'. Ungueltig -> None."""
    if not isinstance(value, str):
        return None
    m = HEX_RE.match(value.strip())
    if not m:
        return None
    h = m.group(1).lower()
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return "#" + h


def to_rgb(h: str) -> tuple[int, int, int]:
    h = norm_hex(h) or "#000000"
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def to_hex(r: float, g: float, b: float) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(v)))) for v in (r, g, b))


def mix(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    ra, rb = to_rgb(a), to_rgb(b)
    return to_hex(*(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def luminance(h: str) -> float:
    def ch(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = to_rgb(h)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_text(bg: str) -> str:
    return "#0B0B12" if luminance(bg) > 0.40 else "#FFFFFF"


def to_hsv(h: str) -> tuple[float, float, float]:
    r, g, b = (v / 255 for v in to_rgb(h))
    return colorsys.rgb_to_hsv(r, g, b)


def from_hsv(h: float, s: float, v: float) -> str:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return to_hex(r * 255, g * 255, b * 255)


def shift_hue(h: str, deg: float) -> str:
    hh, s, v = to_hsv(h)
    return from_hsv(hh + deg / 360.0, s, v)


# --------------------------------------------------------------------------
# Themes
# --------------------------------------------------------------------------
# fx = eigenes visuelles Merkmal (siehe fx.py): glass, softlight, neon, energy, matrix, holo, pulse, electric, stars, chromatic, none
BUILTIN: dict[str, dict] = {
    "Black":      dict(light=False, bg="#08080B", accent="#D9DBE6", accent2="#FFFFFF", secondary="#8FA3BF", tertiary="#A78BFA", fx="glass",     glass=222),
    "White":      dict(light=True,  bg="#EEF0F7", accent="#5B5BF0", accent2="#7C83FF", secondary="#0EA5C6", tertiary="#E0508F", fx="softlight", glass=235),
    "Pink":       dict(light=False, bg="#0E0810", accent="#FF4FA3", accent2="#FF93C9", secondary="#C084FC", tertiary="#FDA4D4", fx="neon",      glass=222),
    "Purple":     dict(light=False, bg="#0A0714", accent="#8B5CF6", accent2="#C4A8FF", secondary="#38BDF8", tertiary="#F472B6", fx="energy",    glass=222),
    "Green":      dict(light=False, bg="#050A07", accent="#22C55E", accent2="#86EFAC", secondary="#2DD4BF", tertiary="#A3E635", fx="matrix",    glass=214),
    "Blue":       dict(light=False, bg="#060A14", accent="#3B82F6", accent2="#93C5FD", secondary="#22D3EE", tertiary="#818CF8", fx="holo",      glass=220),
    "Red":        dict(light=False, bg="#0C0607", accent="#EF4444", accent2="#FCA5A5", secondary="#F97316", tertiary="#FB7185", fx="pulse",     glass=222),
    "Cyan":       dict(light=False, bg="#050C0F", accent="#06B6D4", accent2="#67E8F9", secondary="#34D399", tertiary="#60A5FA", fx="electric",  glass=220),
    "Midnight":   dict(light=False, bg="#02030A", accent="#6D7BFF", accent2="#A5B4FC", secondary="#C084FC", tertiary="#F0ABFC", fx="stars",     glass=210),
    "Chromatic":  dict(light=False, bg="#08080E", accent="#8B7CF6", accent2="#B89CFF", secondary="#5EEAD4", tertiary="#F472B6", fx="chromatic", glass=220, chromatic=True),
}
BUILTIN_ORDER = tuple(BUILTIN)
FX_NAMES = ("none", "glass", "softlight", "neon", "energy", "matrix", "holo", "pulse", "electric", "stars", "chromatic")
FX_LABELS = {"none": "Keiner", "glass": "Glas", "softlight": "Softlight", "neon": "Neon", "energy": "Energie", "matrix": "Matrix",
             "holo": "Hologramm", "pulse": "Pulse", "electric": "Elektro", "stars": "Sterne", "chromatic": "Farbfluss"}
DEFAULT_THEME = "Purple"   # entspricht dem bisherigen Squallow-Look


def custom_spec(primary: str, secondary: str, accent: str, background: str, fx: str = "glass") -> dict:
    """Aus den vier Benutzerfarben ein vollstaendiges Theme-Dict bauen."""
    bg = norm_hex(background) or "#0A0A10"
    pri = norm_hex(primary) or "#8B7CF6"
    sec = norm_hex(secondary) or "#5EEAD4"
    acc = norm_hex(accent) or "#B89CFF"
    return dict(light=luminance(bg) > 0.40, bg=bg, accent=pri, accent2=acc, secondary=sec, tertiary=shift_hue(pri, 70),
                fx=fx if fx in FX_NAMES else "glass", glass=222)


TOKEN_NAMES = (
    "name", "light", "fx", "glass", "chromatic",
    "bg", "sidebar", "card", "card2", "border", "border_hi", "text", "muted", "dim",
    "accent", "accent2", "secondary", "tertiary", "green", "yellow", "red",
    "hero_a", "hero_b", "hero_border", "nav_on_a", "nav_on_b", "nav_hover", "track", "grid",
    "btn_off", "btn_a", "btn_a_h", "btn_b", "btn_b_h", "on_accent", "ghost_h", "danger_bg", "danger_bg_h", "danger_border",
    "chip_on", "toggle_off", "toggle_off_h", "knob", "knob_off", "input_focus", "scroll", "scroll_h", "tooltip_bg", "tooltip_border",
    "row_hover", "overlay",
)


def derive(spec: dict, name: str = "Custom") -> dict:
    """Basisfarben -> alle Design-Tokens."""
    light = bool(spec.get("light"))
    bg, acc, acc2 = spec["bg"], spec["accent"], spec["accent2"]
    sec = spec.get("secondary") or acc2
    ter = spec.get("tertiary") or shift_hue(acc, 60)
    if light:
        card, card2 = mix(bg, WHITE, .78), mix(bg, BLACK, .04)
        border, border_hi = mix(bg, BLACK, .12), mix(bg, BLACK, .24)
        sidebar = mix(bg, WHITE, .55)
        text = "#14141F"
        green, yellow, red = "#16A34A", "#B45309", "#DC2626"
    else:
        card, card2 = mix(bg, WHITE, .05), mix(bg, WHITE, .095)
        border, border_hi = mix(bg, WHITE, .12), mix(bg, WHITE, .22)
        sidebar = mix(bg, BLACK, .28)
        text = "#EDEDF7"
        green, yellow, red = "#4ADE80", "#FBBF24", "#F87171"
    if luminance(bg) > 0.40 and not light:       # helle Custom-Hintergruende
        text = contrast_text(bg)
    muted, dim = mix(text, bg, .42), mix(text, bg, .62)
    on_accent = contrast_text(mix(acc, acc2, .5))
    t = {
        "name": name, "light": light, "fx": spec.get("fx", "none"), "glass": int(spec.get("glass", 225)),
        "chromatic": bool(spec.get("chromatic")),
        "bg": bg, "sidebar": sidebar, "card": card, "card2": card2, "border": border, "border_hi": border_hi,
        "text": text, "muted": muted, "dim": dim,
        "accent": acc, "accent2": acc2, "secondary": sec, "tertiary": ter, "green": green, "yellow": yellow, "red": red,
        "hero_a": mix(card, acc, .13 if not light else .08), "hero_b": mix(card, acc, .20 if not light else .13),
        "hero_border": mix(border, acc, .38),
        "nav_on_a": mix(card, acc, .30 if not light else .16), "nav_on_b": mix(sidebar, acc, .10 if not light else .06),
        "nav_hover": mix(sidebar, text, .07),
        "track": mix(card, text, .08), "grid": mix(bg, text, .07),
        "btn_off": mix(card2, bg, .35), "btn_a": acc, "btn_a_h": mix(acc, WHITE, .18), "btn_b": acc2, "btn_b_h": mix(acc2, WHITE, .18),
        "on_accent": on_accent, "ghost_h": mix(card2, acc, .12),
        "danger_bg": mix(card, red, .12), "danger_bg_h": mix(card, red, .22), "danger_border": mix(border, red, .5),
        "chip_on": mix(card, acc, .24 if not light else .14),
        "toggle_off": mix(card2, text, .10), "toggle_off_h": mix(card2, text, .20),
        "knob": "#ffffff", "knob_off": "#9A9AB0",
        "input_focus": mix(card, acc, .05), "scroll": mix(bg, text, .16), "scroll_h": mix(bg, text, .32),
        "tooltip_bg": card2, "tooltip_border": border_hi,
        "row_hover": mix(card, acc, .05), "overlay": bg,
    }
    return t


class Tokens:
    """Globales Token-Objekt. Attribute werden in-place ueberschrieben, damit `from theme import C` immer aktuell bleibt."""

    def __init__(self):
        self.set(derive(BUILTIN[DEFAULT_THEME], DEFAULT_THEME))

    def set(self, tokens: dict) -> None:
        for k in TOKEN_NAMES:
            setattr(self, k, tokens[k])

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in TOKEN_NAMES}


C = Tokens()


def chromatic_spec(base: dict, hue: float) -> dict:
    """Chromatic: Akzente wandern ueber den Farbkreis (hue 0..1). Hintergrund bleibt ruhig dunkel."""
    s = dict(base)
    s["accent"] = from_hsv(hue, .62, .98)
    s["accent2"] = from_hsv(hue + .07, .42, 1.0)
    s["secondary"] = from_hsv(hue + .40, .58, .95)
    s["tertiary"] = from_hsv(hue + .72, .60, .98)
    return s


# --------------------------------------------------------------------------
# Verwaltung + Speicherung
# --------------------------------------------------------------------------
FX_LEVELS = {0: "Aus", 1: "Reduziert", 2: "Voll"}


class ThemeManager:
    """Haelt das aktive Theme, speichert Einstellungen (JSON) und informiert Listener."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.current = DEFAULT_THEME
        self.custom: dict = {"primary": "#8B7CF6", "secondary": "#5EEAD4", "accent": "#B89CFF", "background": "#0A0A10", "fx": "glass"}
        self.saved: dict[str, dict] = {}
        self.fx_level = 2
        self.settings_tab = "Allgemein"
        self.hue = 0.72
        self._listeners: list[Callable[[], None]] = []
        self.load()

    # ----- Laden / Speichern -----
    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            data = {}
        if not isinstance(data, dict):
            data = {}
        cust = data.get("custom")
        if isinstance(cust, dict):
            for k in ("primary", "secondary", "accent", "background"):
                v = norm_hex(cust.get(k))
                if v:
                    self.custom[k] = v
            if cust.get("fx") in FX_NAMES:
                self.custom["fx"] = cust["fx"]
        saved = data.get("saved")
        if isinstance(saved, dict):
            for nm, c in saved.items():
                if isinstance(nm, str) and nm.strip() and nm not in BUILTIN and isinstance(c, dict):
                    cols = {k: norm_hex(c.get(k)) for k in ("primary", "secondary", "accent", "background")}
                    if all(cols.values()):
                        cols["fx"] = c.get("fx") if c.get("fx") in FX_NAMES else "glass"
                        self.saved[nm.strip()[:24]] = cols
        lvl = data.get("fx_level")
        if lvl in FX_LEVELS:
            self.fx_level = lvl
        cur = data.get("theme")
        if isinstance(cur, str) and (cur in BUILTIN or cur in self.saved or cur == "Custom"):
            self.current = cur
        tab = data.get("settings_tab")
        if tab in ("Allgemein", "Design"):
            self.settings_tab = tab
        self.apply()

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"theme": self.current, "custom": self.custom, "saved": self.saved, "fx_level": self.fx_level,
                       "settings_tab": self.settings_tab}
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.path)
            return True
        except Exception:  # noqa: BLE001
            return False

    # ----- Specs -----
    def names(self) -> list[str]:
        return list(BUILTIN_ORDER) + list(self.saved)

    def spec_of(self, name: str) -> dict:
        if name in BUILTIN:
            return dict(BUILTIN[name])
        c = self.saved.get(name) if name != "Custom" else self.custom
        c = c or self.custom
        return custom_spec(c["primary"], c["secondary"], c["accent"], c["background"], c.get("fx", "glass"))

    def tokens_of(self, name: str, hue: Optional[float] = None) -> dict:
        spec = self.spec_of(name)
        if spec.get("chromatic"):
            spec = chromatic_spec(spec, self.hue if hue is None else hue)
        return derive(spec, name)

    def preview_tokens(self, primary: str, secondary: str, accent: str, background: str, fx: str = "glass") -> dict:
        return derive(custom_spec(primary, secondary, accent, background, fx), "Vorschau")

    # ----- Aktionen -----
    def apply(self) -> None:
        C.set(self.tokens_of(self.current))

    def set_theme(self, name: str, persist: bool = True) -> bool:
        if name != "Custom" and name not in self.names():
            return False
        self.current = name
        self.apply()
        if persist:
            self.save()
        self._notify()
        return True

    def set_custom(self, primary: str, secondary: str, accent: str, background: str, fx: Optional[str] = None, activate: bool = True) -> bool:
        cols = {k: norm_hex(v) for k, v in (("primary", primary), ("secondary", secondary), ("accent", accent), ("background", background))}
        if not all(cols.values()):
            return False
        cols["fx"] = fx if fx in FX_NAMES else self.custom.get("fx", "glass")
        self.custom = cols
        if activate:
            return self.set_theme("Custom")
        self.save()
        return True

    def save_custom_as(self, name: str) -> Optional[str]:
        name = " ".join((name or "").split())[:24]
        if not name or name in BUILTIN or name == "Custom":
            return None
        self.saved[name] = dict(self.custom)
        self.current = name
        self.apply()
        self.save()
        self._notify()
        return name

    def delete_saved(self, name: str) -> bool:
        if name not in self.saved:
            return False
        del self.saved[name]
        if self.current == name:
            self.current = DEFAULT_THEME
            self.apply()
        self.save()
        self._notify()
        return True

    def set_fx_level(self, level: int) -> None:
        if level in FX_LEVELS:
            self.fx_level = level
            self.save()
            self._notify()

    def set_settings_tab(self, tab: str) -> None:
        if tab in ("Allgemein", "Design"):
            self.settings_tab = tab
            self.save()

    def chromatic_tick(self, hue: float) -> None:
        """Nur fuer das Chromatic-Theme: Tokens leise in-place aktualisieren (kein Listener-Aufruf, keine Speicherung)."""
        self.hue = hue % 1.0
        if C.chromatic:
            C.set(self.tokens_of(self.current, self.hue))

    # ----- Listener -----
    def subscribe(self, fn: Callable[[], None]) -> None:
        self._listeners.append(fn)

    def _notify(self) -> None:
        for fn in list(self._listeners):
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass
