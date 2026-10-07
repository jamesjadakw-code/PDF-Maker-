"""Photo make/model/attachment read through Grok 4.6.

Off unless XAI_API_KEY is set, or data/xai.key holds the key.
The scanner stays on the Lectura roster, then enrich loads that row.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

VISION_SECONDS = 60
_MAX_IMAGE = 4_000_000
MODEL = "grok-4.6"
REASONING = "high"
_API = "https://api.x.ai/v1/chat/completions"
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


def grok_key() -> str:
    """Env wins, including an empty value so tests can turn the call off."""
    if "XAI_API_KEY" in os.environ:
        return os.environ["XAI_API_KEY"].strip()
    data_dir = os.environ.get("BAM_DATA_DIR", "").strip()
    candidates = []
    if data_dir:
        candidates.append(Path(data_dir) / "xai.key")
    candidates.append(Path(__file__).resolve().parent.parent / "data" / "xai.key")
    for path in candidates:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    return ""


def detect_machine_from_image(image_path: str | None, listing: dict | None = None) -> dict:
    """Return make/model/attachments from a listing photo. Empty dict if unset or failed."""
    token = grok_key()
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

    model = os.environ.get("GROK_MODEL", MODEL).strip() or MODEL
    effort = os.environ.get("GROK_REASONING", REASONING).strip() or REASONING
    roster = "\n".join(roster_lines())
    text = "\n".join(
        part for part in (
            listing.get("title") or "",
            listing.get("description") or "",
            _PROMPT_HEAD + roster + "\n" + _PROMPT_TAIL,
        ) if part
    )
    data_url = f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    body = json.dumps({
        "model": model,
        "reasoning_effort": effort,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}},
                {"type": "text", "text": text},
            ],
        }],
    }).encode()
    request = Request(
        _API,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "BAM-CRM/1.0",
        },
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
    for choice in payload.get("choices") or []:
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            bits = []
            for part in content:
                if isinstance(part, str) and part.strip():
                    bits.append(part)
                elif isinstance(part, dict) and part.get("text"):
                    bits.append(str(part["text"]))
            if bits:
                return "\n".join(bits)
    return ""
