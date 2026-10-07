"""One payload for the split-pane desk: units, buyers, and ranked matches."""

from __future__ import annotations

from crm.brochure_file import attach_brochure
from crm.leads import attach_packet, get_lead, iter_leads, summarize_lead
from crm.match import rank_all, rank_buyers, rank_machines
from crm.store import get_draft, iter_drafts, save_draft, summarize_draft


def snapshot(min_score: int = 45, limit: int = 40) -> dict:
    drafts = list(iter_drafts())
    leads = list(iter_leads())
    ranked = rank_all(drafts, leads, min_score=min_score, limit=10_000)
    return {
        "drafts": [summarize_draft(draft) for draft in drafts],
        "leads": [summarize_lead(lead) for lead in leads],
        "matches": ranked[:limit],
        "counts": {
            "units": len(drafts),
            "buyers": len(leads),
            "hot": sum(1 for row in ranked if row["score"] >= 70),
        },
    }


def matches_for(listing_id: str = "", lead_id: str = "") -> dict:
    drafts = list(iter_drafts())
    leads = list(iter_leads())
    if listing_id:
        draft = get_draft(listing_id)
        return {"ok": True, "kind": "listing", "id": listing_id, "matches": rank_buyers(draft, leads)}
    if lead_id:
        lead = get_lead(lead_id)
        return {"ok": True, "kind": "lead", "id": lead_id, "matches": rank_machines(lead, drafts)}
    return {"ok": True, "kind": "desk", "id": "", "matches": rank_all(drafts, leads)}


def packet_hot_matches(draft: dict, min_score: int = 70) -> list[dict]:
    """Put the unit brochure on every hot buyer. Skip pairs already packed."""
    attach_brochure(draft)
    save_draft(draft)
    pdf = (draft.get("machineCard") or {}).get("pdf") or ""
    packed: list[dict] = []
    for row in rank_buyers(draft, list(iter_leads()), limit=40):
        if row["score"] < min_score:
            continue
        lead = get_lead(row["leadId"])
        existing = [
            item for item in (lead.get("packets") or [])
            if item.get("listingId") == draft["id"]
        ]
        if existing:
            packed.append({**row, "pdf": existing[0].get("pdf") or pdf, "already": True})
            continue
        packet = {
            "listingId": draft["id"],
            "leadId": lead["id"],
            "title": row["unitTitle"],
            "score": row["score"],
            "pdf": pdf,
            "preparedAt": "",
        }
        saved = attach_packet(lead["id"], packet)
        packet["preparedAt"] = saved.get("updatedAt") or ""
        packed.append({**row, "pdf": pdf, "already": False, "packeted": True})
    return packed
