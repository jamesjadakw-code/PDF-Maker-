"""Save the verified BAM brochure PDF onto the machine card."""

from __future__ import annotations

import re
from pathlib import Path

from crm import store

_NAME = re.compile(r"[^A-Za-z0-9]+")


def brochure_dir() -> Path:
    path = store.ROOT / "brochures"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pdf_path(draft_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{12}", draft_id or ""):
        raise ValueError("Unknown brochure.")
    file = (brochure_dir() / f"{draft_id}.pdf").resolve()
    if file.parent != brochure_dir().resolve():
        raise ValueError("Unknown brochure.")
    return file


def pdf_filename(draft: dict) -> str:
    title = ((draft.get("listing") or {}).get("title") or "Unit").strip()
    slug = _NAME.sub("_", title).strip("_") or "Unit"
    return f"BAM_Brochure_{slug}.pdf"[:120]


def download_path(draft_id: str) -> str:
    return f"/api/marketplace/brochure/{draft_id}.pdf"


def attach_brochure(draft: dict) -> dict:
    """Write the brochure onto the machine card. A later upload can replace the file."""
    file = pdf_path(draft["id"])
    if not file.is_file():
        file.write_bytes(simple_pdf(draft))
    draft["machineCard"] = {
        "brochureSaved": True,
        "name": pdf_filename(draft),
        "pdf": download_path(draft["id"]),
    }
    return draft


def save_upload(draft_id: str, data: bytes) -> Path:
    if not data.startswith(b"%PDF"):
        raise ValueError("Send a PDF.")
    if len(data) > 20_000_000:
        raise ValueError("That PDF is too large.")
    file = pdf_path(draft_id)
    file.write_bytes(data)
    return file


def simple_pdf(draft: dict) -> bytes:
    """A letter-size stand-in until the sheet PDF is uploaded. Same words, one page."""
    listing = draft.get("listing") or {}
    brochure = draft.get("brochure") or {}
    photos = brochure.get("photos") or []
    lines = [
        "BIG ASS MOTORS",
        brochure.get("title") or listing.get("title") or "Equipment unit",
        brochure.get("status") or "Verified",
        f"Brochure photos: {len(photos)} of 10 max",
        f"Listing photos kept: {len(listing.get('photos') or [])}",
        "Download the laid-out sheet from the machine card.",
    ]
    text = "\\n".join(_pdf_escape(line) for line in lines)
    stream = f"BT /F1 14 Tf 48 740 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    parts = [b"%PDF-1.4\n"]
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in parts))
        parts.append(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = sum(len(part) for part in parts)
    xref_lines = [f"xref\n0 {len(objects) + 1}\n", "0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref_lines.append(f"{offset:010d} 00000 n \n")
    parts.append("".join(xref_lines).encode())
    parts.append(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return b"".join(parts)


def _pdf_escape(value: str) -> str:
    cleaned = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in value)
    return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
