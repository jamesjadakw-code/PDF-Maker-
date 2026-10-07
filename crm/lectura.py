"""Fill missing brochure fields from the saved Lectura machinery master.

Only maps onto the CRM spec fields. Extra Lectura keys stay unused.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from crm.machine import spec_fields_for

_MASTER = Path(__file__).with_name("lectura_machinery_master.json")

_FAMILY = {
    "crawler_excavators": ("excavator", "Excavators"),
    "backhoe_loaders": ("backhoe", "Backhoes"),
    "horizontal_directional_drills": ("hdd", "Directional Drills"),
    "bulldozers": ("dozer", "Dozers"),
}

_MAKE_ALIASES = {
    "cat": "caterpillar",
    "caterpillar": "caterpillar",
    "deere": "johndeere",
    "john deere": "johndeere",
    "johndeere": "johndeere",
    "jd": "johndeere",
    "vermeer": "vermeer",
    "ditch witch": "ditchwitch",
    "ditchwitch": "ditchwitch",
    "dw": "ditchwitch",
}


@lru_cache(maxsize=1)
def _rows() -> tuple[dict, ...]:
    payload = json.loads(_MASTER.read_text(encoding="utf-8"))
    rows = []
    for group, block in payload.items():
        family, category = _FAMILY.get(group, ("", ""))
        for item in block.get("models") or []:
            row = dict(item)
            row["family"] = family
            row["category"] = category
            rows.append(row)
    return tuple(rows)


def apply_lectura(listing: dict, ident: dict | None = None) -> dict:
    """Copy Lectura figures onto empty allowed CRM fields. Returns named values filled."""
    from crm.machine import identify_machine

    ident = ident or identify_machine(listing)
    hit = lookup_lectura(ident.get("make") or "", ident.get("model") or "")
    if not hit:
        listing["lectura_hit"] = False
        return {}
    listing["lectura_hit"] = True
    if hit.get("family") and (ident.get("family") in {"", "other"} or not ident.get("family")):
        listing["category"] = hit["category"]
        listing["model_category"] = hit["category"]
        listing["spec_profile"] = hit["family"]
        ident = identify_machine(listing)
        ident["family"] = hit["family"]
        ident["category"] = hit["category"]
        ident["spec_fields"] = spec_fields_for(hit["family"], ident.get("attachments") or [])
    allowed = set(ident.get("spec_fields") or spec_fields_for(ident.get("family") or "other", ident.get("attachments") or []))
    named = {}
    for key, value in (hit.get("named") or {}).items():
        if key in allowed and value:
            named[key] = value
    return named


def lookup_lectura(make: str, model: str) -> dict | None:
    make_key = _make_key(make)
    compact = _compact(model)
    if not make_key or not compact:
        return None
    matches = []
    for row in _rows():
        if _make_key(row.get("make") or "") != make_key:
            continue
        token = _compact(row.get("model") or "")
        if not token:
            continue
        if compact == token:
            matches.append((0, -len(token), row))
        elif _model_matches(compact, token):
            matches.append((1, -len(token), row))
    if not matches:
        return None
    matches.sort()
    row = matches[0][2]
    return {
        "make": row.get("make") or "",
        "model": row.get("model") or "",
        "family": row.get("family") or "",
        "category": row.get("category") or "",
        "named": _named(row),
        "source": "Lectura machinery master",
    }


def roster_lines() -> list[str]:
    """Make/model lines the photo scanner must choose from."""
    return [f"- {row.get('make')} {row.get('model')} ({row.get('category')})" for row in _rows()]


def snap_identity(make: str, model: str) -> dict | None:
    """Canonical Lectura row for a photo or text guess."""
    return lookup_lectura(make, model)


def _named(row: dict) -> dict:
    named = {}
    if row.get("power_kw") is not None:
        named["engine_power"] = _hp(row["power_kw"])
    if row.get("weight_t") is not None:
        named["operating_weight"] = _lb_from_t(row["weight_t"])
    if row.get("bucket_capacity_m3") is not None:
        named["bucket_capacity"] = _yd3(row["bucket_capacity_m3"])
    if row.get("dig_depth_m") is not None:
        named["digging_depth"] = _ft(row["dig_depth_m"])
    if row.get("pullback_kn") is not None:
        named["pullback_force"] = _lbf(row["pullback_kn"])
    if row.get("thrust_kn") is not None:
        named["thrust_force"] = _lbf(row["thrust_kn"])
    if row.get("torque_nm") is not None:
        named["max_spindle_torque"] = _ftlb(row["torque_nm"])
    if row.get("blade_width_m") is not None:
        named["dimensions"] = f"{_ft(row['blade_width_m'])} blade"
    return named


def _make_key(make: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", (make or "").lower()).strip()
    return _MAKE_ALIASES.get(text, text.replace(" ", ""))


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _model_matches(compact: str, token: str) -> bool:
    if not compact or not token:
        return False
    if compact == token:
        return True
    longer, shorter = (compact, token) if len(compact) >= len(token) else (token, compact)
    rest = longer[len(shorter):]
    return longer.startswith(shorter) and bool(rest) and rest[0].isalpha()


def _hp(kw) -> str:
    return f"{round(float(kw) * 1.34102209)} hp"


def _lb_from_t(tonnes) -> str:
    return f"{round(float(tonnes) * 2204.6226218):,} lb"


def _yd3(m3) -> str:
    value = float(m3) * 1.30795062
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text} yd³"


def _ft(meters) -> str:
    feet = float(meters) / 0.3048
    text = f"{feet:.1f}".rstrip("0").rstrip(".")
    return f"{text} ft"


def _lbf(kn) -> str:
    pounds = int(round(float(kn) * 224.80894387 / 100.0) * 100)
    return f"{pounds:,} lb"


def _ftlb(nm) -> str:
    return f"{round(float(nm) * 0.737562149):,} ft·lb"
