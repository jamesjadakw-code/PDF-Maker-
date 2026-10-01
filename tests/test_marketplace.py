import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from crm.marketplace import machine_fields, marketplace_url, parse_listing, to_brochure
from crm.server import Handler
from crm import store
from http.server import ThreadingHTTPServer


FIXTURE = Path(__file__).parent / "fixtures" / "marketplace_item.html"
ITEM_URL = "https://www.facebook.com/marketplace/item/123456789012345/"


class ParseTests(unittest.TestCase):
    def test_rejects_non_marketplace_urls(self):
        with self.assertRaises(ValueError):
            marketplace_url("https://example.com/marketplace/item/1")
        with self.assertRaises(ValueError):
            marketplace_url("https://www.facebook.com/profile.php")

    def test_extracts_every_listing_photo_and_the_facts(self):
        listing = parse_listing(FIXTURE.read_text(encoding="utf-8"), ITEM_URL)
        self.assertEqual(listing["title"], "2019 Ditch Witch JT20 Horizontal Drill")
        self.assertEqual(listing["price"], "$128,500")
        self.assertEqual(listing["location"], "Jacksonville, FL")
        self.assertEqual(listing["hours"], "1840")
        self.assertEqual(listing["year"], "2019")
        self.assertEqual(len(listing["photos"]), 7)
        self.assertTrue(all("emoji" not in url for url in listing["photos"]))
        self.assertIn("photo6.jpg", listing["photos"][-1])

    def test_brochure_stays_unpublished(self):
        listing = parse_listing(FIXTURE.read_text(encoding="utf-8"), ITEM_URL)
        brochure = to_brochure(listing, pending=True)
        self.assertIn("Pending verification", brochure["status"])
        self.assertIn("HELD FOR REVIEW", brochure["ready"])
        self.assertEqual(len(brochure["photos"]), 7)
        self.assertEqual(len(brochure["specs"]), 26)
        sheet = " ".join([
            brochure["status"], brochure["subtitle"], brochure["priceLine"],
            brochure["condition"], brochure["page2Title"], *brochure["specs"],
        ])
        self.assertNotIn("Jacksonville", sheet)
        self.assertNotIn("facebook.com", sheet.lower())
        self.assertNotIn("Facebook", sheet)
        self.assertNotIn("128,500", sheet)
        self.assertNotIn("128500", sheet)
        labels = [row.split("|", 1)[0].strip() for row in brochure["specs"]]
        self.assertIn("Price", labels)
        self.assertNotIn("Location", labels)
        self.assertNotIn("Source", labels)
        self.assertNotIn("Item URL", labels)
        self.assertNotIn("City", labels)
        self.assertNotIn("Listing ID", labels)
        self.assertEqual(len(brochure["specs"]), 26)

    def test_machine_fields_match_the_crm_unit_form(self):
        listing = parse_listing(FIXTURE.read_text(encoding="utf-8"), ITEM_URL)
        fields = machine_fields(listing)
        self.assertEqual(fields["year"], "2019")
        self.assertEqual(fields["make"], "Ditch Witch")
        self.assertEqual(fields["model"], "JT20")
        self.assertEqual(fields["category"], "Directional Drills")
        self.assertEqual(fields["hours"], "1840")
        self.assertEqual(fields["price"], "128500")
        self.assertEqual(fields["location"], "Jacksonville, FL")


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BAM_DATA_DIR"] = self.tmp.name
        store.ROOT = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_post_is_blocked_until_verified(self):
        listing = parse_listing(FIXTURE.read_text(encoding="utf-8"), ITEM_URL)
        draft = store.create_draft(listing, to_brochure(listing))
        self.assertEqual(draft["listing"]["price"], "")
        self.assertEqual(draft["listing"]["askingPrice"], "$128,500")
        edited = to_brochure(listing)
        edited["priceLine"] = "PRICE: $149,000  •  +1-904-767-5232  •  sales@bigassmotors.com"
        with self.assertRaises(PermissionError):
            store.post_draft(draft["id"])
        with self.assertRaises(PermissionError):
            store.save_verified_edits(draft["id"], edited)
        verified = store.verify_draft(draft["id"])
        self.assertEqual(verified["status"], "verified")
        self.assertEqual(verified["listing"]["price"], "")
        saved = store.save_verified_edits(draft["id"], edited)
        self.assertEqual(saved["listing"]["price"], "$149,000")
        self.assertEqual(saved["listing"]["location"], "")
        self.assertEqual(saved["listing"]["sourceUrl"], "")
        posted = store.post_draft(draft["id"])
        self.assertEqual(posted["status"], "posted")
        self.assertEqual(posted["website"]["price"], "$149,000")
        self.assertEqual(posted["website"]["location"], "")
        self.assertEqual(posted["website"]["sourceUrl"], "")
        self.assertEqual(len(posted["website"]["photos"]), 7)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BAM_DATA_DIR"] = self.tmp.name
        os.environ.pop("BAM_CRM_EMAIL", None)
        os.environ.pop("BAM_CRM_PASSWORD", None)
        os.environ.pop("BAM_CRM_BASE", None)
        store.ROOT = Path(self.tmp.name)
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.tmp.cleanup()

    def _post(self, path, payload):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())

    def test_api_holds_the_listing_for_verification(self):
        created = self._post("/api/marketplace/parse", {
            "url": ITEM_URL,
            "html": FIXTURE.read_text(encoding="utf-8"),
        })
        self.assertTrue(created["ok"])
        self.assertEqual(created["draft"]["status"], "pending_verification")
        draft_id = created["draft"]["id"]
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/api/marketplace/post",
            data=json.dumps({"id": draft_id}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(req)
        self.assertEqual(caught.exception.code, 409)
        verified = self._post("/api/marketplace/verify", {"id": draft_id})
        self.assertEqual(verified["draft"]["status"], "verified")
        posted = self._post("/api/marketplace/post", {"id": draft_id})
        self.assertEqual(posted["draft"]["status"], "posted")
        self.assertFalse(posted["draft"]["website"].get("sent"))
        self.assertNotIn("crm", posted["draft"]["website"])


class FakeCrmTests(unittest.TestCase):
    def setUp(self):
        from http.server import BaseHTTPRequestHandler

        class Fake(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                return

            def do_GET(self):
                body = '<input type="hidden" name="_csrf" value="abc123">'
                if self.path.startswith("/inventory/login"):
                    body += '<input type="password" name="password">'
                if self.path.startswith("/inventory/unit.php"):
                    body += "<option selected>Draft</option> BAM-10055 · Draft"
                self._send(200, body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length).decode()
                Fake.posts.append((self.path, raw))
                if "list_now" in raw:
                    self._send(500, "refused")
                    return
                if self.path.startswith("/inventory/login"):
                    self._send(200, "Add from URL")
                    return
                self.send_response(302)
                self.send_header("Location", "/inventory/unit.php?id=55")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _send(self, status, body):
                raw = body.encode()
                self.send_response(status)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        Fake.posts = []
        self.fake_cls = Fake
        self.crm = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
        self.thread = threading.Thread(target=self.crm.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.crm.server_address[1]}"
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["BAM_DATA_DIR"] = self.tmp.name
        store.ROOT = Path(self.tmp.name)

    def tearDown(self):
        self.crm.shutdown()
        self.tmp.cleanup()
        os.environ.pop("BAM_CRM_EMAIL", None)
        os.environ.pop("BAM_CRM_PASSWORD", None)
        os.environ.pop("BAM_CRM_BASE", None)

    def test_verified_post_files_a_hidden_draft_and_does_not_list_it(self):
        from crm.live_inventory import LiveInventory
        from crm.server import _file_hidden_draft

        listing = parse_listing(FIXTURE.read_text(encoding="utf-8"), ITEM_URL)
        client = LiveInventory("sales@bigassmotors.com", "secret", base=self.base)
        filed = client.create_hidden_draft(listing)
        self.assertEqual(filed["status"], "Draft")
        self.assertFalse(filed["onWebsite"])
        self.assertIn("unit.php?id=55", filed["url"])
        create = [body for path, body in self.fake_cls.posts if path.startswith("/inventory/add_url")]
        self.assertEqual(len(create), 1)
        self.assertIn("do=create", create[0])
        self.assertNotIn("list_now", create[0])
        self.assertEqual(create[0].count("photos%5B%5D="), 7)
        self.assertIn("hours=1840", create[0])
        self.assertNotIn("price=128500", create[0])
        self.assertNotIn("Jacksonville", create[0])
        self.assertNotIn("marketplace", create[0].lower())
        self.assertIn("price=", create[0])
        self.assertIn("location=", create[0])
        self.assertIn("url=", create[0])

        os.environ["BAM_CRM_EMAIL"] = "sales@bigassmotors.com"
        os.environ["BAM_CRM_PASSWORD"] = "secret"
        os.environ["BAM_CRM_BASE"] = self.base
        draft = store.create_draft(listing, to_brochure(listing))
        store.verify_draft(draft["id"])
        edited = to_brochure(listing)
        edited["priceLine"] = "PRICE: $149,000"
        store.save_verified_edits(draft["id"], edited)
        held = store.get_draft(draft["id"])
        crm_unit = _file_hidden_draft(held)
        self.assertEqual(crm_unit["id"], "55")
        creates = [body for path, body in self.fake_cls.posts if path.startswith("/inventory/add_url")]
        self.assertEqual(len(creates), 2)
        self.assertNotIn("price=128500", creates[1])
        self.assertIn("price=149000", creates[1])
        self.assertNotIn("Jacksonville", creates[1])
        self.assertNotIn("marketplace", creates[1].lower())
        self.assertTrue(all("list_now" not in body for _path, body in self.fake_cls.posts))


if __name__ == "__main__":
    unittest.main()
