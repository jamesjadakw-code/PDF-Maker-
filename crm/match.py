"""Rank machines against buyer wants. One pass, no extra page loads."""

from __future__ import annotations

import re

from crm.marketplace import display_price, machine_fields

_MAKE_ALIASES = {
    "cat": "caterpillar",
    "caterpillar": "caterpillar",
    "jd": "john deere",
    "deere": "john deere",
    "john deere": "john deere",
    "dw": "ditch witch",
    "ditchwitch": "ditch witch",
    "ditch witch": "ditch witch",
}

_CATEGORY_ALIASES = {
    "hdd": "directional drills",
    "horizontal directional drill": "directional drills",
    "directional drill": "directional drills",
    "directional drills": "directional drills",
    "excavator": "excavators",
    "excavators": "excavators",
    "trackhoe": "excavators",
    "trencher": "trenchers & rock saws",
    "trenchers": "trenchers & rock saws",
    "trenchers & rock saws": "trenchers & rock saws",
    "rock saw": "trenchers & rock saws",
    "skid steer": "skid steers & ctls",
    "skid steers & ctls": "skid steers & ctls",
    "ctl": "skid steers & ctls",
    "dozer": "dozers",
    "dozers": "dozers",
    "backhoe": "backhoes",
    "backhoes": "backhoes",
    "wheel loader": "wheel loaders",
    "wheel loaders": "wheel loaders",
    "drill": "drills",
    "drills": "drills",
}


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _make(value: str) -> str:
    text = _norm(value)
    return _MAKE_ALIASES.get(text, text)


def _category(value: str) -> str:
    text = _norm(value)
    if text in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[text]
    for key, name in _CATEGORY_ALIASES.items():
        if key and key in text:
            return name
    return text


def _tokens(value: str) -> set[str]:
    return {part for part in _norm(value).split() if len(part) >= 2}


def _dollars(value) -> int | None:
    digits = re.sub(r"[^\d]", "", str(value or ""))
    return int(digits) if digits else None


def _year(value) -> int | None:
    match = re.search(r"(?:19|20)\d{2}", str(value or ""))
    return int(match.group(0)) if match else None


def _hours(value) -> int | None:
    digits = re.sub(r"[^\d]", "", str(value or ""))
    return int(digits) if digits else None


def score_pair(draft: dict, lead: dict) -> dict:
    """Score one unit against one buyer. 100 is a locked-in match."""
    listing = draft.get("listing") or {}
    fields = machine_fields(listing)
    want = lead.get("want") or {}
    hay = " ".join([
        fields.get("title") or "",
        fields.get("make") or "",
        fields.get("model") or "",
        fields.get("category") or "",
        listing.get("description") or "",
    ])
    hay_norm = _norm(hay)
    score = 0
    reasons: list[str] = []

    want_cat = _category(str(want.get("category") or ""))
    unit_cat = _category(fields.get("category") or "")
    if want_cat and unit_cat:
        if want_cat == unit_cat:
            score += 28
            reasons.append("category")
        elif want_cat in unit_cat or unit_cat in want_cat:
            score += 14
            reasons.append("category-close")

    want_make = _make(str(want.get("make") or ""))
    unit_make = _make(fields.get("make") or "")
    if want_make and unit_make and want_make == unit_make:
        score += 18
        reasons.append("make")
    elif want_make and want_make in hay_norm:
        score += 10
        reasons.append("make-in-title")

    want_model = _norm(str(want.get("model") or ""))
    unit_model = _norm(fields.get("model") or "")
    if want_model:
        if want_model == unit_model or want_model in unit_model or want_model in hay_norm:
            score += 22
            reasons.append("model")
        else:
            overlap = _tokens(want_model) & _tokens(unit_model + " " + (fields.get("title") or ""))
            if overlap:
                score += 12
                reasons.append("model-token")

    unit_year = _year(fields.get("year"))
    year_min = want.get("yearMin")
    year_max = want.get("yearMax")
    if unit_year and (year_min or year_max):
        low = year_min or 0
        high = year_max or 9999
        if low <= unit_year <= high:
            score += 10
            reasons.append("year")
        elif low - 2 <= unit_year <= high + 2:
            score += 4
            reasons.append("year-close")

    unit_hours = _hours(fields.get("hours"))
    hours_max = want.get("hoursMax")
    if unit_hours is not None and hours_max:
        if unit_hours <= hours_max:
            score += 8
            reasons.append("hours")
        elif unit_hours <= int(hours_max * 1.15):
            score += 3
            reasons.append("hours-stretch")

    price = _dollars(display_price(listing))
    budget = want.get("budgetMax")
    if price and budget:
        if price <= budget:
            score += 10
            reasons.append("budget")
        elif price <= int(budget * 1.08):
            score += 6
            reasons.append("budget-stretch")

    hits = 0
    for word in want.get("keywords") or []:
        token = _norm(str(word))
        if token and token in hay_norm:
            hits += 1
    if hits:
        score += min(4, hits)
        reasons.append("keywords")

    score = max(0, min(100, score))
    if score >= 70:
        tier = "hot"
    elif score >= 45:
        tier = "warm"
    else:
        tier = "cold"
    packeted = False
    packet_pdf = ""
    for packed in lead.get("packets") or []:
        if packed.get("listingId") == draft.get("id"):
            packeted = True
            packet_pdf = packed.get("pdf") or ""
            break
    return {
        "leadId": lead.get("id") or "",
        "listingId": draft.get("id") or "",
        "score": score,
        "tier": tier,
        "reasons": reasons,
        "leadName": lead.get("name") or "",
        "company": lead.get("company") or "",
        "phone": lead.get("phone") or "",
        "email": lead.get("email") or "",
        "unitTitle": listing.get("title") or fields.get("title") or "",
        "price": display_price(listing),
        "category": fields.get("category") or "",
        "make": fields.get("make") or "",
        "model": fields.get("model") or "",
        "brochurePdf": (draft.get("machineCard") or {}).get("pdf") or "",
        "unitStatus": draft.get("status") or "",
        "leadStatus": lead.get("status") or "",
        "packeted": packeted,
        "packetPdf": packet_pdf,
    }


def _pool_for_lead(lead: dict, drafts: list[dict], by_cat: dict[str, list[dict]]) -> list[dict]:
    want_cat = _category(str((lead.get("want") or {}).get("category") or ""))
    if want_cat and want_cat in by_cat:
        return by_cat[want_cat]
    return drafts


def rank_all(drafts: list[dict], leads: list[dict], min_score: int = 45, limit: int = 40) -> list[dict]:
    """Top matches for the desk. Category index avoids a full 1,000 × 3,000 scan."""
    live_leads = [lead for lead in leads if (lead.get("status") or "active") == "active"]
    live_drafts = [draft for draft in drafts if draft.get("status") != "dead"]
    by_cat: dict[str, list[dict]] = {}
    for draft in live_drafts:
        cat = _category(machine_fields(draft.get("listing") or {}).get("category") or "")
        if cat:
            by_cat.setdefault(cat, []).append(draft)
    ranked: list[dict] = []
    for lead in live_leads:
        want = lead.get("want") or {}
        if not any(want.get(key) for key in ("category", "make", "model", "keywords", "budgetMax")):
            continue
        for draft in _pool_for_lead(lead, live_drafts, by_cat):
            row = score_pair(draft, lead)
            if row["score"] >= min_score:
                ranked.append(row)
    ranked.sort(key=lambda row: (-row["score"], row["unitTitle"]))
    return ranked[:limit]


def rank_buyers(draft: dict, leads: list[dict], limit: int = 12) -> list[dict]:
    rows = [
        score_pair(draft, lead)
        for lead in leads
        if (lead.get("status") or "active") == "active"
    ]
    rows.sort(key=lambda row: -row["score"])
    return [row for row in rows if row["score"] >= 30][:limit]


def rank_machines(lead: dict, drafts: list[dict], limit: int = 12) -> list[dict]:
    rows = [score_pair(draft, lead) for draft in drafts if draft.get("status") != "dead"]
    rows.sort(key=lambda row: -row["score"])
    return [row for row in rows if row["score"] >= 30][:limit]
