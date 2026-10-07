"""Identify a unit by make, model, year, and attachments, then name its OEM fields.

A 2012 Ditch Witch RT-115 is a trencher. It gets trench depth (and saw depth
when a rocksaw is on the listing), not HDD pullback.
"""

from __future__ import annotations

import re

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
    (("directional", "horizontal drill"), "Directional Drills", "hdd"),
    (("trencher", "rock saw", "rocksaw"), "Trenchers & Rock Saws", "trencher"),
    (("excavator",), "Excavators", "excavator"),
    (("backhoe",), "Backhoes", "backhoe"),
    (("dozer", "bulldozer"), "Dozers", "dozer"),
    (("skid steer", "ctl"), "Skid Steers & CTLs", "skid"),
    (("wheel loader",), "Wheel Loaders", "loader"),
    (("plow",), "Vibratory Plows", "plow"),
    (("drill",), "Drills", "drill"),
)

# Model-code families win over title keywords. Compact model is letters+digits only.
_MODEL_FAMILIES = (
    (("ditch witch",), r"^jt\d", "hdd", "Directional Drills"),
    (("ditch witch",), r"^rt\d", "trencher", "Trenchers & Rock Saws"),
    (("ditch witch",), r"^ht\d", "trencher", "Trenchers & Rock Saws"),
    (("ditch witch",), r"^mt\d", "trencher", "Trenchers & Rock Saws"),
    (("ditch witch",), r"^c\d", "trencher", "Trenchers & Rock Saws"),
    (("ditch witch",), r"^fx\d|^f2", "plow", "Vibratory Plows"),
    (("vermeer",), r"^d\d+x\d", "hdd", "Directional Drills"),
    (("vermeer",), r"^rtx\d", "trencher", "Trenchers & Rock Saws"),
    (("vermeer",), r"^ctx\d", "trencher", "Trenchers & Rock Saws"),
    (("vermeer",), r"^t[4-9]\d", "trencher", "Trenchers & Rock Saws"),
)

_FAMILY_CATEGORY = {
    "hdd": "Directional Drills",
    "trencher": "Trenchers & Rock Saws",
    "excavator": "Excavators",
    "backhoe": "Backhoes",
    "dozer": "Dozers",
    "skid": "Skid Steers & CTLs",
    "loader": "Wheel Loaders",
    "plow": "Vibratory Plows",
    "drill": "Drills",
}

_CATEGORY_FAMILY = {name.lower(): family for _keys, name, family in _CATEGORIES}

_ATTACHMENT_PATTERNS = (
    ("rocksaw", r"\b(?:rock\s*-?\s*saw|rocksaw|saw\s+attachment|concrete\s+saw|hydrawheel|h[56]\d{2})\b"),
    ("plow", r"\b(?:vibratory\s+)?plow\b"),
    ("reel", r"\b(?:(?:fiber|cable|conduit)\s+)?reel(?:\s+carrier)?\b"),
    ("backhoe", r"\bbackhoe(?:\s+attachment|\s+boom|\s+assembly)?\b"),
    ("bore", r"\b(?:boring\s+attachment|bore\s+attachment)\b"),
    ("thumb", r"\b(?:hydraulic\s+)?thumb\b"),
    ("bucket", r"\b(?:4[\s-]*in[\s-]*1|four[\s-]*in[\s-]*one).*(?:bucket)?|\b(?:loader\s+)?bucket\b"),
    ("pipe_loader", r"\bpipe\s+loader\b"),
    ("multiprocessor", r"\b(?:multi[\s-]*processor|mp15|demolition\s+shear)\b"),
)

# families=None → every machine. attachments=() → only when that kit is on the unit.
SPEC_FIELDS = (
    ("pullback_force", "Pullback force", ("pullback",), ("pullback_force", "pullback"), ("hdd",), ()),
    ("thrust_force", "Thrust force", ("thrust",), ("thrust_force", "thrust"), ("hdd",), ()),
    ("max_spindle_torque", "Spindle torque, max", ("spindle torque", "max torque"), ("max_spindle_torque", "spindle_torque"), ("hdd",), ()),
    ("trench_depth", "Trench depth", ("trench depth", "maximum trench", "max trench"), ("trench_depth", "trench depth"), ("trencher",), ()),
    ("trench_width", "Trench width", ("trench width",), ("trench_width", "trench width"), ("trencher",), ()),
    ("saw_depth", "Saw depth", ("saw depth", "rock saw depth", "cutting depth", "sawing depth"), ("saw_depth", "saw depth"), ("trencher",), ("rocksaw",)),
    ("plow_depth", "Plow depth", ("plow depth",), ("plow_depth", "plow depth"), ("plow", "trencher"), ("plow",)),
    ("digging_depth", "Digging depth", ("digging depth", "max dig depth"), ("digging_depth", "dig depth"), ("excavator", "backhoe"), ()),
    ("bucket_capacity", "Bucket capacity", ("bucket capacity", "heaped capacity"), ("bucket_capacity", "bucket"), ("excavator", "backhoe", "loader"), ()),
    ("engine_power", "Power", ("horsepower", "engine power", "gross power", "rated power", "power"), ("engine_power", "power"), None, ()),
    ("operating_weight", "Operating weight", ("operating weight", "weight w", "weight"), ("operating_weight", "weight"), None, ()),
    ("dimensions", "Length / width / height", ("length / width / height", "l x w x h", "dimensions"), ("dimensions",), None, ()),
)

_KEEP_ROW = ("engine", "fuel", "horsepower", "weight", "length", "width", "height", "power")


def clean_title(title: str) -> str:
    title = re.sub(r"\s*[|–-]\s*Facebook Marketplace.*$", "", title or "", flags=re.I)
    title = re.sub(r"\s*[|–-]\s*Facebook$", "", title, flags=re.I)
    return re.sub(r"\s+", " ", title).strip()


def identify_machine(listing: dict) -> dict:
    """Make, model, year, category, family, attachments, and the OEM fields that apply."""
    title = clean_title(listing.get("title") or "")
    year = _year(listing, title)
    make, model = _make_model(listing, title, year)
    keyword_category, keyword_family = _keyword_category(title, listing.get("description") or "")
    family, category = _model_family(make, model)
    if not family:
        listed = str(listing.get("category") or "").strip()
        listed_family = _category_family(listed) if listed else ""
        if listed_family and listed_family != "other":
            family, category = listed_family, listed
        else:
            family = keyword_family or "other"
            category = keyword_category or _FAMILY_CATEGORY.get(family) or "Other Equipment"
    attachments = detect_attachments(listing, title)
    fields = spec_fields_for(family, attachments)
    return {
        "title": title,
        "year": year,
        "make": make,
        "model": model or title,
        "category": category,
        "family": family or "other",
        "attachments": attachments,
        "spec_fields": fields,
    }


def spec_fields_for(family: str, attachments: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    attached = set(attachments or ())
    allowed = []
    for key, _label, _needles, _wire, families, needed in SPEC_FIELDS:
        if families and family not in families:
            continue
        if needed and not (attached & set(needed)):
            continue
        allowed.append(key)
    return tuple(allowed)


def spec_query(ident: dict) -> str:
    parts = [ident.get("year"), ident.get("make"), ident.get("model")]
    family = ident.get("family") or ""
    if family == "trencher":
        parts.append("trencher")
    elif family == "hdd":
        parts.append("directional drill")
    elif family and family not in {"other", "drill"}:
        parts.append(family)
    attachments = ident.get("attachments") or []
    if "rocksaw" in attachments:
        parts.append("rocksaw")
    if "plow" in attachments:
        parts.append("plow")
    parts.append("specifications")
    return " ".join(str(part).strip() for part in parts if str(part).strip())


def detect_attachments(listing: dict, title: str = "") -> list[str]:
    listed = listing.get("attachments") or listing.get("attachment") or []
    found: list[str] = []
    if isinstance(listed, str):
        listed = [part.strip() for part in re.split(r"[,;/]", listed) if part.strip()]
    for item in listed:
        token = re.sub(r"[^a-z0-9]+", "", str(item).lower())
        if token in {"rocksaw", "saw", "hydrawheel"} or ("saw" in token and "backhoe" not in token):
            found.append("rocksaw")
        elif "plow" in token:
            found.append("plow")
        elif "thumb" in token:
            found.append("thumb")
        elif "bucket" in token or "4in1" in token:
            found.append("bucket")
        elif "pipe" in token and "load" in token:
            found.append("pipe_loader")
        elif "processor" in token or token in {"mp15", "shear"}:
            found.append("multiprocessor")
        elif "backhoe" in token:
            found.append("backhoe")
        elif "reel" in token:
            found.append("reel")
        elif token:
            found.append(token)
    blob = " ".join([
        title,
        listing.get("title") or "",
        listing.get("description") or "",
        " ".join(listing.get("highlights") or []),
        " ".join(str(item) for item in listed),
    ]).lower()
    for name, pattern in _ATTACHMENT_PATTERNS:
        if re.search(pattern, blob, re.I):
            found.append(name)
    ordered = []
    for name in ("rocksaw", "plow", "reel", "backhoe", "bore", "thumb", "bucket", "pipe_loader", "multiprocessor"):
        if name in found and name not in ordered:
            ordered.append(name)
    return ordered


def field_meta(key: str) -> tuple:
    for row in SPEC_FIELDS:
        if row[0] == key:
            return row
    return ("", "", (), (), None, ())


def field_for_label(label: str, allowed: tuple[str, ...] | list[str] | None = None) -> str:
    lowered = str(label or "").lower()
    keys = set(allowed) if allowed is not None else {row[0] for row in SPEC_FIELDS}
    ranked: list[tuple[int, str]] = []
    for key, _label, needles, _wire, _families, _needed in SPEC_FIELDS:
        if key not in keys:
            continue
        for needle in needles:
            if needle in lowered:
                ranked.append((-len(needle), key))
                break
    ranked.sort()
    return ranked[0][1] if ranked else ""


def wire_target(key: str, allowed: tuple[str, ...] | list[str] | None = None) -> str:
    token = str(key or "").strip().lower()
    keys = set(allowed) if allowed is not None else {row[0] for row in SPEC_FIELDS}
    for field, _label, _needles, aliases, _families, _needed in SPEC_FIELDS:
        if field not in keys:
            continue
        if token == field or token in aliases:
            return field
    return ""


def prefer_labels(family: str) -> tuple[str, ...]:
    if family == "hdd":
        return ("thrust", "pullback", "torque", "spindle", "engine", "power", "horse", "weight", "bore", "fuel")
    if family == "trencher":
        return ("trench", "saw", "plow", "depth", "width", "engine", "power", "horse", "weight", "fuel")
    if family == "excavator":
        return ("digging", "bucket", "reach", "engine", "power", "weight")
    return ("engine", "power", "horse", "weight", "length", "width", "height")


def keep_spec_row(label: str, allowed: tuple[str, ...] | list[str] | None) -> bool:
    lowered = str(label or "").lower()
    field = field_for_label(label, allowed)
    if field:
        return True
    if any(word in lowered for word in ("pullback", "thrust", "spindle")) and "pullback_force" not in (allowed or ()):
        return False
    return any(word in lowered for word in _KEEP_ROW)


def _year(listing: dict, title: str) -> str:
    raw = str(listing.get("year") or "").strip()
    if re.fullmatch(r"(?:19|20)\d{2}", raw):
        return raw
    match = re.search(r"\b((?:19|20)\d{2})\b", title) or re.search(
        r"\b((?:19|20)\d{2})\b", listing.get("description") or ""
    )
    return match.group(1) if match else raw


def make_from_model(model: str) -> str:
    """RT125 is Ditch Witch. RTX1250 is Vermeer. The X is the whole difference."""
    compact = re.sub(r"[^a-z0-9]+", "", (model or "").lower())
    for pattern, brand in (
        (r"^rtx\d", "Vermeer"),
        (r"^ctx\d", "Vermeer"),
        (r"^d\d+x\d", "Vermeer"),
        (r"^jt\d", "Ditch Witch"),
        (r"^rt\d", "Ditch Witch"),
        (r"^ht\d", "Ditch Witch"),
        (r"^mt\d", "Ditch Witch"),
        (r"^fx\d", "Ditch Witch"),
    ):
        if re.match(pattern, compact):
            return brand
    return ""


def _make_model(listing: dict, title: str, year: str) -> tuple[str, str]:
    rest = title
    if year and rest.startswith(year):
        rest = rest[len(year):].strip()
    make = str(listing.get("make") or "").strip()
    model = str(listing.get("model") or "").strip()
    lowered = rest.lower()
    parsed_make = ""
    parsed_model = rest
    for brand in _BRANDS:
        if lowered.startswith(brand.lower()):
            parsed_make = brand
            parsed_model = rest[len(brand):].strip(" -–")
            break
    parsed_model = re.split(
        r"\s+(?:horizontal|directional|drill|trencher|excavator|rocksaw|rock\s*saw|plow|reel|with)\b",
        parsed_model,
        maxsplit=1,
        flags=re.I,
    )[0].strip()
    model = model or parsed_model
    inferred = make_from_model(model)
    compact = re.sub(r"[^a-z0-9]+", "", (model or "").lower())
    got = re.sub(r"[^a-z0-9]+", " ", (make or parsed_make).lower()).strip()
    if inferred == "Ditch Witch" and re.match(r"^rt\d", compact) and not compact.startswith("rtx") and got in {"", "vermeer"}:
        make = "Ditch Witch"
    elif inferred == "Vermeer" and compact.startswith("rtx") and "ditch" in got:
        make = "Vermeer"
    else:
        make = make or parsed_make or inferred
    return make, model


def _keyword_category(title: str, description: str) -> tuple[str, str]:
    blob = f"{title} {description}".lower()
    for keys, name, family in _CATEGORIES:
        if any(key in blob for key in keys):
            return name, family
    return "Other Equipment", "other"


def _model_family(make: str, model: str) -> tuple[str, str]:
    make_key = re.sub(r"[^a-z0-9]+", " ", (make or "").lower()).strip()
    if make_key == "cat":
        make_key = "caterpillar"
    compact = re.sub(r"[^a-z0-9]+", "", (model or "").lower())
    if not compact:
        return "", ""
    for brands, pattern, family, category in _MODEL_FAMILIES:
        if make_key and make_key not in brands:
            continue
        if re.match(pattern, compact):
            return family, category
    return "", ""


def _category_family(category: str) -> str:
    text = (category or "").strip().lower()
    if text in _CATEGORY_FAMILY:
        return _CATEGORY_FAMILY[text]
    for name, family in _CATEGORY_FAMILY.items():
        if name and name in text:
            return family
    return "other"
