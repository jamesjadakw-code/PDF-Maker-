"""Draft queue. A Marketplace import cannot be posted until it is verified."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

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


def create_draft(listing: dict, brochure: dict) -> dict:
    draft_id = uuid.uuid4().hex[:12]
    stored = dict(listing)
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


def list_drafts() -> list[dict]:
    rows = []
    for path in sorted(queue_dir().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        draft = json.loads(path.read_text(encoding="utf-8"))
        listing = draft.get("listing") or {}
        rows.append({
            "id": draft["id"],
            "status": draft["status"],
            "title": listing.get("title") or "",
            "price": listing.get("price") or "",
            "photos": len(listing.get("photos") or []),
            "createdAt": draft.get("createdAt"),
        })
    return rows


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
        "stock": "",
    }
    draft["status"] = "posted"
    draft["postedAt"] = _now()
    return save_draft(draft)
