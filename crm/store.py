"""Draft queue. A Marketplace import cannot be posted until it is verified."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from crm.marketplace import display_price, machine_fields

ROOT = Path(os.environ.get("BAM_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def queue_dir() -> Path:
    path = ROOT / "queue"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(draft_id: str) -> Path:
    if not draft_id or "/" in draft_id or ".." in draft_id:
        raise ValueError("Unknown draft.")
    return queue_dir() / f"{draft_id}.json"


def _mark_source(listing: dict) -> dict:
    """Stamp scrape vs staged. Matching never ranks staged inventory."""
    fields = machine_fields(listing)
    listing["model_category"] = listing.get("model_category") or fields.get("category") or ""
    source = str(listing.get("source_type") or "").strip().lower()
    if listing.get("is_staged") is True or source in ("staged", "internal", "original", "bam"):
        listing["is_staged"] = True
        listing["source_type"] = source or "staged"
        listing["source_platform"] = listing.get("source_platform") or "Staged"
        return listing
    url = str(listing.get("sourceUrl") or "")
    if "facebook.com" in url.lower() or listing.get("itemId"):
        listing["source_type"] = source or "facebook"
        listing["source_platform"] = listing.get("source_platform") or "Facebook Marketplace"
    elif source:
        listing["source_type"] = source
        listing["source_platform"] = listing.get("source_platform") or source
    else:
        listing["source_type"] = "scrape"
        listing["source_platform"] = listing.get("source_platform") or "Third-Party Scrape"
    listing["is_staged"] = False
    return listing


def create_draft(listing: dict, brochure: dict) -> dict:
    draft_id = uuid.uuid4().hex[:12]
    stored = _mark_source(dict(listing))
    stored["askingPrice"] = stored.get("price") or ""
    stored["price"] = ""
    draft = {
        "id": draft_id,
        "status": "pending_verification",
        "createdAt": _now(),
        "verifiedAt": None,
        "postedAt": None,
        "listing": stored,
        "brochure": brochure,
        "website": None,
    }
    _path(draft_id).write_text(json.dumps(draft, indent=2), encoding="utf-8")
    return draft


def get_draft(draft_id: str) -> dict:
    path = _path(draft_id)
    if not path.exists():
        raise ValueError("That draft is not in the CRM queue.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_draft(draft: dict) -> dict:
    _path(draft["id"]).write_text(json.dumps(draft, indent=2), encoding="utf-8")
    return draft


def iter_drafts():
    for path in sorted(queue_dir().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        yield json.loads(path.read_text(encoding="utf-8"))


def _place(location: str) -> tuple[str, str]:
    text = (location or "").strip()
    if "," not in text:
        return text, ""
    city, state = text.rsplit(",", 1)
    return city.strip(), state.strip()


def _sheet_value(listing: dict, *labels: str) -> str:
    wanted = {label.lower() for label in labels}
    for row in listing.get("spec_sheet") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("label") or "").lower() in wanted:
            return str(row.get("value") or "")
    return ""


def _thumb(listing: dict) -> str:
    photos = listing.get("photos") or []
    local = ""
    for photo in photos:
        src = str(photo or "")
        if src.startswith("/api/marketplace/photo/"):
            return src
        if src and not local:
            local = src
    return local


def summarize_draft(draft: dict) -> dict:
    listing = draft.get("listing") or {}
    fields = machine_fields(listing)
    card = draft.get("machineCard") or {}
    city, state = _place(listing.get("location") or "")
    attachments = fields.get("attachments") or listing.get("attachments") or []
    track = _sheet_value(listing, "Attachments") or ", ".join(str(item) for item in attachments if item)
    return {
        "id": draft["id"],
        "status": draft["status"],
        "title": listing.get("title") or "",
        "price": listing.get("price") or "",
        "ask": listing.get("askingPrice") or "",
        "displayPrice": display_price(listing),
        "photos": len(listing.get("photos") or []),
        "thumb": _thumb(listing),
        "year": fields.get("year") or "",
        "make": fields.get("make") or "",
        "model": fields.get("model") or "",
        "category": fields.get("category") or "",
        "hours": fields.get("hours") or "",
        "city": city,
        "state": state,
        "location": listing.get("location") or "",
        "engine": _sheet_value(listing, "Power", "Engine"),
        "track": track,
        "createdAt": draft.get("createdAt"),
        "brochurePdf": card.get("pdf") or "",
        "itemId": listing.get("itemId") or "",
        "source_type": listing.get("source_type") or "",
        "is_staged": bool(listing.get("is_staged")),
        "source_platform": listing.get("source_platform") or "",
        "model_category": listing.get("model_category") or fields.get("category") or "",
        "fresh": draft.get("status") == "pending_verification" and not listing.get("is_staged"),
    }


def list_drafts() -> list[dict]:
    return [summarize_draft(draft) for draft in iter_drafts()]


def find_by_item_id(item_id: str) -> dict | None:
    if not item_id:
        return None
    for draft in iter_drafts():
        if (draft.get("listing") or {}).get("itemId") == item_id:
            return draft
    return None


def verify_draft(draft_id: str, brochure: dict | None = None) -> dict:
    draft = get_draft(draft_id)
    if draft["status"] == "posted":
        raise ValueError("This listing is already posted.")
    if brochure:
        _apply_brochure(draft, brochure)
    draft["status"] = "verified"
    draft["verifiedAt"] = _now()
    if draft.get("brochure"):
        draft["brochure"]["status"] = draft["brochure"].get("status", "").replace(
            "Pending verification — not on the website", "Verified"
        )
        draft["brochure"]["lock"] = "Call or text to lock it down."
        ready = draft["brochure"].get("ready") or ""
        draft["brochure"]["ready"] = ready.replace("HELD FOR REVIEW", "READY TO MOVE")
        from crm.marketplace import brochure_photos

        draft["brochure"]["photos"] = brochure_photos(draft["brochure"].get("photos"))
    from crm.brochure_file import attach_brochure

    attach_brochure(draft)
    return save_draft(draft)


def save_verified_edits(draft_id: str, brochure: dict) -> dict:
    """Keep price edits made after verification. Pending drafts stay locked."""
    draft = get_draft(draft_id)
    if draft["status"] == "posted":
        raise ValueError("This listing is already posted.")
    if draft["status"] != "verified":
        raise PermissionError("Verify the brochure before editing the price.")
    _apply_brochure(draft, brochure)
    draft["listing"]["location"] = ""
    draft["listing"]["sourceUrl"] = ""
    return save_draft(draft)


_SAVED_PHOTO = re.compile(r"/api/marketplace/photo/[a-f0-9]{12}/\d{1,4}\.(jpg|png|gif|webp)")


def _saved_photo(src: str) -> bool:
    path = urlparse(src).path if "://" in src else src.split("?", 1)[0]
    return bool(_SAVED_PHOTO.fullmatch(path))


def _apply_brochure(draft: dict, brochure: dict) -> None:
    """Keep the Facebook photo links for the CRM. The sheet uses the saved files."""
    from crm.marketplace import edited_price

    sources = list((draft.get("listing") or {}).get("photos") or [])
    incoming = list(brochure.get("photos") or [])
    # The brochure only carries the first 10 photos. Keep every other listing photo.
    merged = list(sources)
    for index, src in enumerate(incoming):
        src = str(src or "")
        if not src or src.startswith("data:image/svg") or _saved_photo(src):
            continue
        if index < len(merged):
            merged[index] = src
        else:
            merged.append(src)
    from crm.marketplace import brochure_photos

    brochure = dict(brochure)
    brochure["photos"] = brochure_photos(incoming or sources)
    draft["brochure"] = brochure
    draft["listing"]["photos"] = merged or sources
    draft["listing"]["price"] = edited_price(brochure)


def post_draft(draft_id: str) -> dict:
    draft = get_draft(draft_id)
    if draft["status"] != "verified":
        raise PermissionError("Verify the brochure before posting it on the website.")
    listing = draft["listing"]
    draft["website"] = {
        "title": listing.get("title"),
        "price": listing.get("price") or "",
        "location": "",
        "description": listing.get("description"),
        "year": listing.get("year"),
        "hours": listing.get("hours"),
        "condition": listing.get("condition"),
        "photos": listing.get("photos") or [],
        "sourceUrl": "",
        "stock": ((draft.get("website") or {}).get("stock") or ""),
    }
    draft["status"] = "posted"
    draft["postedAt"] = _now()
    return save_draft(draft)
