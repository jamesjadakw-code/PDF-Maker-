"""Optional photo+text make/model/attachment read. Off unless GEMINI_API_KEY is set.

The scanner is constrained to the saved Lectura machinery master so a photo
snaps onto a known unit, then enrich loads that row's specs.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

VISION_SECONDS = 8
_MAX_IMAGE = 4_000_000
_PROMPT_HEAD = (
    "Analyze this heavy machinery listing image and text payload.\n"
    "1. Determine the core Manufacturer.\n"
    "2. Determine the exact Model designation string.\n"
    "3. Detect and itemize ALL attachments visible or mentioned "
    "(e.g., rocksaws, vibratory plows, buckets, thumbs, backhoes, reels).\n"
    "Choose make and model from this roster when the photo matches. "
    "Use the roster's exact model string.\n"
)
_PROMPT_TAIL = (
    "If none match, still return your best make and model.\n"
    'Return JSON only: {"make": "string", "model": "string", "detected_attachments": ["attachment name"]}'
)


def detect_machine_from_image(image_path: str | None, listing: dict | None = None) -> dict:
    """Return make/model/attachments from a listing photo. Empty dict if unset or failed."""
    token = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    if not token or not image_path:
        return {}
    try:
        return _detect(Path(image_path), listing or {}, token)
    except (OSError, ValueError, TimeoutError, HTTPError, URLError, TypeError, json.JSONDecodeError, KeyError):
        return {}


def _detect(path: Path, listing: dict, token: str) -> dict:
    if not path.is_file():
        return {}
    data = path.read_bytes()
    if not data or len(data) > _MAX_IMAGE:
        return {}
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/jpeg")
    import base64

    from crm.lectura import roster_lines, snap_identity

    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    roster = "\n".join(roster_lines())
    text = "\n".join(
        part for part in (
            listing.get("title") or "",
            listing.get("description") or "",
            _PROMPT_HEAD + roster + "\n" + _PROMPT_TAIL,
        ) if part
    )
    body = json.dumps({
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode("ascii")}},
                {"text": text},
            ]
        }],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }).encode()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={token}"
    )
    request = Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "BAM-CRM/1.0"},
    )
    with urlopen(request, timeout=VISION_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8", "replace") or "{}")
    raw = _response_text(payload)
    parsed = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.I | re.M).strip() or "{}")
    if not isinstance(parsed, dict):
        return {}
    attachments = parsed.get("detected_attachments") or parsed.get("attachments") or []
    if isinstance(attachments, str):
        attachments = [part.strip() for part in re.split(r"[,;/]", attachments) if part.strip()]
    make = str(parsed.get("make") or "").strip()
    model_name = str(parsed.get("model") or "").strip()
    result = {
        "make": make,
        "model": model_name,
        "detected_attachments": [str(item).strip() for item in attachments if str(item).strip()],
    }
    snapped = snap_identity(make, model_name)
    if snapped:
        result["make"] = snapped.get("make") or make
        result["model"] = snapped.get("model") or model_name
        result["category"] = snapped.get("category") or ""
        result["lectura_canonical"] = True
    return result


def _response_text(payload: dict) -> str:
    for candidate in payload.get("candidates") or []:
        for part in ((candidate.get("content") or {}).get("parts") or []):
            text = part.get("text")
            if text:
                return str(text)
    return str(payload.get("text") or "")
