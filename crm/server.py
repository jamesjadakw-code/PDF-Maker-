"""Desk server: one split-pane workspace, Marketplace intake, lead ingest, matching."""

from __future__ import annotations

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, build_opener

from crm.brochure_file import attach_brochure, pdf_path, save_upload
from crm.desk import matches_for, packet_hot_matches, snapshot
from crm.ingest import lead_from_payload
from crm.leads import attach_packet, get_lead, list_leads, upsert_lead
from crm.marketplace import brochure_photos, marketplace_url, parse_listing, to_brochure
from crm.photos import photo_path, save_listing_photos
from crm.specs import lookup_specs, specs_missing
from crm.store import (
    create_draft,
    find_by_item_id,
    get_draft,
    list_drafts,
    post_draft,
    save_draft,
    save_verified_edits,
    verify_draft,
)

ROOT = Path(__file__).resolve().parent.parent
MAX_HTML = 2_000_000
SPEC_SECONDS = 12

GET_EXACT = {
    "/api/desk": "desk",
    "/api/marketplace/queue": "queue",
    "/api/leads": "leads",
    "/api/matches": "matches",
}
POST_EXACT = {
    "/api/marketplace/scrape": "scrape",
    "/api/marketplace/parse": "parse",
    "/api/marketplace/verify": "verify",
    "/api/marketplace/brochure": "brochure",
    "/api/marketplace/post": "post",
    "/api/leads": "lead_upsert",
    "/api/ingest/leads": "ingest_leads",
    "/api/ingest/listings": "ingest_listings",
    "/api/matches/brochure": "match_brochure",
}


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
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/Code":
            return self._json(404, {"ok": False, "error": "That duplicate brochure page is gone. Use /"})
        if path in GET_EXACT:
            return self._get_api(GET_EXACT[path], query)
        if path.startswith("/api/marketplace/draft/"):
            draft_id = path.rsplit("/", 1)[-1]
            try:
                return self._json(200, {"ok": True, "draft": get_draft(draft_id)})
            except ValueError as exc:
                return self._json(404, {"ok": False, "error": str(exc)})
        if path.startswith("/api/leads/") and path != "/api/leads/":
            lead_id = path.rsplit("/", 1)[-1]
            try:
                return self._json(200, {"ok": True, "lead": get_lead(lead_id)})
            except ValueError as exc:
                return self._json(404, {"ok": False, "error": str(exc)})
        if path.startswith("/api/marketplace/photo/"):
            return self._photo(path)
        if path.startswith("/api/marketplace/brochure/"):
            return self._brochure(path)
        if path.startswith("/api/"):
            return self._json(404, {"ok": False, "error": "Unknown action."})
        if path in ("/", "/index.html", "/desk", "/desk/"):
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self._body(28_000_000 if path == "/api/marketplace/brochure" else None)
            if path not in POST_EXACT:
                return self._json(404, {"ok": False, "error": "Unknown action."})
            return self._post_api(POST_EXACT[path], payload)
        except PermissionError as exc:
            return self._json(409 if "token" not in str(exc).lower() else 401, {"ok": False, "error": str(exc)})
        except ValueError as exc:
            return self._json(400, {"ok": False, "error": str(exc)})
        except (HTTPError, URLError, TimeoutError) as exc:
            return self._json(502, {"ok": False, "error": f"Could not reach Facebook: {exc}"})

    def _get_api(self, action: str, query: dict):
        if action == "desk":
            return self._json(200, {"ok": True, **snapshot()})
        if action == "queue":
            return self._json(200, {"ok": True, "drafts": list_drafts()})
        if action == "leads":
            return self._json(200, {"ok": True, "leads": list_leads()})
        listing_id = _q(query, "listing", "listingId")
        lead_id = _q(query, "lead", "leadId")
        try:
            return self._json(200, matches_for(listing_id, lead_id))
        except ValueError as exc:
            return self._json(404, {"ok": False, "error": str(exc)})

    def _post_api(self, action: str, payload: dict):
        if action == "scrape":
            url = marketplace_url(payload.get("url") or "")
            html = FETCHER.fetch(url)
            draft = _hold(html, url)
            return self._json(200, {"ok": True, "draft": draft, **snapshot()})
        if action == "parse":
            url = marketplace_url(payload.get("url") or "https://www.facebook.com/marketplace/item/0/")
            html = payload.get("html") or ""
            if not html.strip():
                raise ValueError("Paste the listing page HTML.")
            if len(html) > MAX_HTML:
                raise ValueError("That page is too large to import.")
            draft = _hold(html, url)
            return self._json(200, {"ok": True, "draft": draft, **snapshot()})
        if action == "verify":
            draft = verify_draft(payload.get("id") or "", payload.get("brochure"))
            packets = packet_hot_matches(draft)
            return self._json(200, {"ok": True, "draft": get_draft(draft["id"]), "packets": packets, **snapshot()})
        if action == "brochure":
            draft_id = payload.get("id") or ""
            held = get_draft(draft_id)
            if held.get("status") not in ("verified", "posted"):
                raise PermissionError("Verify the brochure before saving the PDF.")
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
        if action == "post":
            draft_id = payload.get("id") or ""
            if payload.get("brochure"):
                save_verified_edits(draft_id, payload.get("brochure"))
            held = get_draft(draft_id)
            crm_unit = _file_hidden_draft(held)
            draft = post_draft(draft_id)
            draft["website"]["sent"] = False
            if crm_unit:
                draft["website"]["crm"] = crm_unit
                draft["website"]["stock"] = crm_unit.get("stock") or ""
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
        if action == "lead_upsert":
            body = payload
            if "field_data" in payload or payload.get("object") == "page" or payload.get("leadgen_id"):
                body = lead_from_payload(payload)
            lead = upsert_lead(body)
            return self._json(200, {"ok": True, "lead": lead, **snapshot()})
        if action == "ingest_leads":
            self._require_ingest_token()
            lead = upsert_lead(lead_from_payload(payload))
            return self._json(200, {"ok": True, "lead": lead, **snapshot()})
        if action == "ingest_listings":
            self._require_ingest_token()
            urls = list(payload.get("urls") or [])
            if payload.get("url"):
                urls.insert(0, payload.get("url"))
            urls = [item.strip() for item in urls if str(item).strip()]
            if not urls:
                raise ValueError("Send at least one Marketplace URL.")
            if len(urls) > 10:
                raise ValueError("Send at most 10 listing URLs per ingest.")
            drafts = []
            errors = []
            for raw_url in urls:
                try:
                    url = marketplace_url(raw_url)
                    drafts.append(_hold(FETCHER.fetch(url), url))
                except (ValueError, HTTPError, URLError, TimeoutError, OSError) as exc:
                    errors.append({"url": raw_url, "error": str(exc)})
            return self._json(200, {"ok": True, "drafts": drafts, "errors": errors, **snapshot()})
        if action == "match_brochure":
            return self._json(200, _prepare_match_brochure(payload))
        return self._json(404, {"ok": False, "error": "Unknown action."})

    def _require_ingest_token(self):
        expected = os.environ.get("BAM_INGEST_TOKEN", "").strip()
        if not expected:
            raise PermissionError("Set BAM_INGEST_TOKEN before accepting inbound leads.")
        auth = self.headers.get("Authorization") or ""
        bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        got = (self.headers.get("X-BAM-Token") or bearer).strip()
        if got != expected:
            raise PermissionError("Ingest token does not match.")

    def _body(self, limit: int | None = None) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > (limit or MAX_HTML + 10_000):
            raise ValueError("Request is too large.")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode() or "{}")
        except json.JSONDecodeError as extra:
            raise ValueError("Send JSON.") from extra
        if not isinstance(data, dict):
            raise ValueError("Send a JSON object.")
        return data

    def _brochure(self, path: str):
        name = path.rsplit("/", 1)[-1]
        draft_id = name[:-4] if name.endswith(".pdf") else ""
        try:
            get_draft(draft_id)
            file = pdf_path(draft_id)
        except ValueError as extra:
            return self._json(404, {"ok": False, "error": str(extra)})
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
        except ValueError as extra:
            return self._json(404, {"ok": False, "error": str(extra)})
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


def _q(query: dict, *names: str) -> str:
    for name in names:
        values = query.get(name) or []
        if values and values[0]:
            return values[0]
    return ""


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


def _fill_oem_specs(listing: dict) -> None:
    if not specs_missing(listing):
        listing["specsStatus"] = "ready"
        return
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            listing["oemSpecs"] = pool.submit(lookup_specs, listing).result(timeout=SPEC_SECONDS)
    except (OSError, ValueError, TimeoutError):
        listing["oemSpecs"] = []
    listing["specsStatus"] = "ready" if listing.get("oemSpecs") else "none"


def _hold(html: str, url: str) -> dict:
    listing = parse_listing(html, url)
    existing = find_by_item_id(listing.get("itemId") or "")
    if existing and existing.get("status") != "pending_verification":
        return existing
    _fill_oem_specs(listing)
    brochure = to_brochure(listing, pending=True)
    if existing and existing.get("status") == "pending_verification":
        stored = dict(listing)
        stored["askingPrice"] = stored.get("price") or (existing.get("listing") or {}).get("askingPrice") or ""
        stored["price"] = (existing.get("listing") or {}).get("price") or ""
        existing["listing"] = stored
        existing["brochure"] = brochure
        draft = save_draft(existing)
    else:
        draft = create_draft(listing, brochure)
    urls = list(listing.get("photos") or [])
    if urls:
        draft["brochure"]["photos"] = brochure_photos(save_listing_photos(draft["id"], urls))
        save_draft(draft)
    return draft


def _prepare_match_brochure(payload: dict) -> dict:
    draft = get_draft(payload.get("listingId") or payload.get("id") or "")
    lead = get_lead(payload.get("leadId") or "")
    from crm.match import score_pair

    row = score_pair(draft, lead)
    existing = [
        item for item in (lead.get("packets") or [])
        if item.get("listingId") == draft["id"]
    ]
    if existing:
        return {"ok": True, "draft": draft, "lead": lead, "match": row, "packet": existing[0], **snapshot()}
    attach_brochure(draft)
    save_draft(draft)
    pdf = (draft.get("machineCard") or {}).get("pdf") or ""
    packet = {
        "listingId": draft["id"],
        "leadId": lead["id"],
        "title": row["unitTitle"],
        "score": row["score"],
        "pdf": pdf,
        "preparedAt": lead.get("updatedAt") or "",
    }
    saved = attach_packet(lead["id"], packet)
    packet["preparedAt"] = saved.get("updatedAt") or packet["preparedAt"]
    return {"ok": True, "draft": draft, "lead": saved, "match": row, "packet": packet, **snapshot()}


def main():
    port = int(os.environ.get("PORT", "8780"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"BAM desk on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
