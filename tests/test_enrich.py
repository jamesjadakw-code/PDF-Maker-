import json
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError

from crm.enrich import enrich_machine_with_oem_specs
from crm.machine import identify_machine, spec_fields_for, spec_query


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

    def test_rt115_gets_trench_depth_not_pullback(self):
        item = {
            "title": "2012 Ditch Witch RT-115",
            "year": "2012",
            "description": "Ride-on trencher.",
        }
        ident = identify_machine(item)
        self.assertEqual(ident["family"], "trencher")
        self.assertEqual(ident["year"], "2012")
        self.assertIn("trench_depth", ident["spec_fields"])
        self.assertNotIn("pullback_force", ident["spec_fields"])
        self.assertIn("2012", spec_query(ident))
        self.assertIn("trencher", spec_query(ident))
        rows = [
            ("Pullback force", "20,000 lb"),
            ("Trench depth", "80 in"),
            ("Trench width", "12 in"),
            ("Power", "115 hp"),
            ("Operating weight", "11,150 lb"),
        ]
        with patch("crm.enrich.lookup_specs", return_value=rows):
            out = enrich_machine_with_oem_specs(item)
        self.assertEqual(out["trench_depth"], "80 in")
        self.assertEqual(out["trench_width"], "12 in")
        self.assertEqual(out["engine_power"], "115 hp")
        self.assertEqual(out["category"], "Trenchers & Rock Saws")
        self.assertEqual(out["spec_profile"], "trencher")
        self.assertFalse(out.get("pullback_force"))
        self.assertNotIn("Pullback force", dict(out["oemSpecs"]))

    def test_rt115_rocksaw_fills_saw_depth(self):
        item = {
            "title": "2012 Ditch Witch RT-115 with rocksaw",
            "year": "2012",
            "description": "H512 attachment.",
        }
        self.assertIn("rocksaw", identify_machine(item)["attachments"])
        self.assertIn("saw_depth", spec_fields_for("trencher", ["rocksaw"]))
        rows = [
            ("Trench depth", "80 in"),
            ("Saw depth", "30 in"),
            ("Power", "115 hp"),
            ("Operating weight", "12,400 lb"),
        ]
        with patch("crm.enrich.lookup_specs", return_value=rows):
            out = enrich_machine_with_oem_specs(item)
        self.assertEqual(out["trench_depth"], "80 in")
        self.assertEqual(out["saw_depth"], "30 in")
        self.assertIn("rocksaw", out["attachments"])
        self.assertFalse(out.get("pullback_force"))
        self.assertFalse(out.get("thrust_force"))
