import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

from crm import store
from crm.ingest import lead_from_payload
from crm.leads import upsert_lead
from crm.marketplace import parse_listing, to_brochure
from crm.match import process_marketplace_scrape_matches, rank_buyers, rank_machines, score_pair
from crm.server import Handler


FIXTURE = Path(__file__).parent / "fixtures" / "marketplace_item.html"
ITEM_URL = "https://www.facebook.com/marketplace/item/123456789012345/"


def _buyer(**extra):
    payload = {
        "name": "Jose Martinez",
        "phone": "9045550100",
        "email": "jose@fiber.example",
        "company": "East Coast Fiber",
        "source": "facebook",
        "want": {
            "category": "Directional Drills",
            "make": "Ditch Witch",
            "model": "JT20",
            "yearMin": 2018,
            "yearMax": 2024,
            "hoursMax": 4000,
            "budgetMax": 160000,
            "keywords": ["rods", "hdd"],
        },
    }
    payload.update(extra)
    return payload


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BAM_DATA_DIR"] = self.tmp.name
        store.ROOT = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_jt20_listing_hot_matches_hdd_buyer_and_skips_excavator_budget(self):
        listing = parse_listing(FIXTURE.read_text(encoding="utf-8"), ITEM_URL)
        draft = store.create_draft(listing, to_brochure(listing))
        hdd = upsert_lead(_buyer())
        excavator = upsert_lead(_buyer(
            name="Maya Cole",
            phone="9045550199",
            email="maya@earth.example",
            company="Cole Earthwork",
            want={
                "category": "Excavators",
                "make": "Caterpillar",
                "model": "320",
                "budgetMax": 90000,
            },
        ))
        row = score_pair(draft, hdd)
        self.assertGreaterEqual(row["score"], 70)
        self.assertEqual(row["tier"], "hot")
        self.assertIn("category", row["reasons"])
        self.assertIn("make", row["reasons"])
        self.assertIn("model", row["reasons"])
        self.assertEqual(row["price"], "$128,500")
        cold = score_pair(draft, excavator)
        self.assertLess(cold["score"], 45)
        buyers = rank_buyers(draft, [hdd, excavator])
        self.assertEqual(buyers[0]["leadId"], hdd["id"])
        machines = rank_machines(hdd, [draft])
        self.assertEqual(machines[0]["listingId"], draft["id"])
        self.assertEqual(draft["listing"]["source_type"], "facebook")
        self.assertFalse(draft["listing"]["is_staged"])

    def test_scrape_matcher_skips_staged_and_uses_category_map(self):
        listing = parse_listing(FIXTURE.read_text(encoding="utf-8"), ITEM_URL)
        scrape = store.create_draft(listing, to_brochure(listing))
        staged_listing = dict(listing)
        staged_listing["is_staged"] = True
        staged_listing["source_type"] = "staged"
        staged = store.create_draft(staged_listing, to_brochure(staged_listing))
        hdd = upsert_lead(_buyer())
        rows = process_marketplace_scrape_matches([scrape, staged], [hdd])
        ids = {row["listingId"] for row in rows}
        self.assertIn(scrape["id"], ids)
        self.assertNotIn(staged["id"], ids)
        self.assertEqual(rank_buyers(staged, [hdd]), [])
        hits = process_marketplace_scrape_matches(
            [
                {
                    "id": "fb1",
                    "source_type": "facebook",
                    "model_category": "Directional Drills",
                    "make": "Ditch Witch",
                    "model": "JT20",
                    "price": "$128,500",
                    "source_platform": "Facebook Marketplace",
                },
                {
                    "id": "st1",
                    "source_type": "staged",
                    "is_staged": True,
                    "model_category": "Directional Drills",
                    "make": "Ditch Witch",
                    "model": "JT20",
                    "price": "$1",
                },
            ],
            [{
                "id": "lead1",
                "name": "Ana Ruiz",
                "phone": "9045550111",
                "target_machinery_category": "Directional Drills",
            }],
        )
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["listingId"], "fb1")
        self.assertEqual(hits[0]["buyerName"], "Ana Ruiz")
        self.assertEqual(hits[0]["source"], "Facebook Marketplace")


class IngestTests(unittest.TestCase):
    def test_facebook_field_data_becomes_a_buyer_want(self):
        lead = lead_from_payload({
            "leadgen_id": "lead_88",
            "field_data": [
                {"name": "full_name", "values": ["Ana Ruiz"]},
                {"name": "phone_number", "values": ["9045550111"]},
                {"name": "email", "values": ["ana@ruiz.example"]},
                {"name": "make", "values": ["CAT"]},
                {"name": "machine", "values": ["320 GC"]},
                {"name": "category", "values": ["Excavators"]},
                {"name": "budget", "values": ["$185,000"]},
            ],
        })
        self.assertEqual(lead["name"], "Ana Ruiz")
        self.assertEqual(lead["externalId"], "lead_88")
        self.assertEqual(lead["source"], "facebook")
        self.assertEqual(lead["want"]["make"], "CAT")
        self.assertEqual(lead["want"]["model"], "320 GC")
        self.assertEqual(lead["want"]["budgetMax"], "185000")

    def test_page_ping_without_fields_is_rejected(self):
        with self.assertRaises(ValueError):
            lead_from_payload({
                "object": "page",
                "entry": [{"changes": [{"value": {"leadgen_id": "x"}}]}],
            })


class DeskServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BAM_DATA_DIR"] = self.tmp.name
        os.environ["BAM_INGEST_TOKEN"] = "desk-token"
        os.environ.pop("BAM_CRM_EMAIL", None)
        os.environ.pop("BAM_CRM_PASSWORD", None)
        store.ROOT = Path(self.tmp.name)
        os.environ.pop("ANAKIN_WIRE_API_KEY", None)
        self.specs_patch = patch("crm.enrich.lookup_specs", return_value=[])
        self.specs_patch.start()
        self.photo_patch = patch("crm.photos.fetch_image", side_effect=OSError("blocked"))
        self.photo_patch.start()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.photo_patch.stop()
        self.specs_patch.stop()
        self.httpd.shutdown()
        self.tmp.cleanup()
        os.environ.pop("BAM_INGEST_TOKEN", None)

    def _url(self, path):
        return f"http://127.0.0.1:{self.port}{path}"

    def _get(self, path):
        with urllib.request.urlopen(self._url(path)) as response:
            return json.loads(response.read().decode())

    def _post(self, path, payload, headers=None):
        req = urllib.request.Request(
            self._url(path),
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())

    def test_desk_one_call_and_hash_routes_stay_on_index(self):
        created = self._post("/api/marketplace/parse", {
            "url": ITEM_URL,
            "html": FIXTURE.read_text(encoding="utf-8"),
        })
        lead = self._post("/api/leads", _buyer())
        desk = self._get("/api/desk")
        self.assertTrue(desk["ok"])
        self.assertEqual(desk["counts"]["units"], 1)
        self.assertEqual(desk["counts"]["buyers"], 1)
        self.assertGreaterEqual(desk["counts"]["hot"], 1)
        self.assertEqual(desk["drafts"][0]["displayPrice"], "$128,500")
        self.assertEqual(desk["matches"][0]["listingId"], created["draft"]["id"])
        self.assertEqual(desk["matches"][0]["leadId"], lead["lead"]["id"])
        ranked = self._get("/api/matches?listing=" + created["draft"]["id"])
        self.assertEqual(ranked["matches"][0]["leadName"], "Jose Martinez")
        with urllib.request.urlopen(self._url("/")) as response:
            html = response.read().decode()
        self.assertIn("BAM Desk", html)
        self.assertIn("#/unit/", html)
        self.assertIn("#/lead/", html)
        self.assertIn("/for/", html)
        self.assertIn("Prepare PDF", html)
        self.assertIn("Ingest buyer", html)
        self.assertNotIn("Theme</span>", html)
        self.assertNotIn("Post to website", html)

    def test_verify_packs_hot_buyers_and_desk_accepts_facebook_json(self):
        created = self._post("/api/marketplace/parse", {
            "url": ITEM_URL,
            "html": FIXTURE.read_text(encoding="utf-8"),
        })
        ingested = self._post("/api/leads", {
            "leadgen_id": "fb-desk",
            "field_data": [
                {"name": "full_name", "values": ["Jose Martinez"]},
                {"name": "phone_number", "values": ["9045550100"]},
                {"name": "email", "values": ["jose@fiber.example"]},
                {"name": "make", "values": ["Ditch Witch"]},
                {"name": "machine", "values": ["JT20"]},
                {"name": "category", "values": ["Directional Drills"]},
                {"name": "budget", "values": ["160000"]},
            ],
        })
        self.assertEqual(ingested["lead"]["externalId"], "fb-desk")
        self.assertGreaterEqual(ingested["counts"]["hot"], 1)
        verified = self._post("/api/marketplace/verify", {"id": created["draft"]["id"]})
        self.assertEqual(len(verified["packets"]), 1)
        self.assertEqual(verified["packets"][0]["leadId"], ingested["lead"]["id"])
        self.assertTrue(verified["packets"][0]["pdf"].endswith(".pdf"))
        again = self._post("/api/marketplace/verify", {"id": created["draft"]["id"]})
        self.assertTrue(again["packets"][0]["already"])

    def test_dead_paths_are_rewritten_or_json_404(self):
        with urllib.request.urlopen(self._url("/desk")) as response:
            html = response.read().decode()
        self.assertIn("BAM Desk", html)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self._url("/api/theme.php"))
        self.assertEqual(caught.exception.code, 404)
        with self.assertRaises(urllib.error.HTTPError) as gone:
            urllib.request.urlopen(self._url("/Code"))
        self.assertEqual(gone.exception.code, 404)
        again = self._post("/api/marketplace/parse", {
            "url": ITEM_URL,
            "html": FIXTURE.read_text(encoding="utf-8"),
        })
        second = self._post("/api/marketplace/parse", {
            "url": ITEM_URL,
            "html": FIXTURE.read_text(encoding="utf-8"),
        })
        self.assertEqual(again["draft"]["id"], second["draft"]["id"])

    def test_ingest_webhook_needs_token_then_ranks(self):
        self._post("/api/marketplace/parse", {
            "url": ITEM_URL,
            "html": FIXTURE.read_text(encoding="utf-8"),
        })
        req = urllib.request.Request(
            self._url("/api/ingest/leads"),
            data=json.dumps(_buyer(externalId="fb-1")).encode(),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(req)
        self.assertEqual(caught.exception.code, 401)
        ingested = self._post(
            "/api/ingest/leads",
            {
                "field_data": [
                    {"name": "full_name", "values": ["Jose Martinez"]},
                    {"name": "phone_number", "values": ["9045550100"]},
                    {"name": "email", "values": ["jose@fiber.example"]},
                    {"name": "make", "values": ["Ditch Witch"]},
                    {"name": "machine", "values": ["JT20"]},
                    {"name": "category", "values": ["Directional Drills"]},
                    {"name": "budget", "values": ["160000"]},
                ],
                "leadgen_id": "fb-1",
            },
            headers={"X-BAM-Token": "desk-token"},
        )
        self.assertEqual(ingested["lead"]["externalId"], "fb-1")
        self.assertGreaterEqual(ingested["counts"]["hot"], 1)
        packet = self._post("/api/matches/brochure", {
            "listingId": ingested["drafts"][0]["id"],
            "leadId": ingested["lead"]["id"],
        })
        self.assertTrue(packet["packet"]["pdf"].endswith(".pdf"))
        self.assertEqual(packet["lead"]["packets"][0]["listingId"], ingested["drafts"][0]["id"])
        listing = parse_listing(FIXTURE.read_text(encoding="utf-8"), ITEM_URL)
        self.assertEqual(listing["title"], "2019 Ditch Witch JT20 Horizontal Drill")


if __name__ == "__main__":
    unittest.main()
