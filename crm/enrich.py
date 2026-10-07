"""Fill missing OEM baseline specs on a third-party scrape. Never block ingest."""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from crm.marketplace import machine_fields
from crm.specs import lookup_specs, specs_missing

SPEC_SECONDS = 12

_NAMED = (
    ("pullback_force", ("pullback",)),
    ("thrust_force", ("thrust",)),
    ("max_spindle_torque", ("spindle torque", "max torque", "torque")),
    ("engine_power", ("horsepower", "engine power", "gross power", "rated power", "power")),
    ("operating_weight", ("operating weight", "weight w", "weight")),
    ("dimensions", ("length / width / height", "l x w x h", "dimensions")),
)

_WIRE_KEYS = {
    "pullback_force": "pullback_force",
    "pullback": "pullback_force",
    "thrust_force": "thrust_force",
    "thrust": "thrust_force",
    "max_spindle_torque": "max_spindle_torque",
    "spindle_torque": "max_spindle_torque",
    "engine_power": "engine_power",
    "power": "engine_power",
    "operating_weight": "operating_weight",
    "weight": "operating_weight",
    "dimensions": "dimensions",
}


def enrich_machine_with_oem_specs(scraped_item: dict, fetcher=None) -> dict:
    """Lookup published OEM figures for make/model. Returns the same listing dict."""
    try:
        return _enrich(scraped_item, fetcher)
    except Exception:
        scraped_item["is_oem_enriched"] = False
        scraped_item.setdefault("oemSpecs", scraped_item.get("oemSpecs") or [])
        return scraped_item


def _enrich(scraped_item: dict, fetcher=None) -> dict:
    fields = machine_fields(scraped_item)
    make = str(scraped_item.get("make") or fields.get("make") or "").strip()
    model = str(scraped_item.get("model") or fields.get("model") or "").strip()
    if not make or not model or model == fields.get("title"):
        scraped_item["is_oem_enriched"] = False
        return scraped_item

    named = {}
    try:
        named = _from_wire(make, model, fields.get("category") or scraped_item.get("category") or "")
    except (OSError, ValueError, TimeoutError, HTTPError, URLError, TypeError, json.JSONDecodeError):
        named = {}
    rows = list(scraped_item.get("oemSpecs") or [])
    if specs_missing(scraped_item) and not rows:
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                rows = list(pool.submit(lookup_specs, scraped_item, fetcher).result(timeout=SPEC_SECONDS))
        except TimeoutError:
            rows = []
    named = _merge_named(scraped_item, named, rows)

    filled = []
    for key, _needles in _NAMED:
        value = named.get(key) or scraped_item.get(key) or ""
        if value and str(value).strip().upper() not in {"N/A", "NA", "NONE"}:
            scraped_item[key] = str(value).strip()
            filled.append(key)
        else:
            scraped_item.setdefault(key, scraped_item.get(key) or "")

    if filled and not rows:
        rows = _rows_from_named(scraped_item)
    if rows:
        scraped_item["oemSpecs"] = rows
    else:
        scraped_item.setdefault("oemSpecs", [])

    scraped_item["is_oem_enriched"] = bool(filled or rows)
    if scraped_item["is_oem_enriched"]:
        scraped_item["enriched_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        scraped_item["specsStatus"] = "ready"
    else:
        scraped_item["specsStatus"] = "none"
    return scraped_item


def _from_wire(make: str, model: str, category: str) -> dict:
    token = os.environ.get("ANAKIN_WIRE_API_KEY", "").strip()
    if not token:
        return {}
    body = json.dumps({
        "action_id": "machinio_specs_lookup_v1",
        "parameters": {
            "search_query": f"{make} {model} specifications",
            "category_filter": category or "construction",
        },
    }).encode()
    request = Request(
        "https://api.anakin.io/v1/wire/task",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "BAM-CRM/1.0",
        },
    )
    with urlopen(request, timeout=SPEC_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8", "replace") or "{}")
    specs = payload.get("specs") or payload.get("data") or payload
    if not isinstance(specs, dict):
        return {}
    if isinstance(specs.get("specs"), dict):
        specs = specs["specs"]
    mapped = {}
    for key, value in specs.items():
        target = _WIRE_KEYS.get(str(key).strip().lower())
        text = str(value or "").strip()
        if target and text and text.upper() not in {"N/A", "NA", "NONE"}:
            mapped[target] = text
    return mapped


def _merge_named(listing: dict, wired: dict, rows: list[tuple[str, str]]) -> dict:
    named = dict(wired)
    for key, _needles in _NAMED:
        current = str(listing.get(key) or "").strip()
        if current and current.upper() not in {"N/A", "NA"}:
            named[key] = current
    for label, value in rows:
        field = _field_for_label(label)
        if field and not named.get(field) and str(value).strip():
            named[field] = str(value).strip()
    if not named.get("dimensions"):
        dims = _combine_dimensions(rows)
        if dims:
            named["dimensions"] = dims
    return named


def _field_for_label(label: str) -> str:
    lowered = str(label or "").lower()
    for field, needles in _NAMED:
        for needle in needles:
            if needle in lowered:
                return field
    return ""


def _combine_dimensions(rows: list[tuple[str, str]]) -> str:
    found: dict[str, str] = {}
    for label, value in rows:
        lowered = str(label or "").lower()
        text = str(value or "").strip()
        if not text:
            continue
        for axis in ("length", "width", "height"):
            if axis in lowered and "pipe" not in lowered and axis not in found:
                found[axis] = text
    if len(found) >= 2:
        return " / ".join(found[axis] for axis in ("length", "width", "height") if axis in found)
    return ""


def _rows_from_named(listing: dict) -> list[tuple[str, str]]:
    labels = {
        "pullback_force": "Pullback force",
        "thrust_force": "Thrust force",
        "max_spindle_torque": "Spindle torque, max",
        "engine_power": "Power",
        "operating_weight": "Operating weight",
        "dimensions": "Length / width / height",
    }
    return [
        (labels[key], listing[key])
        for key in labels
        if str(listing.get(key) or "").strip()
    ]
