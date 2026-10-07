import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from crm.catalog import lookup_catalog, process_incoming_third_party_listing
from crm.enrich import enrich_machine_with_oem_specs
from crm.machine import identify_machine, make_from_model
from crm.marketplace import to_brochure
from crm.vision import detect_machine_from_image


class CatalogIngestTests(unittest.TestCase):
    def setUp(self):
        os.environ.pop("ANAKIN_WIRE_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GOOGLE_API_KEY", None)

    def tearDown(self):
        os.environ.pop("ANAKIN_WIRE_API_KEY", None)
        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("GOOGLE_API_KEY", None)

    def test_vermeer_d20x22_uses_cache_pullback_not_web(self):
        item = {
            "title": "Vermeer D20x22 Directional Drill",
            "make": "Vermeer",
            "model": "D20x22",
            "description": "HDD.",
        }
        with patch("crm.enrich.lookup_specs") as lookup:
            out = process_incoming_third_party_listing(item)
        lookup.assert_not_called()
        self.assertEqual(out["pullback_force"], "20,000 lbs")
        self.assertEqual(out["thrust_force"], "22,000 lbs")
        self.assertEqual(out["spec_profile"], "hdd")
        self.assertTrue(out["catalog_hit"])
        self.assertFalse(out["is_staged"])
        self.assertEqual(out["source_platform"], "Third-Party Scrape Stream")

    def test_rt125_is_ditch_witch_not_vermeer_rtx(self):
        self.assertEqual(make_from_model("RT125"), "Ditch Witch")
        self.assertEqual(make_from_model("RTX1250"), "Vermeer")
        ident = identify_machine({
            "title": "Ditch Witch RT125 with vibratory plow and rear reel carrier",
        })
        self.assertEqual(ident["make"], "Ditch Witch")
        self.assertEqual(ident["model"], "RT125")
        self.assertEqual(ident["family"], "trencher")
        self.assertIn("plow", ident["attachments"])
        self.assertIn("reel", ident["attachments"])
        dw = lookup_catalog("Ditch Witch", "RT125")
        vm = lookup_catalog("Vermeer", "RT125")
        self.assertEqual(dw["payload"].get("base_hp"), 121)
        self.assertFalse(vm["payload"])
        wrong = identify_machine({"make": "Vermeer", "model": "RT125", "title": "RT125 Quad"})
        self.assertEqual(wrong["make"], "Ditch Witch")

    def test_rt125_plow_and_reel_show_full_spec_sheet(self):
        item = {
            "title": "Ditch Witch RT125 with vibratory plow and rear reel carrier",
            "description": "Quad tracks laying conduit.",
        }
        with patch("crm.enrich.lookup_specs") as lookup:
            out = process_incoming_third_party_listing(item)
        lookup.assert_not_called()
        self.assertEqual(out["make"], "Ditch Witch")
        self.assertEqual(out["model"], "RT125")
        self.assertEqual(out["engine_power"], "121 hp")
        self.assertEqual(out["plow_depth"], "42 in")
        self.assertEqual(out["operating_weight"], "15,300 lb")
        self.assertIn("166 in", out["dimensions"])
        self.assertIn("plow", out["attachments"])
        self.assertIn("reel", out["attachments"])
        self.assertFalse(out.get("pullback_force"))
        labels = {row["label"]: row["value"] for row in out["spec_sheet"]}
        self.assertEqual(labels["Make"], "Ditch Witch")
        self.assertEqual(labels["Model"], "RT125")
        self.assertEqual(labels["Power"], "121 hp")
        self.assertEqual(labels["Plow depth"], "42 in")
        self.assertNotIn("Fuel tank", labels)
        self.assertNotIn("DEF tank", labels)
        self.assertNotIn("Engine", labels)
        self.assertLessEqual(len(out["spec_sheet"]), 12)
        self.assertIn("reel", labels["Attachments"])
        self.assertIn("VP120Q", labels["Attachments"])
        models = {row.get("token"): row.get("model") for row in out["compiled_attachments"]}
        self.assertEqual(models.get("plow"), "VP120Q")
        self.assertEqual(models.get("reel"), "RC30")
        brochure = to_brochure(out)
        self.assertEqual(len(brochure["specs"]), 26)
        sheet = " ".join(brochure["specs"])
        self.assertIn("Power | 121 hp", sheet)
        self.assertIn("Plow depth | 42 in", sheet)
        self.assertNotIn("DEF tank", sheet)
        self.assertNotIn("Fuel tank", sheet)
        filled = [row for row in brochure["specs"] if row.split("|", 1)[0].strip()]
        self.assertLessEqual(len(filled), 12)

    def test_rtx1250_plow_gets_plow_depth_not_pullback(self):
        item = {
            "title": "Vermeer RTX1250 with vibratory plow",
            "year": "2018",
            "description": "Quad tracks.",
        }
        with patch("crm.enrich.lookup_specs") as lookup:
            out = enrich_machine_with_oem_specs(item)
        lookup.assert_not_called()
        self.assertEqual(out["engine_power"], "121 hp")
        self.assertEqual(out["plow_depth"], "42 in")
        self.assertIn("plow", out["attachments"])
        self.assertFalse(out.get("pullback_force"))
        self.assertEqual(out["spec_profile"], "trencher")
        names = [row["attachment_name"] for row in out["compiled_attachments"]]
        self.assertTrue(any("plow" in str(name).lower() or row.get("token") == "plow" for name, row in zip(names, out["compiled_attachments"])))

    def test_cat_420_backhoe_from_cache(self):
        item = {"title": "CAT 420", "make": "CAT", "model": "420"}
        with patch("crm.enrich.lookup_specs") as lookup:
            out = enrich_machine_with_oem_specs(item)
        lookup.assert_not_called()
        self.assertEqual(out["engine_power"], "93 hp")
        self.assertEqual(out["operating_weight"], "17,000 lbs")
        self.assertEqual(out["spec_profile"], "backhoe")

    def test_deere_310_with_4in1_bucket_capacity(self):
        item = {
            "title": "John Deere 310 with 4-in-1 loader bucket",
            "make": "John Deere",
            "model": "310",
        }
        out = enrich_machine_with_oem_specs(item)
        self.assertEqual(out["engine_power"], "91 hp")
        self.assertEqual(out["bucket_capacity"], "1.2 yd³")
        self.assertIn("bucket", out["attachments"])

    def test_staged_inventory_is_not_cataloged(self):
        item = {
            "title": "Vermeer D20x22",
            "make": "Vermeer",
            "model": "D20x22",
            "is_staged": True,
            "source_type": "staged",
        }
        with patch("crm.enrich.lookup_specs") as lookup:
            out = process_incoming_third_party_listing(item)
        lookup.assert_not_called()
        self.assertFalse(out.get("catalog_hit"))
        self.assertFalse(out.get("pullback_force"))

    def test_vision_attachments_compile_rocksaw_depth(self):
        item = {
            "title": "Vermeer RTX1250",
            "make": "Vermeer",
            "model": "RTX1250",
            "description": "Ride-on.",
        }
        jpeg = Path(tempfile.gettempdir()) / "bam-vision.jpg"
        jpeg.write_bytes(b"\xff\xd8\xff\xd9")
        os.environ["GEMINI_API_KEY"] = "test-key"
        payload = {
            "candidates": [{
                "content": {
                    "parts": [{
                        "text": json.dumps({
                            "make": "Vermeer",
                            "model": "RTX1250",
                            "detected_attachments": ["rocksaw", "vibratory plow"],
                        })
                    }]
                }
            }]
        }

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(payload).encode()

        with patch("crm.vision.urlopen", return_value=FakeResp()), \
             patch("crm.enrich.lookup_specs") as lookup:
            out = process_incoming_third_party_listing(item, image_path=str(jpeg))
        lookup.assert_not_called()
        self.assertIn("rocksaw", out["attachments"])
        self.assertIn("plow", out["attachments"])
        self.assertEqual(out["saw_depth"], "18-24 in")
        self.assertEqual(out["plow_depth"], "42 in")
        jpeg.unlink(missing_ok=True)

    def test_vision_without_key_does_not_call_network(self):
        jpeg = Path(tempfile.gettempdir()) / "bam-vision2.jpg"
        jpeg.write_bytes(b"\xff\xd8\xff\xd9")
        with patch("crm.vision.urlopen") as opener:
            out = detect_machine_from_image(str(jpeg), {"title": "Vermeer RTX1250"})
        opener.assert_not_called()
        self.assertEqual(out, {})
        jpeg.unlink(missing_ok=True)

    def test_vision_failure_does_not_block(self):
        jpeg = Path(tempfile.gettempdir()) / "bam-vision3.jpg"
        jpeg.write_bytes(b"\xff\xd8\xff\xd9")
        os.environ["GEMINI_API_KEY"] = "test-key"
        with patch("crm.vision.urlopen", side_effect=URLError("down")):
            out = process_incoming_third_party_listing({
                "title": "Vermeer D20x22 HDD",
                "make": "Vermeer",
                "model": "D20x22",
            }, image_path=str(jpeg))
        self.assertEqual(out["pullback_force"], "20,000 lbs")
        jpeg.unlink(missing_ok=True)
