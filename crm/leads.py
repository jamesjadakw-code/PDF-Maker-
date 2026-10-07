"""Buyer leads. One JSON file per lead. No extra CRM tabs or copies."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from crm import store


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def leads_dir() -> Path:
    path = store.ROOT / "leads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(lead_id: str) -> Path:
    if not lead_id or "/" in lead_id or ".." in lead_id:
        raise ValueError("Unknown lead.")
    return leads_dir() / f"{lead_id}.json"


def _want(raw: dict | None) -> dict:
    src = raw or {}
    keywords = src.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [part.strip() for part in re.split(r"[,/;]+", keywords) if part.strip()]
    year_min = _int(src.get("yearMin"))
    year_max = _int(src.get("yearMax"))
    if year_min and year_max and year_min > year_max:
        year_min, year_max = year_max, year_min
    return {
        "category": str(src.get("category") or "").strip(),
        "make": str(src.get("make") or "").strip(),
        "model": str(src.get("model") or "").strip(),
        "yearMin": year_min,
        "yearMax": year_max,
        "hoursMax": _int(src.get("hoursMax")),
        "budgetMax": _int(src.get("budgetMax")),
        "keywords": [str(word).strip() for word in keywords if str(word).strip()][:12],
    }


def _int(value) -> int | None:
    if value in (None, ""):
        return None
    digits = re.sub(r"[^\d]", "", str(value))
    if not digits:
        return None
    return int(digits)


def _clean(payload: dict) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("A buyer lead needs a name.")
    status = str(payload.get("status") or "active").strip().lower()
    if status not in ("active", "won", "dead"):
        status = "active"
    phone = str(payload.get("phone") or "").strip()
    email = str(payload.get("email") or "").strip()
    if not phone and not email:
        raise ValueError("A buyer lead needs a phone or an email.")
    return {
        "name": name,
        "company": str(payload.get("company") or "").strip(),
        "phone": phone,
        "email": email,
        "source": str(payload.get("source") or "manual").strip() or "manual",
        "status": status,
        "want": _want(payload.get("want") if isinstance(payload.get("want"), dict) else payload),
        "notes": str(payload.get("notes") or "").strip(),
        "externalId": str(payload.get("externalId") or "").strip(),
    }


def iter_leads():
    for path in sorted(leads_dir().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        yield json.loads(path.read_text(encoding="utf-8"))


def summarize_lead(lead: dict) -> dict:
    want = lead.get("want") or {}
    return {
        "id": lead["id"],
        "name": lead.get("name") or "",
        "company": lead.get("company") or "",
        "phone": lead.get("phone") or "",
        "email": lead.get("email") or "",
        "source": lead.get("source") or "",
        "status": lead.get("status") or "active",
        "category": want.get("category") or "",
        "make": want.get("make") or "",
        "model": want.get("model") or "",
        "budgetMax": want.get("budgetMax"),
        "hoursMax": want.get("hoursMax"),
        "createdAt": lead.get("createdAt"),
        "packets": len(lead.get("packets") or []),
    }


def list_leads() -> list[dict]:
    return [summarize_lead(lead) for lead in iter_leads()]


def get_lead(lead_id: str) -> dict:
    path = _path(lead_id)
    if not path.exists():
        raise ValueError("That lead is not in the desk.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_lead(lead: dict) -> dict:
    _path(lead["id"]).write_text(json.dumps(lead, indent=2), encoding="utf-8")
    return lead


def find_by_external(external_id: str) -> dict | None:
    if not external_id:
        return None
    for lead in iter_leads():
        if lead.get("externalId") == external_id:
            return lead
    return None


def upsert_lead(payload: dict) -> dict:
    body = _clean(payload)
    existing = None
    lead_id = str(payload.get("id") or "").strip()
    if lead_id:
        try:
            existing = get_lead(lead_id)
        except ValueError:
            existing = None
    if existing is None and body["externalId"]:
        existing = find_by_external(body["externalId"])
    if existing:
        existing.update(body)
        existing["updatedAt"] = _now()
        return save_lead(existing)
    lead = {
        "id": uuid.uuid4().hex[:12],
        "createdAt": _now(),
        "updatedAt": _now(),
        "packets": [],
        **body,
    }
    return save_lead(lead)


def attach_packet(lead_id: str, packet: dict) -> dict:
    lead = get_lead(lead_id)
    packets = list(lead.get("packets") or [])
    packets.append(packet)
    lead["packets"] = packets[-50:]
    lead["updatedAt"] = _now()
    return save_lead(lead)
