"""Draft queue. A Marketplace import cannot be posted until it is verified."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

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
    draft = {
        "id": draft_id,
        "status": "pending_verification",
        "createdAt": _now(),
        "verifiedAt": None,
        "postedAt": None,
        "listing": listing,
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
        draft["brochure"] = brochure
        draft["listing"]["photos"] = brochure.get("photos") or draft["listing"].get("photos") or []
    draft["status"] = "verified"
    draft["verifiedAt"] = _now()
    if draft.get("brochure"):
        draft["brochure"]["status"] = draft["brochure"].get("status", "").replace(
            "Pending verification — not on the website", "Verified"
        )
        draft["brochure"]["lock"] = "Call or text to lock it down."
        ready = draft["brochure"].get("ready") or ""
        draft["brochure"]["ready"] = ready.replace("HELD FOR REVIEW", "READY TO MOVE")
    return save_draft(draft)


def post_draft(draft_id: str) -> dict:
    draft = get_draft(draft_id)
    if draft["status"] != "verified":
        raise PermissionError("Verify the brochure before posting it on the website.")
    listing = draft["listing"]
    draft["website"] = {
        "title": listing.get("title"),
        "price": listing.get("price"),
        "location": listing.get("location"),
        "description": listing.get("description"),
        "year": listing.get("year"),
        "hours": listing.get("hours"),
        "condition": listing.get("condition"),
        "photos": listing.get("photos") or [],
        "sourceUrl": listing.get("sourceUrl"),
        "stock": f"FB-{(listing.get('itemId') or draft_id)[-6:]}",
    }
    draft["status"] = "posted"
    draft["postedAt"] = _now()
    return save_draft(draft)
