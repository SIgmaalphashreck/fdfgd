"""Funktionsgarantie: Tweaks, Profile und Optimierungslogik duerfen durch Design-/Lizenz-Arbeit nicht veraendert werden."""
import dataclasses
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import catalog  # noqa: E402

BASE = json.loads((Path(__file__).with_name("baseline_tweaks.json")).read_text(encoding="utf-8"))


def _norm(txt: str) -> str:
    return re.sub(r"0x[0-9a-f]+", "0x", txt)      # Speicheradressen von Funktions-Objekten ignorieren


def _ser(t):
    return json.loads(_norm(json.dumps(dataclasses.asdict(t) if dataclasses.is_dataclass(t) else vars(t), default=repr, sort_keys=True)))


class TweakIntegrity(unittest.TestCase):
    def test_tweak_definitions_identical_to_original(self):
        now = sorted((_ser(t) for t in catalog.build_catalog()), key=lambda x: x["id"])
        self.assertEqual(len(now), len(BASE["tweaks"]))
        for a, b in zip(now, BASE["tweaks"]):
            self.assertEqual(a, b, a["id"])

    def test_profiles_identical(self):
        self.assertEqual(json.loads(json.dumps(catalog.PROFILES, default=repr)), BASE["profiles"])

    def test_network_tweaks_present_for_integration(self):
        ids = {t.id for t in catalog.build_catalog() if "Netzwerk" in t.categories}
        self.assertEqual(ids, {"net_adapter_stable", "net_throttle_off", "delivery_opt_off", "net_interrupt_mod_off"})
        ping = {t.id for t in catalog.build_catalog() if "PING" in t.tags}
        self.assertEqual(ids, ping)           # exakt die Tweaks des frueheren Network-Tabs

    def test_every_tweak_has_a_primary_category_for_grouping(self):
        for t in catalog.build_catalog():
            self.assertIn((t.categories or ("System",))[0], ("Gaming", "Latenz", "Netzwerk", "Fortnite", "System"), t.id)

    def test_safety_tweaks_not_paywalled_placeholder(self):
        # Backup/Undo sind Engine-Funktionen und werden nicht an Tweaks gekoppelt
        import engine
        self.assertTrue(hasattr(engine.TweakEngine, "undo") and hasattr(engine.TweakEngine, "has_backup"))


if __name__ == "__main__":
    unittest.main()
