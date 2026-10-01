"""Pull photos and listing facts from one Facebook Marketplace item URL.

Only facebook.com marketplace links are fetched. The listing stays a draft
until a person verifies it; nothing here publishes to the website.
"""

from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urlparse

ALLOWED_HOSTS = {
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "mbasic.facebook.com",
    "web.facebook.com",
}

_STRING = r'"((?:\\.|[^"\\])*)"'
_TITLE_RES = [
    re.compile(r'"marketplace_listing_title"\s*:\s*' + _STRING),
    re.compile(r'"custom_title"\s*:\s*' + _STRING),
    re.compile(r'"listing_title"\s*:\s*' + _STRING),
]
_DESC_RES = [
    re.compile(r'"redacted_description"\s*:\s*\{\s*"text"\s*:\s*' + _STRING),
    re.compile(r'"listing_description"\s*:\s*' + _STRING),
]
_PRICE_RES = [
    re.compile(r'"formatted_amount"\s*:\s*' + _STRING),
    re.compile(r'"listing_price"\s*:\s*\{[^}]{0,240}"amount"\s*:\s*"([\d.,]+)"'),
]
_LOC_RES = [
    re.compile(r'"location_text"\s*:\s*\{\s*"text"\s*:\s*' + _STRING),
    re.compile(r'"location_name"\s*:\s*' + _STRING),
]
_META_RES = {
    "title": re.compile(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', re.I),
    "title_alt": re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', re.I),
    "description": re.compile(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)', re.I),
    "description_alt": re.compile(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']', re.I),
    "image": re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I),
}
_URI_RE = re.compile(r'https:(?:\\?/\\?/|//)[^"\'\\\s<>]+', re.I)
_HOURS_RE = re.compile(r'(\d[\d,]*)\s*(?:hours|hrs)\b', re.I)
_YEAR_RE = re.compile(r'\b(19|20)\d{2}\b')
_MONEY_RE = re.compile(r'\$\s?(\d[\d,]*(?:\.\d{2})?)')


def marketplace_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise ValueError("Paste a Facebook Marketplace item URL.")
    if not re.match(r"https?://", raw, re.I):
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS or parsed.scheme not in ("http", "https"):
        raise ValueError("Only a facebook.com/marketplace item link can be imported.")
    if "/marketplace/" not in parsed.path:
        raise ValueError("That Facebook link is not a Marketplace listing.")
    return parsed._replace(fragment="").geturl()


def item_id(url: str) -> str:
    match = re.search(r"/marketplace/item/(\d+)", url)
    return match.group(1) if match else ""


def _decode(value: str) -> str:
    try:
        return json.loads(f'"{value}"')
    except json.JSONDecodeError:
        return unescape(value.encode("utf-8", "ignore").decode("unicode_escape", "ignore"))


def _first(patterns, text: str) -> str:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return _decode(match.group(1)).strip()
    return ""


def _meta(html: str, key: str) -> str:
    match = _META_RES[key].search(html) or _META_RES.get(key + "_alt", re.compile("$^")).search(html)
    return unescape(match.group(1)).strip() if match else ""


def clean_title(title: str) -> str:
    title = re.sub(r"\s*[|–-]\s*Facebook Marketplace.*$", "", title or "", flags=re.I)
    title = re.sub(r"\s*[|–-]\s*Facebook$", "", title, flags=re.I)
    return re.sub(r"\s+", " ", title).strip()


_BRANDS = (
    "Ditch Witch",
    "John Deere",
    "Caterpillar",
    "CAT",
    "Vermeer",
    "Bobcat",
    "Komatsu",
    "Case",
    "Kubota",
    "Takeuchi",
    "Yanmar",
    "Hitachi",
    "Volvo",
    "Liebherr",
    "JCB",
    "Hyundai",
    "Doosan",
    "Develon",
    "Terex",
    "Wacker Neuson",
    "International",
    "Freightliner",
)
_CATEGORIES = (
    (("directional", "horizontal drill"), "Directional Drills"),
    (("trencher", "rock saw"), "Trenchers & Rock Saws"),
    (("excavator",), "Excavators"),
    (("backhoe",), "Backhoes"),
    (("dozer", "bulldozer"), "Dozers"),
    (("skid steer", "ctl"), "Skid Steers & CTLs"),
    (("wheel loader",), "Wheel Loaders"),
    (("drill",), "Drills"),
)


def machine_fields(listing: dict) -> dict:
    """Split a Marketplace title into the CRM unit fields. Status stays Draft."""
    title = clean_title(listing.get("title") or "")
    year = str(listing.get("year") or "")
    rest = title
    if year and rest.startswith(year):
        rest = rest[len(year):].strip()
    make = ""
    model = rest
    lowered = rest.lower()
    for brand in _BRANDS:
        if lowered.startswith(brand.lower()):
            make = brand
            model = rest[len(brand):].strip(" -–")
            break
    model = re.split(
        r"\s+(?:horizontal|directional|drill|trencher|excavator|with)\b",
        model,
        maxsplit=1,
        flags=re.I,
    )[0].strip()
    blob = title.lower()
    category = "Other Equipment"
    for keys, name in _CATEGORIES:
        if any(key in blob for key in keys):
            category = name
            break
    digits = re.sub(r"[^\d]", "", listing.get("price") or "")
    return {
        "title": title,
        "year": year,
        "make": make,
        "model": model or title,
        "category": category,
        "hours": str(listing.get("hours") or ""),
        "price": digits,
        "location": listing.get("location") or "",
        "description": listing.get("description") or "",
    }


def edited_price(brochure: dict | None) -> str:
    """Dollar amount typed onto the brochure after verification. Blank until then."""
    if not brochure:
        return ""
    chunks = [brochure.get("priceLine") or ""]
    for row in brochure.get("specs") or []:
        if str(row).lower().startswith("price"):
            chunks.append(str(row))
    text = " ".join(chunks)
    match = _MONEY_RE.search(text)
    if not match:
        bare = re.search(r"(?:price:?\s*)(\d[\d,]{3,})", text, re.I)
        if not bare:
            return ""
        amount = bare.group(1)
    else:
        amount = match.group(1)
    try:
        return f"${float(amount.replace(',', '')):,.0f}"
    except ValueError:
        return ""


def crm_draft_fields(listing: dict, brochure: dict | None = None) -> dict:
    """Fields written onto the original CRM draft.

    Location, the Marketplace URL, and the source stay off. Price is whatever
    was edited onto the brochure after verification, or blank.
    """
    fields = machine_fields(listing)
    fields["location"] = ""
    fields["sourceUrl"] = ""
    fields["source"] = ""
    fields["price"] = re.sub(r"[^\d]", "", edited_price(brochure))
    return fields


def money(value: str) -> str:
    if not value:
        return ""
    match = _MONEY_RE.search(value)
    raw = match.group(1) if match else value
    try:
        amount = float(raw.replace(",", "").replace("$", ""))
    except ValueError:
        return ""
    if amount < 1:
        return ""
    return f"${amount:,.0f}"


def _keep_image(url: str) -> bool:
    lowered = url.lower()
    if "fbcdn.net" not in lowered and "facebook.com" not in lowered:
        return False
    blocked = ("emoji", "/rsrc.php", "safe_image", "fb_icon", "/images/emoji", "static.xx.fbcdn.net/rsrc")
    return not any(part in lowered for part in blocked)


def image_urls(html: str, limit: int = 40) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    og = _meta(html, "image")
    normalized = html.replace("\\/", "/").replace("\\u0026", "&").replace("&amp;", "&")
    candidates = ([og] if og else []) + _URI_RE.findall(normalized)
    for candidate in candidates:
        url = candidate.replace("\\/", "/").replace("\\u0026", "&").replace("&amp;", "&")
        url = url.rstrip("\\")
        if not url.startswith("http") or not _keep_image(url):
            continue
        key = url.split("?")[0]
        if key in seen:
            continue
        seen.add(key)
        found.append(url)
        if len(found) >= limit:
            break
    return found


def parse_listing(html: str, url: str) -> dict:
    """Read every photo URL and the listing facts out of Marketplace HTML."""
    title = clean_title(_first(_TITLE_RES, html) or _meta(html, "title"))
    description = _first(_DESC_RES, html) or _meta(html, "description")
    description = unescape(description).replace("\\n", "\n").strip()
    price = money(_first(_PRICE_RES, html) or description or _meta(html, "description"))
    location = _first(_LOC_RES, html)
    if not location:
        parts = re.split(r"\s+[·•]\s+", _meta(html, "description"))
        if len(parts) > 1:
            location = parts[-1].strip()
    blob = " ".join([title, description, _meta(html, "description")])
    hours_match = _HOURS_RE.search(blob)
    hours = hours_match.group(1).replace(",", "") if hours_match else ""
    year_match = _YEAR_RE.search(title) or _YEAR_RE.search(description)
    year = year_match.group(0) if year_match else ""
    condition = ""
    for word in ("like new", "used", "new", "salvage", "for parts"):
        if re.search(rf"\b{word}\b", blob, re.I):
            condition = word.upper() if word != "like new" else "LIKE NEW"
            break
    photos = image_urls(html)
    listing = {
        "sourceUrl": url,
        "itemId": item_id(url),
        "title": title,
        "price": price,
        "location": location,
        "description": description,
        "hours": hours,
        "year": year,
        "condition": condition or "USED",
        "photos": photos,
    }
    if _login_wall(html, listing):
        raise ValueError(
            "Facebook did not return this listing (login wall). Open the item, save the page, and paste its HTML."
        )
    if not title and not photos:
        raise ValueError("No listing title or photos were found on that page.")
    return listing


def _login_wall(html: str, listing: dict) -> bool:
    if listing["photos"] or listing["price"]:
        return False
    title = (listing["title"] or "").lower()
    if title and "log in" not in title and "login" not in title and title != "facebook":
        return False
    lowered = html.lower()
    return "log in" in lowered or "login" in lowered or "you must log in" in lowered


def to_brochure(listing: dict, pending: bool = True) -> dict:
    """Map a scraped listing onto the two-page BAM brochure fields.

    The original draft leaves off location, the listing URL, and the source.
    Price stays blank until someone edits it after verification.
    """
    title = listing.get("title") or "Equipment unit"
    hours = listing.get("hours") or ""
    if hours.isdigit():
        hours = f"{int(hours):,}"
    condition = listing.get("condition") or "USED"
    raw_description = listing.get("description") or title
    highlights = _sentences(raw_description)[:7] or [title]
    included = _feature_lines(raw_description)[:6] or [title]
    description = re.sub(r"\s*\n\s*", " ", raw_description).strip()
    gate = "Pending verification — not on the website" if pending else "Verified — edit the price"
    status_bits = [condition, f"{hours} Hours" if hours else "", gate]
    specs = [
        ("Year", listing.get("year") or "—"),
        ("Title", title),
        ("Hours", f"{hours}" if hours else "—"),
        ("Condition", condition),
        ("Price", ""),
        ("Photos", str(len(listing.get("photos") or []))),
        ("Status", "Pending verification" if pending else "Verified"),
        ("Website", "Held until verified" if pending else "Ready to post"),
        ("Phone", "+1-904-767-5232"),
        ("Email", "sales@bigassmotors.com"),
        ("Stock", "—"),
        ("Make / model", title),
        ("Currency", "USD"),
        ("Seller contact", "sales@bigassmotors.com"),
        ("Freight", "US & MX — quote on request"),
        ("Inspection", "Buyer verifies before deposit"),
        ("As-is", "Sold as-is"),
        ("Brochure", "BAM letter"),
        ("Queue", "CRM verification"),
        ("Mobile", "+1-904-729-1051"),
        ("Web", "www.bigassmotors.com"),
    ]
    while len(specs) < 26:
        specs.append(("", ""))
    return {
        "title": title,
        "subtitle": "Review before it goes on the website",
        "status": "  |  ".join(bit for bit in status_bits if bit),
        "description": description,
        "highlights": highlights,
        "included": included,
        "priceLine": "PRICE: ",
        "page2Title": title,
        "specHead": "TECHNICAL SPECIFICATIONS",
        "specs": [f"{label} | {value}" for label, value in specs[:26]],
        "condition": (
            f"{gate}. Edit the price after verification. "
            "Confirm hours, serial, and that every photo is this unit before posting. "
            "Trailer and support equipment are not included unless the listing says so."
        ),
        "ready": "HELD FOR REVIEW" if pending else "READY TO MOVE",
        "lock": "Verify this listing, then edit the price." if pending else "Edit the price, then file the draft.",
        "phone": "+1-904-767-5232",
        "web": "sales@bigassmotors.com  •  www.bigassmotors.com",
        "photos": list(listing.get("photos") or []),
    }


def _sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [chunk.strip(" -•*") for chunk in chunks if len(chunk.strip()) > 2]


def _feature_lines(text: str) -> list[str]:
    lines = []
    for line in text.splitlines():
        cleaned = line.strip().lstrip("-•*").strip()
        if cleaned and (line.strip()[:1] in "-•*" or line.strip().lower().startswith("includes")):
            lines.append(cleaned)
    return lines or _sentences(text)
