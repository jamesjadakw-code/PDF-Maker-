import json
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError

from crm.enrich import enrich_machine_with_oem_specs


def _unit(**extra):
    item = {
        "title": "2019 Ditch Witch JT20 Horizontal Drill",
        "make": "Ditch Witch",
        "model": "JT20",
        "category": "Directional Drill",
        "description": "Used JT20 with trailer.",
    }
    item.update(extra)
    return item


class FakeWire:
    def __init__(self, payload):
        self.payload = payload if isinstance(payload, (bytes, bytearray)) else json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


class EnrichTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("ANAKIN_WIRE_API_KEY", None)

    def tearDown(self):
        os.environ.pop("ANAKIN_WIRE_API_KEY", None)

    def test_skips_incomplete_make_or_model(self):
        item = {"title": "Used directional drill", "description": "No brand on this ad."}
        with patch("crm.enrich.lookup_specs") as lookup:
            out = enrich_machine_with_oem_specs(item)
        lookup.assert_not_called()
        self.assertIs(out, item)
        self.assertFalse(out["is_oem_enriched"])

    def test_maps_oem_rows_onto_named_schema_fields(self):
        rows = [
            ("Pullback force", "20,000 lb"),
            ("Thrust force", "17,000 lb"),
            ("Spindle torque, max", "2,200 ft·lb"),
            ("Power", "74 hp"),
            ("Operating weight", "15,300 lb"),
            ("Length", "207 in"),
            ("Width", "50 in"),
            ("Height", "94 in"),
        ]
        with patch("crm.enrich.lookup_specs", return_value=rows):
            out = enrich_machine_with_oem_specs(_unit())
        self.assertEqual(out["pullback_force"], "20,000 lb")
        self.assertEqual(out["thrust_force"], "17,000 lb")
        self.assertEqual(out["max_spindle_torque"], "2,200 ft·lb")
        self.assertEqual(out["engine_power"], "74 hp")
        self.assertEqual(out["operating_weight"], "15,300 lb")
        self.assertEqual(out["dimensions"], "207 in / 50 in / 94 in")
        self.assertTrue(out["is_oem_enriched"])
        self.assertTrue(out["enriched_at"])
        self.assertEqual(dict(out["oemSpecs"])["Pullback force"], "20,000 lb")

    def test_keeps_scraped_figures_and_never_writes_na(self):
        item = _unit(pullback_force="24,800 lb")
        with patch("crm.enrich.lookup_specs", return_value=[
            ("Pullback force", "N/A"),
            ("Thrust force", "N/A"),
            ("Power", "74 hp"),
        ]):
            out = enrich_machine_with_oem_specs(item)
        self.assertEqual(out["pullback_force"], "24,800 lb")
        self.assertEqual(out["engine_power"], "74 hp")
        self.assertNotEqual(out.get("thrust_force"), "N/A")
        self.assertFalse(str(out.get("thrust_force") or "").strip())

    def test_lookup_failure_returns_the_listing_and_does_not_raise(self):
        item = _unit()
        with patch("crm.enrich.lookup_specs", side_effect=OSError("search down")):
            out = enrich_machine_with_oem_specs(item)
        self.assertIs(out, item)
        self.assertFalse(out["is_oem_enriched"])
        self.assertEqual(out["model"], "JT20")

    def test_wire_payload_maps_onto_schema_fields(self):
        os.environ["ANAKIN_WIRE_API_KEY"] = "test-key"
        payload = {
            "specs": {
                "pullback_force": "20,000 lb",
                "spindle_torque": "2,200 ft·lb",
                "power": "74 hp",
                "weight": "15,300 lb",
                "dimensions": "207 x 50 x 94 in",
            }
        }
        with patch("crm.enrich.urlopen", return_value=FakeWire(payload)), \
             patch("crm.enrich.lookup_specs", return_value=[]):
            out = enrich_machine_with_oem_specs(_unit())
        self.assertEqual(out["pullback_force"], "20,000 lb")
        self.assertEqual(out["max_spindle_torque"], "2,200 ft·lb")
        self.assertEqual(out["engine_power"], "74 hp")
        self.assertEqual(out["operating_weight"], "15,300 lb")
        self.assertEqual(out["dimensions"], "207 x 50 x 94 in")
        self.assertTrue(out["is_oem_enriched"])
        self.assertEqual(dict(out["oemSpecs"])["Pullback force"], "20,000 lb")

    def test_wire_failure_falls_back_to_public_lookup(self):
        os.environ["ANAKIN_WIRE_API_KEY"] = "test-key"
        with patch("crm.enrich.urlopen", side_effect=URLError("wire down")), \
             patch("crm.enrich.lookup_specs", return_value=[("Pullback force", "19,500 lb")]):
            out = enrich_machine_with_oem_specs(_unit())
        self.assertEqual(out["pullback_force"], "19,500 lb")
        self.assertTrue(out["is_oem_enriched"])
