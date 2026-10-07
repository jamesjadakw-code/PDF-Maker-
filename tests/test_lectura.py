import os
import unittest
from unittest.mock import patch

from crm.enrich import enrich_machine_with_oem_specs
from crm.lectura import lookup_lectura, roster_lines, snap_identity
from crm.marketplace import to_brochure


class LecturaLookupTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("ANAKIN_WIRE_API_KEY", None)

    def test_roster_lists_every_master_machine(self):
        lines = "\n".join(roster_lines())
        self.assertIn("Caterpillar 320", lines)
        self.assertIn("John Deere 310", lines)
        self.assertIn("Vermeer D20x22 S3", lines)
        self.assertIn("Ditch Witch JT32", lines)
        self.assertEqual(len(roster_lines()), 15)

    def test_snap_identity_canonicalizes_cat_320(self):
        hit = snap_identity("CAT", "320")
        self.assertEqual(hit["make"], "Caterpillar")
        self.assertEqual(hit["model"], "320")
        self.assertEqual(hit["named"]["engine_power"], "173 hp")
        self.assertEqual(hit["named"]["bucket_capacity"], "1.57 yd³")

    def test_jt20_fills_hdd_fields_from_master(self):
        hit = lookup_lectura("Ditch Witch", "JT20")
        self.assertEqual(hit["family"], "hdd")
        self.assertEqual(hit["named"]["pullback_force"], "20,000 lb")
        self.assertEqual(hit["named"]["thrust_force"], "17,100 lb")
        self.assertEqual(hit["named"]["max_spindle_torque"], "2,198 ft·lb")

    def test_d20x22_matches_s3_row_and_adds_torque_only(self):
        with patch("crm.enrich.lookup_specs") as lookup:
            out = enrich_machine_with_oem_specs({
                "title": "Vermeer D20x22 Directional Drill",
                "make": "Vermeer",
                "model": "D20x22",
            })
        lookup.assert_not_called()
        self.assertEqual(out["pullback_force"], "20,000 lbs")
        self.assertEqual(out["thrust_force"], "22,000 lbs")
        self.assertEqual(out["max_spindle_torque"], "2,200 ft·lb")
        self.assertNotIn("Fuel tank", dict(out.get("oemSpecs") or []))

    def test_cat_320_fills_excavator_brochure_fields(self):
        with patch("crm.enrich.lookup_specs") as lookup:
            out = enrich_machine_with_oem_specs({
                "title": "CAT 320",
                "make": "CAT",
                "model": "320",
            })
        lookup.assert_not_called()
        self.assertEqual(out["spec_profile"], "excavator")
        self.assertEqual(out["engine_power"], "173 hp")
        self.assertEqual(out["operating_weight"], "49,604 lb")
        self.assertEqual(out["bucket_capacity"], "1.57 yd³")
        self.assertFalse(out.get("pullback_force"))
        brochure = to_brochure(out)
        self.assertEqual(len(brochure["specs"]), 26)
        sheet = " ".join(brochure["specs"])
        self.assertIn("Power | 173 hp", sheet)
        self.assertIn("Bucket capacity | 1.57 yd³", sheet)
        self.assertNotIn("blade_width", sheet)

    def test_cat_420_keeps_catalog_and_fills_dig_depth(self):
        with patch("crm.enrich.lookup_specs") as lookup:
            out = enrich_machine_with_oem_specs({
                "title": "CAT 420",
                "make": "CAT",
                "model": "420",
            })
        lookup.assert_not_called()
        self.assertEqual(out["engine_power"], "93 hp")
        self.assertEqual(out["operating_weight"], "17,000 lbs")
        self.assertEqual(out["digging_depth"], "14.3 ft")
