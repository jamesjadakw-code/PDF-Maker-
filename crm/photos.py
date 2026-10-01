"""Save Marketplace photos on the draft so the brochure can show them.

Facebook image links often refuse a browser on another site. The intake
downloads each public image and the sheet uses those saved files.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.request import Request, build_opener

from crm import store
from crm.specs import StayPublic, public_https

_MAX_BYTES = 8_000_000
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_OPENER = build_opener(StayPublic)


def image_ext(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return ".webp"
    return ""


def fetch_image(url: str) -> bytes:
    if not public_https(url):
        raise ValueError("Photo URL is not a public https image.")
    request = Request(
        url,
        headers={
            "User-Agent": _UA,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": "https://www.facebook.com/",
        },
    )
    with _OPENER.open(request, timeout=15) as response:
        data = response.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError("Photo is too large.")
    if not image_ext(data):
        raise ValueError("That URL did not return an image.")
    return data


def save_listing_photos(draft_id: str, urls: list[str], fetcher=None) -> list[str]:
    """Download listing photos. Return the src the brochure should use for each one."""
    fetcher = fetcher or fetch_image
    folder = _folder(draft_id)
    shown: list[str] = []
    for index, url in enumerate(list(urls)[:40]):
        try:
            data = fetcher(url)
            ext = image_ext(data)
            if not ext:
                raise ValueError("That URL did not return an image.")
            folder.mkdir(parents=True, exist_ok=True)
            name = f"{index}{ext}"
            (folder / name).write_bytes(data)
            shown.append(f"/api/marketplace/photo/{draft_id}/{name}")
        except (OSError, ValueError):
            shown.append(url)
    return shown


def photo_path(draft_id: str, name: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{12}", draft_id or ""):
        raise ValueError("Unknown photo.")
    if not re.fullmatch(r"\d{1,2}\.(jpg|png|gif|webp)", name or ""):
        raise ValueError("Unknown photo.")
    folder = (store.ROOT / "photos" / draft_id).resolve()
    path = (folder / name).resolve()
    if path.parent != folder or not path.is_file():
        raise ValueError("Unknown photo.")
    return path


def _folder(draft_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{12}", draft_id or ""):
        raise ValueError("Unknown draft.")
    return store.ROOT / "photos" / draft_id
