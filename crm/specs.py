"""Look up published machine specs when a listing does not include them.

The search is an HTTPS request for the make and model. Results are read from
public pages only. Location, the Marketplace URL, and the asking price are
not part of this lookup.
"""

from __future__ import annotations

import ipaddress
import re
import socket
from html import unescape
from urllib.parse import quote_plus, unquote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from crm.machine import field_for_label, identify_machine, keep_spec_row, prefer_labels, spec_query

_MEASURE = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s*(?:lb|ft·lb|ft|in|hp|rpm|gpm|psi|mph|kN|N·m|mm|kg|kW|gal|qt)\b",
    re.I,
)
_WORD_VALUES = {"diesel", "gasoline", "liquid", "direct", "turbocharged", "water"}
_MAX_BYTES = 8_000_000
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def specs_missing(listing: dict) -> bool:
    """True when the listing text has no published spec figures."""
    if listing.get("oemSpecs"):
        return False
    text = " ".join([
        listing.get("description") or "",
        " ".join(listing.get("highlights") or []),
    ])
    return len(_MEASURE.findall(text)) < 3


def lookup_specs(listing: dict, fetcher=None) -> list[tuple[str, str]]:
    """Search for this make/model/year and return label/value rows. Empty if none are found."""
    if not specs_missing(listing):
        return []
    ident = identify_machine(listing)
    query = spec_query(ident)
    if not query.strip() or query.strip().lower() == "specifications":
        return []
    allowed = ident.get("spec_fields") or ()
    family = ident.get("family") or ""
    fetcher = fetcher or UrlFetcher()
    for link in search_links(query, fetcher)[:3]:
        try:
            text = fetcher.read(link)
        except (OSError, ValueError, ImportError):
            continue
        rows = [
            (label, value)
            for label, value in parse_spec_text(text)
            if keep_spec_row(label, allowed)
        ]
        ranked = _prefer(rows, family)[:18]
        if _usable_sheet(ranked, family, allowed):
            return ranked
    return []


def search_links(query: str, fetcher) -> list[str]:
    url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    html = fetcher.get(url).decode("utf-8", "replace")
    found: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r"uddg=([^&\"']+)", html):
        link = unquote(raw)
        if not link.startswith("https://") or link in seen:
            continue
        if not public_https(link):
            continue
        seen.add(link)
        found.append(link)
    model = query.lower()
    found.sort(key=lambda link: _rank(link, model), reverse=True)
    return found


def parse_spec_text(text: str) -> list[tuple[str, str]]:
    """Read a spec sheet into label / US-value rows."""
    lines = [re.sub(r"\s+", " ", unescape(line)).strip(" •\t") for line in text.splitlines()]
    lines = [line for line in lines if line]
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    index = 0
    while index < len(lines):
        line = lines[index]
        if _skip(line) or _is_value(line):
            index += 1
            continue
        if index + 1 < len(lines) and _is_value(lines[index + 1]):
            label = line.rstrip(":").strip()
            value = lines[index + 1].strip()
            key = label.lower()
            if label and key not in seen and len(label) <= 48:
                seen.add(key)
                rows.append((label, value))
            index += 2
            if index < len(lines) and _is_value(lines[index]):
                index += 1
            continue
        index += 1
    return rows


def public_https(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or host in {"localhost"} or host.endswith(".local"):
        return False
    if host.replace(".", "").isdigit():
        return _public_ip(host)
    try:
        addresses = socket.getaddrinfo(host, 443)
    except socket.gaierror:
        return False
    return all(_public_ip(item[4][0]) for item in addresses)


class StayPublic(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not public_https(newurl):
            raise ValueError("Spec search refused a non-public redirect.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrlFetcher:
    def __init__(self):
        self.opener = build_opener(StayPublic)

    def get(self, url: str) -> bytes:
        if not public_https(url):
            raise ValueError("Spec search only reads public https pages.")
        request = Request(url, headers={"User-Agent": _UA, "Accept": "text/html,application/pdf"})
        with self.opener.open(request, timeout=20) as response:
            data = response.read(_MAX_BYTES + 1)
        if len(data) > _MAX_BYTES:
            raise ValueError("Spec page is too large.")
        return data

    def read(self, url: str) -> str:
        data = self.get(url)
        if data.startswith(b"%PDF") or url.lower().split("?", 1)[0].endswith(".pdf"):
            return _pdf_text(data)
        text = data.decode("utf-8", "replace")
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", "\n", text)
        return unescape(text)


def _pdf_text(data: bytes) -> str:
    import pymupdf

    document = pymupdf.open(stream=data, filetype="pdf")
    return "\n".join(page.get_text() for page in document)


def _public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _rank(url: str, query: str) -> int:
    lowered = url.lower()
    score = 0
    if "spec" in lowered:
        score += 3
    if lowered.split("?", 1)[0].endswith(".pdf"):
        score += 2
    parts = [part for part in query.split() if part.lower() != "specifications"]
    model = parts[-1] if parts else ""
    if model and model.lower() in lowered:
        score += 2
    return score


def _is_value(line: str) -> bool:
    if line.lower() in _WORD_VALUES:
        return True
    if _is_header(line):
        return False
    return bool(re.search(r"\d", line)) and len(line) <= 48


def _is_header(line: str) -> bool:
    letters = re.sub(r"[^A-Za-z]", "", line)
    return bool(letters) and line == line.upper() and not re.search(r"\d", line) and len(line) <= 40


def _prefer(rows: list[tuple[str, str]], family: str = "") -> list[tuple[str, str]]:
    priority = prefer_labels(family)

    def score(label: str) -> int:
        lowered = label.lower()
        for index, word in enumerate(priority):
            if word in lowered:
                return index
        return len(priority)

    ranked = sorted(enumerate(rows), key=lambda item: (score(item[1][0]), item[0]))
    return [row for _, row in ranked]


def _usable_sheet(rows: list[tuple[str, str]], family: str, allowed: tuple[str, ...]) -> bool:
    if family in {"hdd", "trencher"}:
        keys = {field_for_label(label, allowed) for label, _value in rows}
        if family == "hdd":
            return bool(keys & {"pullback_force", "thrust_force", "max_spindle_torque"})
        return bool(keys & {"trench_depth", "trench_width", "saw_depth", "plow_depth"})
    return len(rows) >= 4


def _skip(line: str) -> bool:
    lowered = line.lower()
    return lowered.startswith("specifications are") or lowered in {"u.s.", "metric", "us", "u.s"}
