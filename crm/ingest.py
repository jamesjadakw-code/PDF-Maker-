"""Normalize inbound buyer payloads from Facebook lead ads and direct CRM posts."""

from __future__ import annotations

import re

_FIELD_MAP = {
    "full_name": "name",
    "name": "name",
    "first_name": "first_name",
    "last_name": "last_name",
    "phone_number": "phone",
    "phone": "phone",
    "work_phone_number": "phone",
    "email": "email",
    "company_name": "company",
    "company": "company",
    "what_machine": "model",
    "machine": "model",
    "model": "model",
    "make": "make",
    "brand": "make",
    "category": "category",
    "equipment_type": "category",
    "budget": "budgetMax",
    "budget_max": "budgetMax",
    "max_budget": "budgetMax",
    "hours": "hoursMax",
    "max_hours": "hoursMax",
    "hours_max": "hoursMax",
    "year_min": "yearMin",
    "min_year": "yearMin",
    "year_max": "yearMax",
    "max_year": "yearMax",
    "notes": "notes",
    "city": "notes",
    "leadgen_id": "externalId",
    "id": "externalId",
}


def _first(values) -> str:
    if isinstance(values, list):
        return str(values[0]).strip() if values else ""
    return str(values or "").strip()


def _field_data(payload: dict) -> dict:
    out: dict[str, str] = {}
    for item in payload.get("field_data") or []:
        raw_name = str(item.get("name") or "").strip().lower()
        key = _FIELD_MAP.get(raw_name, raw_name)
        out[key] = _first(item.get("values"))
    return out


def _page_lead(payload: dict) -> dict:
    """Facebook page webhook: flatten the first leadgen change plus any field_data."""
    fields = _field_data(payload)
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            if value.get("leadgen_id") and not fields.get("externalId"):
                fields["externalId"] = str(value.get("leadgen_id"))
            nested = _field_data(value)
            for key, item in nested.items():
                fields.setdefault(key, item)
    return fields


def lead_from_payload(payload: dict) -> dict:
    """Turn a webhook body into upsert_lead() input. Rejects ping-only Facebook shells."""
    if not isinstance(payload, dict):
        raise ValueError("Send a JSON object.")
    if "field_data" in payload or payload.get("object") == "page":
        fields = _page_lead(payload) if payload.get("object") == "page" else _field_data(payload)
        if payload.get("leadgen_id") and not fields.get("externalId"):
            fields["externalId"] = str(payload.get("leadgen_id"))
    else:
        fields = {
            mapped: payload[key]
            for key, mapped in (
                ("name", "name"),
                ("phone", "phone"),
                ("email", "email"),
                ("company", "company"),
                ("source", "source"),
                ("notes", "notes"),
                ("externalId", "externalId"),
            )
            if payload.get(key)
        }
        want = payload.get("want") if isinstance(payload.get("want"), dict) else payload
        for key in ("category", "make", "model", "yearMin", "yearMax", "hoursMax", "budgetMax", "keywords"):
            if want.get(key) not in (None, ""):
                fields[key] = want.get(key)
        if payload.get("source"):
            fields["source"] = payload["source"]

    if fields.get("first_name") or fields.get("last_name"):
        fields["name"] = " ".join(
            part for part in (fields.get("first_name"), fields.get("name"), fields.get("last_name")) if part
        ).strip() or fields.get("name") or ""

    name = str(fields.get("name") or "").strip()
    phone = str(fields.get("phone") or "").strip()
    email = str(fields.get("email") or "").strip()
    model = str(fields.get("model") or "").strip()
    if not name and (phone or email):
        name = phone or email
    if not name:
        raise ValueError("Inbound lead is missing a buyer name.")
    if not phone and not email:
        raise ValueError("Inbound lead is missing a phone or email.")
    if payload.get("object") == "page" and not payload.get("field_data") and not model and not fields.get("category"):
        if not (fields.get("phone") or fields.get("email")):
            raise ValueError(
                "Facebook ping-only payloads have no buyer fields. POST field_data "
                "(name, phone, machine, budget) to /api/ingest/leads."
            )

    source = str(fields.get("source") or payload.get("source") or "").strip()
    if not source:
        source = "facebook" if ("field_data" in payload or payload.get("object") == "page") else "webhook"

    want = {
        "category": str(fields.get("category") or "").strip(),
        "make": str(fields.get("make") or "").strip(),
        "model": model,
        "yearMin": fields.get("yearMin"),
        "yearMax": fields.get("yearMax"),
        "hoursMax": fields.get("hoursMax"),
        "budgetMax": _money(fields.get("budgetMax")),
        "keywords": fields.get("keywords") or [],
    }
    if model and not want["keywords"]:
        want["keywords"] = [part for part in re.split(r"\s+", model) if len(part) >= 3][:6]

    return {
        "name": name,
        "company": str(fields.get("company") or "").strip(),
        "phone": phone,
        "email": email,
        "source": source,
        "status": "active",
        "want": want,
        "notes": str(fields.get("notes") or "").strip(),
        "externalId": str(fields.get("externalId") or "").strip(),
    }


def _money(value) -> str:
    if value in (None, ""):
        return ""
    digits = re.sub(r"[^\d]", "", str(value))
    return digits
