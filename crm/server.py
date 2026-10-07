"""Local CRM server: scrape one Marketplace URL, hold it, then post after verification."""

from __future__ import annotations

import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from crm.brochure_file import pdf_path, save_upload
from crm.marketplace import brochure_photos, marketplace_url, parse_listing, to_brochure
from crm.photos import photo_path, save_listing_photos
from crm.specs import lookup_specs, specs_missing
from crm.store import create_draft, get_draft, list_drafts, post_draft, save_draft, save_verified_edits, verify_draft

ROOT = Path(__file__).resolve().parent.parent
MAX_HTML = 2_000_000


class StayOnFacebook:
    """Refuse redirects that leave Facebook."""

    def __init__(self):
        from urllib.request import HTTPRedirectHandler

        class Guard(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                marketplace_url(newurl)
                return super().redirect_request(req, fp, code, msg, headers, newurl)

        self.opener = build_opener(Guard)

    def fetch(self, url: str) -> str:
        request = Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; BAM-CRM/1.0; +https://www.bigassmotors.com)",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with self.opener.open(request, timeout=20) as response:
            raw = response.read(MAX_HTML + 1)
        if len(raw) > MAX_HTML:
            raise ValueError("That page is too large to import.")
        return raw.decode("utf-8", "replace")


FETCHER = StayOnFacebook()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt, *args):
        print("[crm]", fmt % args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/marketplace/queue":
            return self._json(200, {"ok": True, "drafts": list_drafts()})
        if path.startswith("/api/marketplace/draft/"):
            draft_id = path.rsplit("/", 1)[-1]
            try:
                return self._json(200, {"ok": True, "draft": get_draft(draft_id)})
            except ValueError as exc:
                return self._json(404, {"ok": False, "error": str(exc)})
        if path.startswith("/api/marketplace/photo/"):
            return self._photo(path)
        if path.startswith("/api/marketplace/brochure/"):
            return self._brochure(path)
        if path in ("/", "/index.html"):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self._body(28_000_000 if path == "/api/marketplace/brochure" else None)
            if path == "/api/marketplace/scrape":
                url = marketplace_url(payload.get("url") or "")
                html = FETCHER.fetch(url)
                return self._json(200, {"ok": True, "draft": _hold(html, url)})
            if path == "/api/marketplace/parse":
                url = marketplace_url(payload.get("url") or "https://www.facebook.com/marketplace/item/0/")
                html = payload.get("html") or ""
                if not html.strip():
                    raise ValueError("Paste the listing page HTML.")
                if len(html) > MAX_HTML:
                    raise ValueError("That page is too large to import.")
                return self._json(200, {"ok": True, "draft": _hold(html, url)})
            if path == "/api/marketplace/verify":
                draft = verify_draft(payload.get("id") or "", payload.get("brochure"))
                return self._json(200, {"ok": True, "draft": draft})
            if path == "/api/marketplace/brochure":
                draft_id = payload.get("id") or ""
                held = get_draft(draft_id)
                if held.get("status") not in ("verified", "posted"):
                    raise PermissionError("Verify the brochure before saving the PDF.")
                import base64
                try:
                    raw = base64.b64decode(payload.get("pdf") or "", validate=True)
                except (ValueError, TypeError) as exc:
                    raise ValueError("Send the brochure PDF.") from exc
                save_upload(draft_id, raw)
                card = held.get("machineCard") or {}
                card["brochureSaved"] = True
                card["pdf"] = f"/api/marketplace/brochure/{draft_id}.pdf"
                held["machineCard"] = card
                save_draft(held)
                return self._json(200, {"ok": True, "draft": held})
            if path == "/api/marketplace/post":
                draft_id = payload.get("id") or ""
                if payload.get("brochure"):
                    save_verified_edits(draft_id, payload.get("brochure"))
                held = get_draft(draft_id)
                crm_unit = _file_hidden_draft(held)
                draft = post_draft(draft_id)
                draft["website"]["sent"] = False
                if crm_unit:
                    draft["website"]["crm"] = crm_unit
                    draft["website"]["note"] = (
                        "Hidden Draft on the CRM. Not on bigassmotors.com. "
                        "Open the unit and choose List Now only after the photos and write-up check out."
                    )
                else:
                    draft["website"]["note"] = (
                        "Verified and queued for the website. Not sent to bigassmotors.com from this server."
                    )
                save_draft(draft)
                return self._json(200, {"ok": True, "draft": draft})
            return self._json(404, {"ok": False, "error": "Unknown action."})
        except PermissionError as exc:
            return self._json(409, {"ok": False, "error": str(exc)})
        except ValueError as exc:
            return self._json(400, {"ok": False, "error": str(exc)})
        except (HTTPError, URLError, TimeoutError) as exc:
            return self._json(502, {"ok": False, "error": f"Could not reach Facebook: {exc}"})

    def _body(self, limit: int | None = None) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > (limit or MAX_HTML + 10_000):
            raise ValueError("Request is too large.")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("Send JSON.") from exc
        if not isinstance(data, dict):
            raise ValueError("Send a JSON object.")
        return data

    def _brochure(self, path: str):
        name = path.rsplit("/", 1)[-1]
        draft_id = name[:-4] if name.endswith(".pdf") else ""
        try:
            get_draft(draft_id)
            file = pdf_path(draft_id)
        except ValueError as exc:
            return self._json(404, {"ok": False, "error": str(exc)})
        if not file.is_file():
            return self._json(404, {"ok": False, "error": "That brochure PDF is not on the machine card yet."})
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _photo(self, path: str):
        parts = [part for part in path.split("/") if part]
        if len(parts) != 5:
            return self._json(404, {"ok": False, "error": "Unknown photo."})
        try:
            file = photo_path(parts[3], parts[4])
        except ValueError as exc:
            return self._json(404, {"ok": False, "error": str(exc)})
        data = file.read_bytes()
        kind = {
            ".jpg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }[file.suffix]
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _file_hidden_draft(draft: dict) -> dict | None:
    email = os.environ.get("BAM_CRM_EMAIL", "").strip()
    password = os.environ.get("BAM_CRM_PASSWORD", "")
    if not email or not password:
        return None
    if draft.get("status") != "verified":
        raise PermissionError("Verify the brochure before filing it on the CRM.")
    from crm.live_inventory import CRM_BASE, LiveInventory

    base = os.environ.get("BAM_CRM_BASE", CRM_BASE)
    return LiveInventory(email, password, base=base).create_hidden_draft(
        draft["listing"], draft.get("brochure")
    )


def _hold(html: str, url: str) -> dict:
    listing = parse_listing(html, url)
    if specs_missing(listing):
        try:
            listing["oemSpecs"] = lookup_specs(listing)
        except (OSError, ValueError):
            listing["oemSpecs"] = []
    brochure = to_brochure(listing, pending=True)
    draft = create_draft(listing, brochure)
    urls = list(listing.get("photos") or [])
    if urls:
        draft["brochure"]["photos"] = brochure_photos(save_listing_photos(draft["id"], urls))
        save_draft(draft)
    return draft


def main():
    port = int(os.environ.get("PORT", "8780"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"BAM CRM brochure intake on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
