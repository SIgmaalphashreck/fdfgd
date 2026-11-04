import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sysinfo  # noqa: E402
import theme  # noqa: E402


class ThemeTests(unittest.TestCase):
    def test_all_ten_required_themes_exist(self):
        for n in ("Black", "White", "Pink", "Purple", "Green", "Blue", "Red", "Cyan", "Midnight", "Chromatic"):
            self.assertIn(n, theme.BUILTIN)

    def test_every_theme_has_all_tokens_valid_hex_and_unique_fx(self):
        fxs = []
        for n, spec in theme.BUILTIN.items():
            t = theme.derive(spec, n)
            for k in theme.TOKEN_NAMES:
                self.assertIn(k, t)
            for k, v in t.items():
                if k in ("name", "light", "fx", "glass", "chromatic"):
                    continue
                self.assertIsNotNone(theme.norm_hex(v), f"{n}.{k}={v}")
            fxs.append(t["fx"])
        self.assertEqual(len(set(fxs)), 10)

    def test_text_is_readable_on_every_background(self):
        for n, spec in theme.BUILTIN.items():
            t = theme.derive(spec, n)
            self.assertGreater(abs(theme.luminance(t["text"]) - theme.luminance(t["bg"])), 0.5, n)
            self.assertGreater(abs(theme.luminance(t["text"]) - theme.luminance(t["card"])), 0.45, n)

    def test_white_is_light_black_is_dark(self):
        self.assertTrue(theme.derive(theme.BUILTIN["White"])["light"])
        self.assertFalse(theme.derive(theme.BUILTIN["Black"])["light"])

    def test_norm_hex(self):
        self.assertEqual(theme.norm_hex("#ABC"), "#aabbcc")
        self.assertEqual(theme.norm_hex("ff00AA"), "#ff00aa")
        for bad in ("", "#12", "zzzzzz", "#1234567", None, 5):
            self.assertIsNone(theme.norm_hex(bad))

    def test_custom_colors_and_persistence_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "theme.json"
            m = theme.ThemeManager(p)
            self.assertEqual(m.current, theme.DEFAULT_THEME)
            self.assertFalse(m.set_custom("nope", "#00ff00", "#0000ff", "#101010"))
            self.assertTrue(m.set_custom("#ff0000", "#00ff00", "#0000ff", "#101010", fx="stars"))
            self.assertEqual(theme.C.accent, "#ff0000")
            self.assertEqual(theme.C.fx, "stars")
            self.assertEqual(m.save_custom_as("  Mein   Theme "), "Mein Theme")
            m.set_theme("Midnight")
            m.set_fx_level(1)
            m2 = theme.ThemeManager(p)          # "Neustart"
            self.assertEqual(m2.current, "Midnight")
            self.assertEqual(m2.fx_level, 1)
            self.assertIn("Mein Theme", m2.saved)
            self.assertEqual(theme.C.name, "Midnight")
            m2.set_theme("Mein Theme")
            self.assertEqual(theme.C.accent, "#ff0000")
            self.assertTrue(m2.delete_saved("Mein Theme"))
            self.assertEqual(m2.current, theme.DEFAULT_THEME)

    def test_cannot_overwrite_builtin_name_and_corrupt_file_is_safe(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "theme.json"
            p.write_text("{kaputt", encoding="utf-8")
            m = theme.ThemeManager(p)
            self.assertEqual(m.current, theme.DEFAULT_THEME)
            self.assertIsNone(m.save_custom_as("Black"))
            p.write_text(json.dumps({"theme": "Gibtsnicht", "saved": {"X": {"primary": "bad"}}}), encoding="utf-8")
            m = theme.ThemeManager(p)
            self.assertEqual(m.current, theme.DEFAULT_THEME)
            self.assertEqual(m.saved, {})

    def test_listeners_fire_on_theme_change_but_not_on_chromatic_tick(self):
        with tempfile.TemporaryDirectory() as d:
            m = theme.ThemeManager(Path(d) / "t.json")
            calls = []
            m.subscribe(lambda: calls.append(1))
            m.set_theme("Pink")
            self.assertEqual(len(calls), 1)
            m.set_theme("Chromatic")
            a1 = theme.C.accent
            m.chromatic_tick(0.1)
            a2 = theme.C.accent
            self.assertNotEqual(a1, a2)
            self.assertEqual(len(calls), 2)
            m.set_theme("Black")
            m.chromatic_tick(0.5)           # darf Nicht-Chromatic-Themes nicht veraendern
            self.assertEqual(theme.C.name, "Black")
            self.assertEqual(theme.C.accent, theme.BUILTIN["Black"]["accent"])


class SysinfoTests(unittest.TestCase):
    def test_cpu_from_registry(self):
        r = sysinfo.read_cpu(registry=lambda: ("AMD Ryzen 5 5500             ", "AuthenticAMD"))
        self.assertEqual(r, {"name": "AMD Ryzen 5 5500", "vendor": "AMD"})

    def test_cpu_intel_trademarks_removed(self):
        r = sysinfo.read_cpu(registry=lambda: ("Intel(R) Core(TM) i7-11800H @ 2.30GHz", "GenuineIntel"))
        self.assertEqual(r["name"], "Intel Core i7-11800H @ 2.30GHz")
        self.assertEqual(r["vendor"], "Intel")

    def test_cpu_falls_back_to_cim_and_never_invents(self):
        r = sysinfo.read_cpu(registry=lambda: (None, None), cim=lambda: {"Name": "AMD Ryzen 7 5800X 8-Core Processor", "Manufacturer": "AuthenticAMD"})
        self.assertEqual(r["name"], "AMD Ryzen 7 5800X 8-Core Processor")
        self.assertEqual(r["vendor"], "AMD")
        r = sysinfo.read_cpu(registry=lambda: ("", None), cim=lambda: None)
        if sysinfo.os.name == "nt":
            self.assertIsNone(r["name"])

    def test_gpu_pick_prefers_discrete_and_skips_virtual(self):
        ad = [{"Name": "AMD Radeon(TM) Graphics"}, {"Name": "Microsoft Basic Display Adapter"}, {"Name": "NVIDIA GeForce RTX 5060 Ti"},
              {"Name": "Parsec Virtual Display Adapter"}]
        self.assertEqual(sysinfo.pick_gpu(ad)["Name"], "NVIDIA GeForce RTX 5060 Ti")
        self.assertIsNone(sysinfo.pick_gpu([{"Name": "Microsoft Remote Display Adapter"}]))
        self.assertIsNone(sysinfo.pick_gpu([]))

    def test_ram_kind(self):
        self.assertEqual(sysinfo.ram_kind([{"SMBIOSMemoryType": 26, "ConfiguredClockSpeed": 3200}] * 2), ("DDR4", 3200))
        self.assertEqual(sysinfo.ram_kind([{"SMBIOSMemoryType": 0}]), (None, None))
        self.assertEqual(sysinfo.ram_kind([{"SMBIOSMemoryType": 26}, {"SMBIOSMemoryType": 34}])[0], None)

    def test_cpu_temp_prefers_package_and_checks_range(self):
        s = [{"Identifier": "/amdcpu/0/temperature/2", "Name": "Core (Tctl/Tdie)", "Value": 61.5},
             {"Identifier": "/amdcpu/0/temperature/3", "Name": "CCD1 (Tdie)", "Value": 55},
             {"Identifier": "/gpu-nvidia/0/temperature/0", "Name": "GPU Core", "Value": 47}]
        self.assertEqual(sysinfo.pick_cpu_temp(s), 61.5)
        self.assertEqual(sysinfo.pick_gpu_temp(s), 47.0)
        self.assertIsNone(sysinfo.pick_cpu_temp([{"Identifier": "/cpu/0", "Name": "CPU Package", "Value": 0}]))
        self.assertIsNone(sysinfo.pick_cpu_temp([]))

    def test_acpi_kelvin_conversion(self):
        self.assertEqual(sysinfo.pick_acpi_temp([{"Temperature": 318.15}]), 45.0)
        self.assertIsNone(sysinfo.pick_acpi_temp([{"Temperature": 0}, {"Temperature": "x"}]))

    def test_read_temps_source_priority_and_failure(self):
        import shutil
        orig = shutil.which
        shutil.which = lambda n: "/x/powershell"
        try:
            ok = json.dumps({"lhm": [{"Identifier": "/intelcpu/0/temperature/0", "Name": "CPU Package", "Value": 48}], "ohm": [], "acpi": [{"Temperature": 330}]})
            r = sysinfo.read_temps(lambda a, t: (0, ok))
            self.assertEqual((r["cpu_temp"], r["cpu_temp_src"]), (48.0, "Sensor"))
            only_acpi = json.dumps({"lhm": [], "ohm": [], "acpi": {"Temperature": 323.15}})
            r = sysinfo.read_temps(lambda a, t: (0, only_acpi))
            self.assertEqual((r["cpu_temp"], r["cpu_temp_src"]), (50.0, "ACPI"))
            r = sysinfo.read_temps(lambda a, t: (1, "boom"))
            self.assertIsNone(r["cpu_temp"])
            r = sysinfo.read_temps(lambda a, t: (0, "kein json"))
            self.assertIsNone(r["cpu_temp"])
        finally:
            shutil.which = orig

    def test_fmt_temp(self):
        self.assertEqual(sysinfo.fmt_temp(None), "Nicht verfügbar")
        self.assertEqual(sysinfo.fmt_temp(45.4), "45 °C")


if __name__ == "__main__":
    unittest.main()
