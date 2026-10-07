"""One payload for the split-pane desk: units, buyers, and ranked matches."""

from __future__ import annotations

from crm.leads import get_lead, iter_leads, summarize_lead
from crm.match import rank_all, rank_buyers, rank_machines
from crm.store import get_draft, iter_drafts, summarize_draft


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
