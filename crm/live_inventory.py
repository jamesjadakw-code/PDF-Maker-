"""File a Marketplace listing on the live BAM CRM as a hidden Draft.

Live and Pending are the statuses that show on bigassmotors.com. This module
never sends List Now. A person opens the unit and lists it after they verify
the photos and the write-up.
"""

from __future__ import annotations

import json
import re
from http.cookiejar import CookieJar
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from crm.marketplace import crm_draft_fields

CRM_BASE = "https://bigassmotorscrm.bigassmotors.com"


class LiveInventory:
    def __init__(self, email: str, password: str, base: str = CRM_BASE, opener=None):
        self.email = email
        self.password = password
        self.base = base.rstrip("/")
        if opener is None:
            opener = build_opener(HTTPCookieProcessor(CookieJar()))
            opener.addheaders = [(
                "User-Agent",
                "Mozilla/5.0 (compatible; BAM-CRM/1.0; +https://www.bigassmotors.com)",
            )]
        self.opener = opener

    def create_hidden_draft(self, listing: dict, brochure: dict | None = None) -> dict:
        self._login()
        page = self._get("/inventory/add_url.php")
        fields = crm_draft_fields(listing, brochure)
        photos = list(listing.get("photos") or [])
        payload = {
            "title": fields["title"],
            "year": int(fields["year"]) if fields["year"].isdigit() else fields["year"],
            "make": fields["make"],
            "model": fields["model"],
            "category": fields["category"],
            "hours": fields["hours"] or None,
            "price": fields["price"],
            "price_raw": "",
            "location": "",
            "seller": "",
            "description": fields["description"],
            "photos": photos,
            "serial": "",
            "via": [],
        }
        pairs = [
            ("_csrf", _csrf(page)),
            ("do", "create"),
            ("url", ""),
            ("x", json.dumps(payload, separators=(",", ":"))),
            ("year", fields["year"]),
            ("make", fields["make"]),
            ("model", fields["model"]),
            ("category", fields["category"]),
            ("hours", fields["hours"]),
            ("serial", ""),
            ("price", fields["price"]),
            ("location", ""),
            ("seller", ""),
            ("description", fields["description"][:4000]),
        ]
        for photo in photos:
            pairs.append(("photos[]", photo))
        html, final = self._post("/inventory/add_url.php", pairs)
        match = re.search(r"unit\.php\?id=(\d+)", final)
        if not match:
            raise ValueError("The CRM did not open a unit after create.")
        if not _is_draft(html):
            raise ValueError("The CRM did not keep this unit as a hidden Draft.")
        unit_id = match.group(1)
        return {
            "id": unit_id,
            "status": "Draft",
            "stock": _stock(html),
            "url": f"{self.base}/inventory/unit.php?id={unit_id}",
            "brochure": f"{self.base}/inventory/brochure.php?type=unit&ids={unit_id}",
            "onWebsite": False,
        }

    def _login(self) -> None:
        page = self._get("/inventory/login.php")
        html, _final = self._post("/inventory/login.php", [
            ("_csrf", _csrf(page)),
            ("next", "/inventory/add_url.php"),
            ("email", self.email),
            ("password", self.password),
        ])
        if 'name="password"' in html:
            raise ValueError("CRM login failed.")

    def _get(self, path: str) -> str:
        with self.opener.open(self.base + path, timeout=40) as response:
            return response.read().decode("utf-8", "replace")

    def _post(self, path: str, pairs: list[tuple[str, str]]) -> tuple[str, str]:
        request = Request(self.base + path, data=urlencode(pairs).encode())
        with self.opener.open(request, timeout=60) as response:
            return response.read().decode("utf-8", "replace"), response.geturl()


def _csrf(html: str) -> str:
    match = re.search(r'name="_csrf" value="([a-f0-9]+)"', html)
    if not match:
        raise ValueError("CRM page did not include a security token.")
    return match.group(1)


def _is_draft(html: str) -> bool:
    return bool(re.search(r"<option selected>\s*Draft\s*</option>", html)) or "· Draft" in html


def _stock(html: str) -> str:
    match = re.search(r"BAM-\d+", html)
    return match.group(0) if match else ""
