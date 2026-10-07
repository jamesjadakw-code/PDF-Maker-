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


_STAGED_SOURCES = {"staged", "internal", "original", "bam"}
_SCRAPE_SOURCES = {
    "facebook",
    "marketplace",
    "scrape",
    "third-party",
    "third_party",
    "machinio",
    "craigslist",
    "equipmenttrader",
}


def is_third_party_scrape(item: dict) -> bool:
    """True only for Marketplace / Machinio / other pulls. Staged BAM stock is out."""
    listing = item.get("listing") if isinstance(item.get("listing"), dict) else item
    if item.get("is_staged") is True or listing.get("is_staged") is True:
        return False
    source = str(item.get("source_type") or listing.get("source_type") or "").strip().lower()
    if source in _STAGED_SOURCES:
        return False
    if source in _SCRAPE_SOURCES:
        return True
    url = str(listing.get("sourceUrl") or "").lower()
    if "facebook.com" in url or "machinio.com" in url:
        return True
    return bool(listing.get("itemId"))


def _as_draft(item: dict) -> dict:
    if isinstance(item.get("listing"), dict):
        return item
    listing = dict(item)
    if not listing.get("title"):
        listing["title"] = " ".join(
            part for part in (listing.get("make"), listing.get("model")) if part
        ).strip()
    return {
        "id": item.get("id") or "",
        "status": item.get("status") or "pending_verification",
        "listing": listing,
        "machineCard": item.get("machineCard") or {},
    }


def _map_keys(*values) -> set[str]:
    keys: set[str] = set()
    for raw in values:
        if raw in (None, ""):
            continue
        text = str(raw).strip()
        if not text:
            continue
        keys.add(_norm(text))
        cat = _category(text)
        if cat:
            keys.add(cat)
    keys.discard("")
    return keys


def lead_map_keys(lead: dict) -> set[str]:
    want = lead.get("want") if isinstance(lead.get("want"), dict) else {}
    return _map_keys(
        lead.get("target_machinery_category"),
        want.get("category"),
        want.get("model"),
        " ".join(part for part in (want.get("make"), want.get("model")) if part),
    )


def listing_map_keys(item: dict) -> set[str]:
    listing = item.get("listing") if isinstance(item.get("listing"), dict) else item
    fields = machine_fields(listing)
    return _map_keys(
        listing.get("model_category"),
        item.get("model_category"),
        fields.get("category"),
        fields.get("model"),
        " ".join(part for part in (fields.get("make"), fields.get("model")) if part),
    )


def process_marketplace_scrape_matches(listings: list[dict], leads: list[dict]) -> list[dict]:
    """Lag-free matcher: category map lookup. Ignores staged inventory."""
    leads_by_category: dict[str, list[dict]] = {}
    for lead in leads:
        if (lead.get("status") or "active") != "active":
            continue
        for key in lead_map_keys(lead):
            leads_by_category.setdefault(key, []).append(lead)

    active: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in listings:
        if not is_third_party_scrape(item):
            continue
        draft = _as_draft(item)
        listing = draft.get("listing") or {}
        fields = machine_fields(listing)
        bucket: list[dict] = []
        found: set[str] = set()
        for key in listing_map_keys(draft):
            for lead in leads_by_category.get(key) or []:
                lead_id = str(lead.get("id") or "")
                if lead_id in found:
                    continue
                found.add(lead_id)
                bucket.append(lead)
        for lead in bucket:
            pair = (str(lead.get("id") or ""), str(draft.get("id") or listing.get("id") or ""))
            if pair in seen:
                continue
            seen.add(pair)
            row = score_pair(draft, lead)
            row["buyerName"] = lead.get("name") or ""
            row["buyerContact"] = lead.get("phone") or lead.get("email") or ""
            row["equipment"] = " ".join(
                part for part in (fields.get("make"), fields.get("model")) if part
            ).strip()
            row["source"] = (
                listing.get("source_platform")
                or listing.get("source_type")
                or "Third-Party Scrape"
            )
            active.append(row)
    return active


def rank_all(drafts: list[dict], leads: list[dict], min_score: int = 45, limit: int = 40) -> list[dict]:
    """Top matches for the desk. Category map; staged units never enter the loop."""
    ranked = [
        row for row in process_marketplace_scrape_matches(drafts, leads)
        if row["score"] >= min_score
    ]
    ranked.sort(key=lambda row: (-row["score"], row["unitTitle"]))
    return ranked[:limit]


def rank_buyers(draft: dict, leads: list[dict], limit: int = 12) -> list[dict]:
    if not is_third_party_scrape(draft):
        return []
    rows = process_marketplace_scrape_matches([draft], leads)
    rows.sort(key=lambda row: -row["score"])
    return [row for row in rows if row["score"] >= 30][:limit]


def rank_machines(lead: dict, drafts: list[dict], limit: int = 12) -> list[dict]:
    rows = process_marketplace_scrape_matches(drafts, [lead])
    rows.sort(key=lambda row: -row["score"])
    return [row for row in rows if row["score"] >= 30][:limit]
