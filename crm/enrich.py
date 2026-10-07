"""Fill missing OEM baseline specs for this make, model, year, and attachments.

Never block ingest. Never copy HDD pullback onto a trencher.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from crm.catalog import apply_catalog, catalog_covers, spec_sheet
from crm.machine import (
    SPEC_FIELDS,
    field_for_label,
    identify_machine,
    keep_spec_row,
    spec_query,
    wire_target,
)
from crm.specs import lookup_specs, specs_missing

SPEC_SECONDS = 12


def enrich_machine_with_oem_specs(scraped_item: dict, fetcher=None) -> dict:
    """Lookup published OEM figures for this unit. Returns the same listing dict."""
    try:
        return _enrich(scraped_item, fetcher)
    except Exception:
        scraped_item["is_oem_enriched"] = False
        scraped_item.setdefault("oemSpecs", scraped_item.get("oemSpecs") or [])
        return scraped_item


def _enrich(scraped_item: dict, fetcher=None) -> dict:
    if scraped_item.get("is_staged") is True or str(scraped_item.get("source_type") or "").lower() in {
        "staged", "internal", "original", "bam",
    }:
        return scraped_item

    ident = identify_machine(scraped_item)
    make = ident["make"]
    model = ident["model"]
    if not make or not model or model == ident["title"]:
        scraped_item["is_oem_enriched"] = False
        return scraped_item

    catalog_named = apply_catalog(scraped_item, ident)
    ident = identify_machine(scraped_item)
    make = ident["make"] or make
    model = ident["model"] or model
    scraped_item["year"] = ident["year"] or scraped_item.get("year") or ""
    scraped_item["make"] = make
    scraped_item["model"] = model
    scraped_item["category"] = ident["category"]
    scraped_item["model_category"] = ident["category"]
    scraped_item["attachments"] = ident["attachments"]
    scraped_item["spec_profile"] = ident["family"]

    allowed = ident["spec_fields"]
    named = {key: value for key, value in catalog_named.items() if key in allowed}
    cache_hit = catalog_covers(named, ident.get("family") or "")
    if not cache_hit:
        try:
            named.update(_from_wire(ident, allowed))
        except (OSError, ValueError, TimeoutError, HTTPError, URLError, TypeError, json.JSONDecodeError):
            pass
    extra_rows = list(scraped_item.pop("_catalog_rows", []) or [])
    rows = _filter_rows(list(scraped_item.get("oemSpecs") or []), allowed)
    if not cache_hit:
        probe = dict(scraped_item)
        probe["oemSpecs"] = []
        if specs_missing(probe):
            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    looked = _filter_rows(
                        list(pool.submit(lookup_specs, probe, fetcher).result(timeout=SPEC_SECONDS)),
                        allowed,
                    )
                for row in looked:
                    if row not in rows:
                        rows.append(row)
            except TimeoutError:
                pass
    for label, value in extra_rows:
        row = (str(label), str(value))
        if label and value and row not in rows:
            rows.append(row)
    named = _merge_named(scraped_item, named, rows, allowed)

    filled = []
    for key, _label, _needles, _wire, _families, _needed in SPEC_FIELDS:
        if key not in allowed:
            continue
        value = named.get(key) or scraped_item.get(key) or ""
        if value and str(value).strip().upper() not in {"N/A", "NA", "NONE"}:
            scraped_item[key] = str(value).strip()
            filled.append(key)
        else:
            scraped_item.setdefault(key, scraped_item.get(key) or "")

    named_rows = _rows_from_named(scraped_item, allowed)
    merged_rows: list[tuple[str, str]] = []
    for row in named_rows + list(rows):
        if row not in merged_rows:
            merged_rows.append(row)
    rows = merged_rows
    if rows:
        scraped_item["oemSpecs"] = rows
    else:
        scraped_item.setdefault("oemSpecs", [])
    scraped_item["spec_sheet"] = spec_sheet(scraped_item)

    scraped_item["is_oem_enriched"] = bool(filled or rows)
    if scraped_item["is_oem_enriched"]:
        scraped_item["enriched_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        scraped_item["specsStatus"] = "ready"
    else:
        scraped_item["specsStatus"] = "none"
    return scraped_item


def _from_wire(ident: dict, allowed: tuple[str, ...]) -> dict:
    token = os.environ.get("ANAKIN_WIRE_API_KEY", "").strip()
    if not token:
        return {}
    body = json.dumps({
        "action_id": "machinio_specs_lookup_v1",
        "parameters": {
            "search_query": spec_query(ident),
            "category_filter": ident.get("category") or ident.get("family") or "construction",
            "year": ident.get("year") or "",
            "attachments": ident.get("attachments") or [],
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
        target = wire_target(key, allowed)
        text = str(value or "").strip()
        if target and text and text.upper() not in {"N/A", "NA", "NONE"}:
            mapped[target] = text
    return mapped


def _merge_named(listing: dict, wired: dict, rows: list[tuple[str, str]], allowed: tuple[str, ...]) -> dict:
    named = {key: value for key, value in wired.items() if key in allowed}
    for key, _label, _needles, _wire, _families, _needed in SPEC_FIELDS:
        if key not in allowed:
            continue
        current = str(listing.get(key) or "").strip()
        if current and current.upper() not in {"N/A", "NA"}:
            named[key] = current
    for label, value in rows:
        field = field_for_label(label, allowed)
        if field and not named.get(field) and str(value).strip() and str(value).strip().upper() not in {"N/A", "NA", "NONE"}:
            named[field] = str(value).strip()
    if "dimensions" in allowed and not named.get("dimensions"):
        dims = _combine_dimensions(rows)
        if dims:
            named["dimensions"] = dims
    return named


def _filter_rows(rows: list, allowed: tuple[str, ...]) -> list[tuple[str, str]]:
    kept = []
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) < 2:
            continue
        label, value = str(row[0]).strip(), str(row[1]).strip()
        if label and value and keep_spec_row(label, allowed):
            kept.append((label, value))
    return kept


def _combine_dimensions(rows: list[tuple[str, str]]) -> str:
    found: dict[str, str] = {}
    for label, value in rows:
        lowered = str(label or "").lower()
        text = str(value or "").strip()
        if not text:
            continue
        for axis in ("length", "width", "height"):
            if axis in lowered and "pipe" not in lowered and "trench" not in lowered and "saw" not in lowered and axis not in found:
                found[axis] = text
    if len(found) >= 2:
        return " / ".join(found[axis] for axis in ("length", "width", "height") if axis in found)
    return ""


def _rows_from_named(listing: dict, allowed: tuple[str, ...]) -> list[tuple[str, str]]:
    labels = {key: label for key, label, _needles, _wire, _families, _needed in SPEC_FIELDS}
    return [
        (labels[key], listing[key])
        for key in allowed
        if key in labels and str(listing.get(key) or "").strip()
    ]
