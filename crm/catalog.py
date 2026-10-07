"""Static OEM cache for third-party ingest. Instant make/model/attachment hits.

Network lookup only runs when this matrix misses. Staged inventory is ignored.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from crm.machine import SPEC_FIELDS, identify_machine, spec_fields_for

# Pre-seeded baseline figures. Keys are compact make / compact model.
MANUFACTURER_SPEC_CATALOG = {
    "vermeer": {
        "rtx1250": {
            "base_hp": 121,
            "tracks": "Quad",
            "default_app": "Trenching/Plowing",
            "configuration": "Ride-on trencher",
        },
        "d20x22": {
            "base_pullback": "20,000 lbs",
            "base_thrust": "22,000 lbs",
            "application": "HDD Drill",
        },
        "attachments": {
            "vibratory plow": {
                "model": "VP125",
                "max_depth": "42 in",
                "notes": "Heavy utility infrastructure cable layer",
                "token": "plow",
            },
            "rocksaw": {
                "model": "HydraWheel",
                "cut_depth": "18-24 in",
                "target_terrain": "Solid rock/concrete",
                "token": "rocksaw",
            },
            "pipe loader": {
                "type": "Automated hydraulic",
                "capacity": "Full rod box",
                "token": "pipe_loader",
            },
        },
    },
    "caterpillar": {
        "420": {
            "base_hp": 93,
            "configuration": "Backhoe Loader",
            "operating_weight": "17,000 lbs",
        },
        "d6": {
            "base_hp": 215,
            "configuration": "Track Bulldozer",
            "blade_capacity": "7.1 yd³",
        },
        "attachments": {
            "4wd backhoe assembly": {
                "model": "CAT 420-Rear",
                "dig_depth": "14.3 ft",
                "bucket_force": "15,000 lbs",
                "token": "backhoe",
            },
            "mp15 multi-processor": {
                "type": "Demolition shear/crusher",
                "jaw_opening": "28 in",
                "token": "multiprocessor",
            },
            "hydraulic thumb": {
                "type": "Progressive link",
                "utility": "Object manipulation/grapple",
                "token": "thumb",
            },
        },
    },
    "deere": {
        "4045tf": {
            "physical_length": "128 in",
            "physical_weight": "7,980 lbs",
            "low_speed": "0.6 mph",
        },
        "310": {
            "base_hp": 91,
            "operating_weight": "14,800 lbs",
            "configuration": "Backhoe Loader",
        },
        "attachments": {
            "rear backhoe boom": {
                "model": "Deere Extended",
                "max_dig_depth": "14 ft 1 in",
                "token": "backhoe",
            },
            "4-in-1 loader bucket": {
                "capacity": "1.2 yd³",
                "front_utility": "Scrape, grab, dump, doze",
                "token": "bucket",
            },
        },
    },
    "ditchwitch": {
        "rt115": {
            "base_hp": 115,
            "configuration": "Ride-on trencher",
            "default_app": "Trenching",
        },
        "rt125": {
            "base_hp": 121,
            "engine": "Cummins F3.8 turbocharged, charge-air cooled",
            "cylinders": 4,
            "displacement": "232 in³ / 3.8 L",
            "rated_speed": "2,200 rpm",
            "emissions": "EPA Tier 4 Final / EU Stage V",
            "tracks": "Quad 450x86x42 rubber, chevron",
            "configuration": "RT125 Quad ride-on tractor",
            "default_app": "Trenching/Plowing",
            "fuel": "Diesel",
            "ground_drive": "Hydrostatic",
            "attachment_drive": "Hydrostatic",
            "operating_weight": "15,300 lb",
            "max_tractor_weight": "27,200 lb",
            "hydrawheel_max_weight": "33,000 lb",
            "front_counterweight": "1,300 lb",
            "side_counterweight": "250 lb each",
            "dimensions": "166 in L x 89 in W x 120 in H",
            "wheelbase": "79 in",
            "tread": "71 in",
            "ground_clearance": "15.5 in",
            "approach_angle": "34°",
            "forward_speed": "6.9 mph",
            "reverse_speed": "4.0 mph",
            "turning_circle_front": "42.4 ft",
            "turning_circle_4ws": "21.6 ft",
            "fuel_tank": "38 gal",
            "def_tank": "4.9 gal",
            "engine_oil": "13.7 qt",
            "hydraulic_system": "30 gal",
            "hydraulic_reservoir": "25 gal",
            "coolant": "4.9 gal",
            "ground_drive_flow": "45 gpm @ 6,300 psi",
            "attachment_flow": "44 gpm @ 6,500 psi",
            "auxiliary_flow": "5.3 gpm @ 3,000 psi",
            "blade_width": "80 in",
            "blade_height": "17 in",
            "blade_lift": "26 in above grade",
            "blade_drop": "10 in below grade",
            "operator_noise": "80 dBA",
            "source": "Ditch Witch RT125 Quad literature 2024",
            "attachments": {
                "rocksaw": {
                    "model": "RS40",
                    "cut_depth": "40 in",
                    "trench_width": "4.5 / 6 / 8 in",
                    "attachment_weight": "5,900 lb",
                    "token": "rocksaw",
                },
                "vibratory plow": {
                    "model": "VP120Q",
                    "max_depth": "42 in",
                    "attachment_weight": "2,600 lb without blade",
                    "notes": "Front vibratory plow; cover depth depends on blade and soil",
                    "token": "plow",
                },
                "reel": {
                    "model": "RC30",
                    "type": "Rear reel carrier",
                    "reel_diameter": "96 in max",
                    "internal_width": "54 in",
                    "capacity": "3,000 lb",
                    "utility": "Fiber and cable payoff",
                    "token": "reel",
                },
                "reel carrier": {
                    "model": "RC30",
                    "type": "Rear reel carrier",
                    "reel_diameter": "96 in max",
                    "internal_width": "54 in",
                    "capacity": "3,000 lb",
                    "utility": "Fiber and cable payoff",
                    "token": "reel",
                },
                "trencher": {
                    "model": "CT120H",
                    "trench_depth": "93 in",
                    "trench_width": "24 in",
                    "attachment_weight": "1,750 lb",
                    "token": "trencher",
                },
                "backhoe": {
                    "model": "BH120",
                    "dig_depth": "108 in",
                    "reach": "158 in",
                    "bucket_width": "12-24 in",
                    "attachment_weight": "3,300 lb without bucket",
                    "token": "backhoe",
                },
            },
        },
        "attachments": {
            "rocksaw": {
                "notes": "Saw depth depends on the mounted wheel",
                "token": "rocksaw",
            },
            "vibratory plow": {
                "token": "plow",
            },
            "reel": {
                "type": "Rear reel carrier",
                "utility": "Fiber and cable payoff",
                "token": "reel",
            },
            "reel carrier": {
                "type": "Rear reel carrier",
                "utility": "Fiber and cable payoff",
                "token": "reel",
            },
        },
    },
}

_MAKE_ALIASES = {
    "cat": "caterpillar",
    "caterpillar": "caterpillar",
    "deere": "deere",
    "john deere": "deere",
    "johndeere": "deere",
    "jd": "deere",
    "vermeer": "vermeer",
    "ditch witch": "ditchwitch",
    "ditchwitch": "ditchwitch",
    "dw": "ditchwitch",
}

_CONFIG_FAMILY = (
    ("hdd drill", "hdd", "Directional Drills"),
    ("directional", "hdd", "Directional Drills"),
    ("backhoe", "backhoe", "Backhoes"),
    ("bulldozer", "dozer", "Dozers"),
    ("dozer", "dozer", "Dozers"),
    ("trencher", "trencher", "Trenchers & Rock Saws"),
    ("trenching", "trencher", "Trenchers & Rock Saws"),
    ("plowing", "trencher", "Trenchers & Rock Saws"),
)

_BASE_NAMED = (
    ("base_hp", "engine_power", "{0} hp"),
    ("engine_power", "engine_power", "{0}"),
    ("base_pullback", "pullback_force", "{0}"),
    ("base_thrust", "thrust_force", "{0}"),
    ("operating_weight", "operating_weight", "{0}"),
    ("physical_weight", "operating_weight", "{0}"),
    ("physical_length", "dimensions", "{0}"),
    ("dimensions", "dimensions", "{0}"),
    ("blade_capacity", "bucket_capacity", "{0}"),
)

_ATTACH_NAMED = (
    ("max_depth", "plow_depth", "plow"),
    ("cut_depth", "saw_depth", "rocksaw"),
    ("dig_depth", "digging_depth", "backhoe"),
    ("max_dig_depth", "digging_depth", "backhoe"),
    ("capacity", "bucket_capacity", "bucket"),
)


def spec_sheet(listing: dict) -> list[dict]:
    """Brochure-facing identity and CRM spec fields. Extra catalog keys stay off the sheet."""
    ident = identify_machine(listing)
    rows: list[dict] = []
    seen: set[str] = set()

    def add(label: str, value) -> None:
        text = str(value or "").strip()
        if not text or text.upper() in {"N/A", "NA", "NONE"}:
            return
        key = re.sub(r"[^a-z0-9]+", "", label.lower())
        if not key or key in seen:
            return
        seen.add(key)
        rows.append({"label": label, "value": text})

    add("Year", listing.get("year") or ident.get("year"))
    add("Make", ident.get("make") or listing.get("make"))
    add("Model", ident.get("model") or listing.get("model"))
    add("Category", ident.get("category") or listing.get("category"))
    add("Hours", listing.get("hours"))
    allowed = spec_fields_for(ident.get("family") or "other", ident.get("attachments") or listing.get("attachments") or [])
    for key, label, _needles, _wire, _families, _needed in SPEC_FIELDS:
        if key in allowed:
            add(label, listing.get(key))
    for label, value in listing.get("oemSpecs") or []:
        from crm.machine import field_for_label

        if field_for_label(str(label), allowed):
            add(str(label), value)
    names = []
    for item in listing.get("compiled_attachments") or []:
        token = str(item.get("token") or item.get("attachment_name") or "").strip()
        model = str(item.get("model") or "").strip()
        names.append(f"{model} {token}".strip() if model else token)
    if not names:
        names = [str(item) for item in (ident.get("attachments") or listing.get("attachments") or []) if item]
    if names:
        add("Attachments", ", ".join(names))
    return rows


def process_incoming_third_party_listing(listing: dict, image_path: str | None = None, fetcher=None) -> dict:
    """Facebook / scrape ingest entry. Catalog first, optional photo parse, never blocks."""
    try:
        if _is_staged(listing):
            return listing
        listing["is_staged"] = False
        listing["source_type"] = listing.get("source_type") or "scrape"
        listing.setdefault("source_platform", "Third-Party Scrape Stream")
        listing["ingested_timestamp"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if image_path:
            from crm.vision import detect_machine_from_image

            visual = detect_machine_from_image(image_path, listing)
            _merge_visual(listing, visual)
        from crm.enrich import enrich_machine_with_oem_specs

        return enrich_machine_with_oem_specs(listing, fetcher)
    except Exception:
        listing["is_oem_enriched"] = listing.get("is_oem_enriched") or False
        listing.setdefault("oemSpecs", listing.get("oemSpecs") or [])
        return listing


def apply_catalog(listing: dict, ident: dict | None = None) -> dict:
    """Copy cache figures onto allowed CRM fields. Returns named values filled from cache."""
    ident = ident or identify_machine(listing)
    hit = lookup_catalog(ident.get("make") or "", ident.get("model") or "")
    if not hit:
        listing.setdefault("compiled_attachments", [])
        listing["catalog_hit"] = False
        return {}
    listing["catalog_hit"] = True
    listing["catalog_payload"] = dict(hit["payload"])
    if hit.get("family") and (ident.get("family") in {"", "other"} or not ident.get("family")):
        listing["category"] = hit["category"]
        listing["model_category"] = hit["category"]
        listing["spec_profile"] = hit["family"]
        ident = identify_machine(listing)
        ident["family"] = hit["family"]
        ident["category"] = hit["category"]
        ident["spec_fields"] = spec_fields_for(hit["family"], ident.get("attachments") or [])
    compiled = _compile_attachments(ident.get("attachments") or [], hit["attachment_index"])
    tokens = [row.get("token") for row in compiled if row.get("token")]
    if tokens:
        merged = list(ident.get("attachments") or [])
        for token in tokens:
            if token not in merged:
                merged.append(token)
        listing["attachments"] = merged
        ident["attachments"] = merged
        ident["spec_fields"] = spec_fields_for(ident.get("family") or "other", merged)
    listing["compiled_attachments"] = compiled
    allowed = set(spec_fields_for(ident.get("family") or "other", listing.get("attachments") or ident.get("attachments") or []))
    ident["spec_fields"] = tuple(allowed)
    named = {}
    for src, dest, template in _BASE_NAMED:
        if dest not in allowed:
            continue
        value = hit["payload"].get(src)
        text = _format_figure(value, template)
        if text:
            named[dest] = text
    for row in compiled:
        token = row.get("token") or ""
        for src, dest, needed in _ATTACH_NAMED:
            if needed and token != needed:
                continue
            if dest not in allowed:
                continue
            text = str(row.get(src) or "").strip()
            if text:
                named.setdefault(dest, text)
    return named


def catalog_covers(named: dict, family: str) -> bool:
    """True when the cache already filled the figures that family must have."""
    if family == "hdd":
        return bool(named.get("pullback_force") or named.get("thrust_force"))
    if family == "trencher":
        return bool(named.get("trench_depth") or named.get("plow_depth") or named.get("saw_depth"))
    if family in {"backhoe", "excavator"}:
        return bool(named.get("digging_depth") or named.get("engine_power"))
    if family == "dozer":
        return bool(named.get("engine_power") or named.get("operating_weight"))
    return False


def lookup_catalog(make: str, model: str) -> dict | None:
    make_key = _make_key(make)
    if not make_key or make_key not in MANUFACTURER_SPEC_CATALOG:
        return None
    brand = MANUFACTURER_SPEC_CATALOG[make_key]
    attachments = dict(brand.get("attachments") or {})
    compact = _compact(model)
    payload = {}
    family = ""
    category = ""
    for key, row in brand.items():
        if key == "attachments" or not isinstance(row, dict):
            continue
        if _model_matches(compact, key):
            payload = {item: value for item, value in row.items() if item != "attachments"}
            attachments.update(row.get("attachments") or {})
            family, category = _family_from_payload(row)
            break
    return {
        "make_key": make_key,
        "payload": payload,
        "attachment_index": attachments,
        "family": family,
        "category": category,
    }


def _compile_attachments(detected: list[str], index: dict) -> list[dict]:
    compiled = []
    seen = set()
    for tool in detected:
        lower = str(tool or "").lower().strip()
        if not lower:
            continue
        for catalog_key, spec in index.items():
            key = catalog_key.lower()
            if lower in key or key in lower or (spec.get("token") and spec["token"] in lower):
                marker = spec.get("token") or key
                if marker in seen:
                    continue
                seen.add(marker)
                compiled.append({"attachment_name": tool, **spec})
    return compiled


def _merge_visual(listing: dict, visual: dict) -> None:
    if not visual:
        return
    if visual.get("make") and not str(listing.get("make") or "").strip():
        listing["make"] = visual["make"]
    if visual.get("model") and not str(listing.get("model") or "").strip():
        listing["model"] = visual["model"]
    incoming = visual.get("detected_attachments") or visual.get("attachments") or []
    if not incoming:
        return
    current = listing.get("attachments")
    if not isinstance(current, list):
        current = []
    blob = current + list(incoming)
    listing["attachments"] = blob
    listing["detected_attachments"] = list(incoming)


def _is_staged(listing: dict) -> bool:
    source = str(listing.get("source_type") or "").strip().lower()
    return listing.get("is_staged") is True or source in {"staged", "internal", "original", "bam"}


def _make_key(make: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", (make or "").lower()).strip()
    return _MAKE_ALIASES.get(text, text.replace(" ", ""))


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _model_matches(compact: str, key: str) -> bool:
    token = _compact(key)
    if not compact or not token:
        return False
    if compact == token:
        return True
    # RT125 is not RTX1250. Require a letter suffix (420F), never a digit slip.
    rest = compact[len(token):] if compact.startswith(token) else ""
    if not rest or not rest[0].isalpha():
        return False
    if token.startswith("rt") and not token.startswith("rtx") and compact.startswith("rtx"):
        return False
    return True


def _family_from_payload(row: dict) -> tuple[str, str]:
    blob = " ".join(str(row.get(key) or "") for key in ("configuration", "application", "default_app")).lower()
    for needle, family, category in _CONFIG_FAMILY:
        if needle in blob:
            return family, category
    return "", ""


def _format_figure(value, template: str) -> str:
    if value is None or value == "":
        return ""
    text = str(value).strip()
    if not text or text.upper() in {"N/A", "NA", "NONE"}:
        return ""
    if "{0}" not in template:
        return text
    if template.endswith(" hp") and re.search(r"\bhp\b", text, re.I):
        return text
    if template == "{0} hp" and str(value).replace(".", "", 1).isdigit():
        return f"{value} hp"
    return template.format(text)
