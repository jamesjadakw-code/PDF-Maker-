/* Match inbox. First screen of the desk. URL pull lands in third-party ingestion. */
const SE_STATES = new Set(["AL", "FL", "GA", "KY", "LA", "MS", "NC", "SC", "TN", "VA"]);
const INBOX_STAGES = ["Contacted", "Qualified", "Negotiation", "Won"];
const WHY = {
  model: "Exact model",
  "model-token": "Model",
  make: "Brand",
  "make-in-title": "Brand",
  budget: "In budget",
  "budget-stretch": "Near budget",
  hours: "Hours OK",
  "hours-stretch": "Hours close",
  category: "Category",
  "category-close": "Category",
  year: "Year",
  "year-close": "Year",
  keywords: "Keywords"
};

const inbox = {
  view: "inbox",
  chip: "All",
  brand: "",
  feed: "",
  q: "",
  region: "",
  score85: false,
  hoursMax: 0,
  tab: "ov",
  drawer: false
};
let inboxLead = null;
let lastPullUrl = "";

function ix(id) { return document.getElementById(id); }

function toast(text) {
  const host = ix("toasts");
  if (!host) return;
  while (host.children.length > 1) host.firstChild.remove();
  const node = document.createElement("div");
  node.className = "bam-toast";
  node.textContent = text;
  host.appendChild(node);
  requestAnimationFrame(() => node.classList.add("in"));
  setTimeout(() => node.remove(), 4600);
}

function marketplaceLink(value) {
  const raw = String(value || "").trim();
  if (/facebook\.com\/marketplace\/item\/\d+/i.test(raw)) return raw;
  return "";
}

function hoursText(value) {
  const n = parseInt(String(value || "").replace(/[^\d]/g, ""), 10);
  if (!n) return "";
  return n.toLocaleString();
}

function ago(iso) {
  const t = Date.parse(iso || "");
  if (!t) return "";
  const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return mins + " min ago";
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return hrs + "h ago";
  return Math.round(hrs / 24) + "d ago";
}

function initials(name) {
  const parts = String(name || "").trim().split(/\s+/).slice(0, 2);
  const text = parts.map(part => part[0] || "").join("").toUpperCase();
  return text || "?";
}

function badgeOf(row) {
  const title = [row.title, row.model].join(" ").toLowerCase();
  const cat = [row.category, row.model_category].join(" ").toLowerCase();
  if (/\brock\s*-?\s*saw\b|\brocksaw\b/.test(title)) return "Rock Saw";
  if (title.includes("blast")) return "Blasthole";
  if (/\bjt\d/.test(title) || /\b(hdd|directional|horizontal)\b/.test(title + " " + cat) || /\bdrill\b/.test(title)) return "HDD Drill";
  if (/\brt\d|\brtx|\btrench/.test(title) || cat.includes("trench")) return "Trencher";
  if (title.includes("backhoe") || cat.includes("backhoe")) return "Backhoe";
  if (/\bdozer\b|\bbulldozer\b/.test(title + " " + cat)) return "Dozer";
  if (title.includes("excav") || cat.includes("excav")) return "Excavator";
  return row.category || "Unit";
}

function badgeClass(name) {
  const key = String(name || "").toLowerCase();
  if (key.includes("rock")) return "rock";
  if (key.includes("hdd") || key.includes("drill")) return "hdd";
  if (key.includes("trench")) return "trencher";
  if (key.includes("blast")) return "blast";
  return "other";
}

function scoreClass(score) {
  const n = Number(score) || 0;
  if (n >= 90) return "hot";
  if (n >= 80) return "warm";
  return "cool";
}

function ring(score) {
  const n = Math.max(0, Math.min(100, Number(score) || 0));
  const c = 2 * Math.PI * 17;
  const col = n >= 90 ? "#18a957" : n >= 80 ? "#d97706" : "#9a9cab";
  return `<svg class="ix-ring" viewBox="0 0 42 42"><circle cx="21" cy="21" r="17" fill="none" stroke="#efeff3" stroke-width="4"/><circle cx="21" cy="21" r="17" fill="none" stroke="${col}" stroke-width="4" stroke-linecap="round" stroke-dasharray="${c * n / 100} ${c}" transform="rotate(-90 21 21)"/><text x="21" y="22" text-anchor="middle" font-size="12" font-weight="650" fill="#1c1d22">${n}</text></svg>`;
}

function buyersFor(id) {
  return (desk.matches || []).filter(row => row.listingId === id);
}

function topBuyers() {
  if (currentDraft && window.inboxMatches && window.inboxMatchFor === currentDraft.id) {
    return window.inboxMatches;
  }
  if (!currentDraft) return [];
  return buyersFor(currentDraft.id);
}

function leadRow(id) {
  if (inboxLead && inboxLead.id === id) return inboxLead;
  if (typeof currentLead !== "undefined" && currentLead && currentLead.id === id) return currentLead;
  return (desk.leads || []).find(row => row.id === id) || null;
}

function focusedMatch() {
  const rows = topBuyers();
  if (!rows.length) return null;
  return rows.find(row => row.leadId === pairLeadId) || rows[0];
}

function machineSummary(id) {
  return (desk.drafts || []).find(row => row.id === id) || null;
}

function placeOf(row) {
  if (row.city && row.state) return row.city + ", " + row.state;
  return row.location || row.city || row.state || "";
}

function passMachine(row) {
  const q = inbox.q.trim().toLowerCase();
  if (q && !marketplaceLink(q)) {
    const blob = [row.title, row.make, row.model, row.category, row.city, row.state, row.location, row.source_platform]
      .concat(buyersFor(row.id).map(hit => hit.leadName + " " + (hit.company || "")))
      .join(" ").toLowerCase();
    if (!blob.includes(q)) return false;
  }
  if (inbox.feed && !String(row.source_platform || "").toLowerCase().includes(inbox.feed)) return false;
  if (inbox.brand) {
    const make = (row.make + " " + row.title).toLowerCase();
    if (inbox.brand === "CAT") {
      if (!make.includes("cat") && !make.includes("caterpillar")) return false;
    } else if (!make.includes(inbox.brand.toLowerCase())) return false;
  }
  const badge = badgeOf(row);
  if (inbox.chip === "New ingestion" && row.status !== "pending_verification") return false;
  if (inbox.chip === "Trencher" && badge !== "Trencher") return false;
  if (inbox.chip === "Rock Saw" && badge !== "Rock Saw") return false;
  if (inbox.chip === "HDD Drill" && badge !== "HDD Drill") return false;
  if (inbox.chip === "Blasthole Drill" && !badge.toLowerCase().includes("blast")) return false;
  const top = (buyersFor(row.id)[0] || {}).score || 0;
  if (inbox.score85 && top < 85) return false;
  if (inbox.hoursMax) {
    const hrs = parseInt(String(row.hours || "").replace(/[^\d]/g, ""), 10);
    if (!hrs || hrs > inbox.hoursMax) return false;
  }
  const state = String(row.state || "").toUpperCase();
  if (inbox.region === "Southeast" && !SE_STATES.has(state)) return false;
  if (inbox.region === "Texas" && state !== "TX") return false;
  if ((inbox.view === "inbox" || inbox.view === "matching") && row.is_staged) return false;
  return true;
}

function passLead(row) {
  const q = inbox.q.trim().toLowerCase();
  if (q && !marketplaceLink(q)) {
    const blob = [row.name, row.company, row.phone, row.email, row.city, row.make, row.model, row.category].join(" ").toLowerCase();
    if (!blob.includes(q)) return false;
  }
  if (inbox.view === "hot") {
    const best = (desk.matches || []).filter(hit => hit.leadId === row.id).reduce((n, hit) => Math.max(n, hit.score || 0), 0);
    if (best < 90) return false;
  }
  return true;
}

function crumb() {
  const names = {
    inbox: "Match inbox",
    matching: "Deal matching center",
    leads: "Leads",
    machines: "Machines",
    pipeline: "Pipeline",
    quotes: "Quote sheets",
    hot: "Hot buyers"
  };
  const node = ix("crumb");
  if (node) node.textContent = names[inbox.view] || "Match inbox";
}

function setNav() {
  document.querySelectorAll("[data-nav]").forEach(node => {
    node.classList.toggle("on", node.getAttribute("data-nav") === inbox.view || (inbox.view === "hot" && node.getAttribute("data-nav") === "leads"));
  });
  crumb();
}

function machineRow(row) {
  const hits = buyersFor(row.id).slice(0, 3);
  const top = hits[0];
  const on = currentDraft && currentDraft.id === row.id ? " on" : "";
  const badge = badgeOf(row);
  const where = placeOf(row);
  const price = row.displayPrice || row.ask || "";
  const hrs = hoursText(row.hours);
  const meta = [price, hrs ? hrs + " hrs" : "", where].filter(Boolean).join(" · ");
  const demo = row.is_staged ? " · staged" : "";
  const avatars = hits.map(hit => `<span>${esc(initials(hit.leadName))}</span>`).join("");
  const score = top ? `<span class="ix-score ${scoreClass(top.score)}">${esc(top.score)}</span>` : "";
  const thumb = row.thumb ? `<img class="ix-thumb" alt="" src="${esc(row.thumb)}" />` : `<span class="ix-thumb ix-ph"></span>`;
  return `<div class="ix-row${on}" data-unit="${esc(row.id)}"><span class="ix-st ${row.fresh || row.status === "pending_verification" ? "fresh" : ""}"></span>${thumb}<div class="ix-mid"><div class="ix-rt">${esc(row.title || "Untitled")}</div><div class="ix-rm"><span class="ix-badge ${badgeClass(badge)}">${esc(badge)}</span><span>${esc(meta)}${esc(demo)}</span></div></div><div class="ix-end">${avatars ? `<div class="ix-av">${avatars}</div>` : ""}${score}</div></div>`;
}

function paintInboxList() {
  const host = ix("ixList");
  if (!host) return;
  const units = (desk.counts && desk.counts.units) || (desk.drafts || []).length;
  if (inbox.view === "leads" || inbox.view === "pipeline" || inbox.view === "hot") {
    paintPeople(host);
    return;
  }
  if (inbox.view === "quotes") {
    paintQuotes(host);
    return;
  }
  const rows = (desk.drafts || []).filter(passMachine);
  if (!rows.length) {
    host.innerHTML = `<p class="ix-more">Nothing in this view. Paste a Marketplace URL in the search bar to pull photos into third-party ingestion.</p>`;
    return;
  }
  if (inbox.view === "machines") {
    host.innerHTML = `<div class="ix-grp"><span>Machines · ${rows.length}</span><span>all units</span></div>` + rows.map(machineRow).join("");
    return;
  }
  if (inbox.view === "matching") {
    const ranked = rows.slice().sort((a, b) => ((buyersFor(b.id)[0] || {}).score || 0) - ((buyersFor(a.id)[0] || {}).score || 0));
    host.innerHTML = `<div class="ix-grp"><span>Live matches · ${ranked.length}</span><span>sorted by score</span></div>` + ranked.map(machineRow).join("") + `<div class="ix-more">Showing ${ranked.length} of ${units} machines</div>`;
    return;
  }
  const fresh = rows.filter(row => row.status === "pending_verification");
  const older = rows.filter(row => row.status !== "pending_verification");
  host.innerHTML = `<div class="ix-grp"><span>New third-party ingestions · ${fresh.length}</span><span>awaiting verification</span></div>`
    + (fresh.map(machineRow).join("") || `<div class="ix-more">Paste a Marketplace URL in the search bar. Photos land here for verification.</div>`)
    + `<div class="ix-grp"><span>Matched earlier · ${older.length}</span><span>sorted by recency</span></div>`
    + older.map(machineRow).join("")
    + `<div class="ix-more">Showing ${rows.length} of ${units} machines</div>`;
}

function personRow(row, extra) {
  const on = (currentLead && currentLead.id === row.id) || pairLeadId === row.id ? " on" : "";
  const want = [row.make, row.model, row.category].filter(Boolean).join(" ");
  return `<div class="ix-row${on}" data-lead="${esc(row.id)}"><span class="ix-st"></span><span class="ix-ava">${esc(initials(row.name))}</span><div class="ix-mid"><div class="ix-rt">${esc(row.name)}</div><div class="ix-rm"><span>${esc(row.company || row.phone || "")}</span><span>${esc(want)}</span></div></div><div class="ix-end"><span class="ix-score cool">${esc(extra || row.stage || "")}</span></div></div>`;
}

function paintPeople(host) {
  const rows = (desk.leads || []).filter(passLead);
  if (inbox.view === "pipeline") {
    const groups = INBOX_STAGES.map(stage => ({ stage, rows: rows.filter(row => (row.stage || "Contacted") === stage) }));
    host.innerHTML = groups.map(group => `<div class="ix-grp"><span>${esc(group.stage)} · ${group.rows.length}</span></div>` + group.rows.map(row => personRow(row, group.stage)).join("")).join("")
      || `<p class="ix-more">No buyers on the desk yet.</p>`;
    return;
  }
  host.innerHTML = `<div class="ix-grp"><span>Buyers · ${rows.length}</span><span>${inbox.view === "hot" ? "score 90+" : "CRM leads"}</span></div>`
    + (rows.map(row => personRow(row, row.packets ? row.packets + " pdf" : row.stage)).join("") || `<p class="ix-more">No buyers in this view.</p>`)
    + `<div class="ix-actions"><button type="button" class="ix-btn" id="ixNewBuyer">New buyer</button></div>`;
}

function paintQuotes(host) {
  const rows = (desk.leads || []).filter(row => row.packets);
  host.innerHTML = `<div class="ix-grp"><span>Quote sheets · ${rows.length}</span><span>packed brochures</span></div>`
    + (rows.map(row => personRow(row, row.packets + " pdf")).join("") || `<p class="ix-more">Verify a unit to pack its brochure onto hot buyers.</p>`);
}

function listingOf() {
  return (currentDraft && currentDraft.listing) || {};
}

function overviewFacts(summary) {
  const listing = listingOf();
  const ask = listing.askingPrice || listing.price || (summary && (summary.displayPrice || summary.ask)) || "";
  const hrs = hoursText(listing.hours || (summary && summary.hours));
  const loc = listing.location || (summary && placeOf(summary)) || "";
  const source = listing.source_platform || (summary && summary.source_platform) || "";
  const engine = (summary && summary.engine) || "";
  const track = (summary && summary.track) || "";
  const sheet = listing.spec_sheet || [];
  const skip = /^(year|make|model|category|hours|attachments|power|engine|track)$/i;
  const extra = sheet.filter(row => row && row.label && !skip.test(row.label) && row.value && row.value !== engine && row.value !== track).slice(0, 2);
  const cells = [
    ["Asking", ask],
    ["Hours", hrs],
    ["Location", loc],
    ["Source", source],
    ["Engine", engine],
    ["Track", track]
  ].concat(extra.map(row => [row.label, row.value])).filter(pair => pair[1]);
  return cells;
}

function whyChips(match) {
  const seen = new Set();
  return (match.reasons || []).map(reason => WHY[reason] || "").filter(label => {
    if (!label || seen.has(label)) return false;
    seen.add(label);
    return true;
  }).slice(0, 4);
}

function stageIndex(name) {
  const i = INBOX_STAGES.indexOf(name || "");
  return i < 0 ? 0 : i;
}

function paintBuyers(summary) {
  const rows = topBuyers().slice(0, 3);
  if (!rows.length) {
    return `<p class="ix-more">No ranked buyers yet. Ingest a buyer whose make, model, and category line up with this unit.</p>`;
  }
  return `<div class="ix-sec"><span>Live deal matching center · top buyers</span><span class="ix-quiet">Press 1 · 2 · 3 to focus</span></div><div class="ix-mc">${rows.map((row, index) => {
    const on = focusedMatch() && focusedMatch().leadId === row.leadId ? " on" : "";
    const lead = leadRow(row.leadId) || {};
    const stage = lead.stage || "Contacted";
    const si = stageIndex(stage);
    const chips = whyChips(row).map(label => `<span>${esc(label)}</span>`).join("");
    const where = [lead.company, lead.city, lead.state].filter(Boolean).join(" · ") || row.company || "";
    return `<div class="ix-buyer${on}" data-buyer="${index}" data-lead="${esc(row.leadId)}">${ring(row.score)}<div class="ix-n">${esc(row.leadName)}</div><div class="ix-c">${esc(where)}</div><div class="ix-c ix-wants">Wants <b>${esc(lead.model || lead.make || summary.model || "")}</b></div><div class="ix-why">${chips}</div><div class="ix-stage">${[0, 1, 2, 3].map(n => `<i class="${n <= si ? "f" : ""}"></i>`).join("")}</div><div class="ix-c">${esc(stage)}</div></div>`;
  }).join("")}</div>`;
}

function paintSelected() {
  const match = focusedMatch();
  if (!match) return "";
  const lead = leadRow(match.leadId) || {};
  const stage = lead.stage || "Contacted";
  const phone = lead.phone || match.phone || "";
  const budget = lead.budgetMax || lead.want && lead.want.budgetMax;
  const hours = lead.hoursMax || (lead.want && lead.want.hoursMax);
  const linked = lead.linked ? "Linked" : "Not linked";
  const note = lead.notes || lead.msg || "";
  return `<div class="ix-sec"><span>Selected buyer</span><span class="ix-link" data-drawer="1">Open in drawer</span></div>
    <div class="ix-cols"><div class="ix-card"><div class="ix-name">${esc(lead.name || match.leadName)}</div><div class="ix-c">${esc(lead.company || match.company || "")}${phone ? " · " + esc(phone) : ""}</div>
      <dl class="ix-props"><dt>Stage</dt><dd>${esc(stage)}</dd><dt>Budget</dt><dd>${budget ? "$" + Number(budget).toLocaleString() : "—"}</dd><dt>Max hours</dt><dd>${hours ? Number(hours).toLocaleString() : "—"}</dd><dt>Linked</dt><dd>${esc(linked)}</dd></dl>
      ${note ? `<p class="ix-quote">"${esc(note)}"</p>` : ""}</div>
      <div class="ix-card"><div class="ix-name">Activity</div><div class="ix-tl">${activityHtml(match.leadId, lead.name || match.leadName, lead.source || match.leadStatus || "")}</div></div></div>`;
}

function activityHtml(leadId, name, source) {
  const rows = (leadRow(leadId) || {}).activity || [];
  const items = rows.length ? rows.slice(0, 6) : [
    { msg: "Auto-matched by ingestion engine", at: Date.now() }
  ];
  if (!rows.length && name) {
    items.push({ msg: name + " is on the buyer list" + (source ? " via " + source : ""), at: Date.now() - 3600000 });
  }
  return items.map(item => `<div><i></i><span>${esc(item.msg)}<br><small>${esc(item.at ? new Date(item.at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "")}</small></span></div>`).join("");
}

function photoBlock(summary) {
  const listing = listingOf();
  const photos = listing.photos || [];
  const src = (summary && summary.thumb) || photos.find(item => String(item).startsWith("/api/")) || "";
  if (src) return `<img class="ix-hero" alt="" src="${esc(src)}" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'ix-hero ix-hero-empty',textContent:'Photo is saved on the unit'}))" />`;
  return `<div class="ix-hero ix-hero-empty">Photo arrives with the URL pull</div>`;
}

function paintDetail() {
  const host = ix("ixDetail");
  if (!host) return;
  if (inbox.view === "leads" || inbox.view === "pipeline" || inbox.view === "quotes" || inbox.view === "hot") {
    paintLeadDetail(host);
    return;
  }
  const summary = currentDraft ? machineSummary(currentDraft.id) : null;
  if (!currentDraft || !summary) {
    host.innerHTML = `<div class="ix-pad"><p class="ix-more">Select a unit, or paste a Marketplace URL in the search bar. The pull saves the photos and drops the unit at the top of third-party ingestion for verification.</p></div>`;
    return;
  }
  const listing = listingOf();
  const badge = badgeOf(summary);
  const fresh = summary.status === "pending_verification";
  const when = ago(summary.createdAt);
  const facts = overviewFacts(summary);
  const tabs = `<div class="ix-tabs"><span class="${inbox.tab === "ov" ? "on" : ""}" data-tab="ov">Overview</span><span class="${inbox.tab === "map" ? "on" : ""}" data-tab="map">Map · dealers &amp; service</span><span class="${inbox.tab === "activity" ? "on" : ""}" data-tab="activity">Activity</span><div class="ix-oem">${["CAT", "John Deere", "Case", "Ditch Witch", "Vermeer"].map(brand => `<span class="${inbox.brand === brand ? "on" : ""}" data-brand="${esc(brand)}"><i class="${brand.toLowerCase().includes("deere") ? "jd" : brand.toLowerCase().includes("case") ? "case" : brand.toLowerCase().includes("ditch") ? "dw" : brand.toLowerCase().includes("vermeer") ? "vm" : "cat"}"></i>${esc(brand === "John Deere" ? "John Deere" : brand === "Ditch Witch" ? "Ditch Witch" : brand)}</span>`).join("")}</div></div>`;
  let body = "";
  if (inbox.tab === "map") {
    const loc = listing.location || placeOf(summary) || "No location on this pull";
    const buyers = topBuyers().slice(0, 3).map(row => {
      const lead = leadRow(row.leadId) || {};
      const where = [lead.city, lead.state].filter(Boolean).join(", ") || lead.company || "Location not on the buyer";
      return `<div class="ix-card"><b>${esc(row.leadName)}</b><div class="ix-c">${esc(where)} · score ${esc(row.score)}</div></div>`;
    }).join("");
    body = `<div class="ix-pad"><div class="ix-card"><b>Unit location</b><div class="ix-c">${esc(loc)}</div><p class="ix-more">This is the operator desk. Location stays off the buyer-facing brochure. Dealer pins are not loaded on this desk.</p></div><div class="ix-sec"><span>Buyers</span></div>${buyers || ""}</div>`;
  } else if (inbox.tab === "activity") {
    const match = focusedMatch();
    body = `<div class="ix-pad"><div class="ix-card"><div class="ix-tl">${match ? activityHtml(match.leadId, match.leadName, "") : "<p class='ix-more'>Select a buyer.</p>"}</div></div></div>`;
  } else {
    const verify = fresh ? `<button type="button" class="ix-btn ix-pri" id="ixVerify">Verify</button>` : (summary.status === "verified" ? `<button type="button" class="ix-btn ix-pri" id="ixFile">File hidden draft</button>` : "");
    body = `<div class="ix-ins">${photoBlock(summary)}<div>${fresh ? `<div class="ix-alert"><b>NEW</b> New third-party ingestion alert · ${esc(summary.source_platform || "Marketplace")} · ${esc(when)} · auto-matched to ${topBuyers().length} buyers</div>` : ""}<div class="ix-kicker"><span class="ix-badge ${badgeClass(badge)}">${esc(badge)}</span><span>${esc(listing.itemId || summary.itemId || "")}${summary.source_platform ? " · " + esc(summary.source_platform) : ""}</span></div><h1>${esc(summary.title)}</h1><dl class="ix-facts">${facts.map(([label, value]) => `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`).join("")}</dl><div class="ix-actions">${verify}<button type="button" class="ix-btn" id="ixBrochure">Brochure</button></div></div></div>`
      + paintBuyers(summary) + `<div class="ix-pad">${paintSelected()}</div>`;
  }
  host.innerHTML = tabs + body;
  ensureFocusedLead();
}

function paintLeadDetail(host) {
  const lead = currentLead;
  if (!lead || !lead.id) {
    host.innerHTML = `<div class="ix-pad"><p class="ix-more">Select a buyer. New buyer opens the buyer form.</p><div class="ix-actions"><button type="button" class="ix-btn ix-pri" id="ixNewBuyer">New buyer</button></div></div>`;
    return;
  }
  const want = lead.want || {};
  const machines = (window.inboxLeadMatches || []).map(row => `<div class="ix-row" data-unit="${esc(row.listingId)}" data-for="${esc(lead.id)}"><div class="ix-mid"><div class="ix-rt">${esc(row.score)} · ${esc(row.unitTitle)}</div><div class="ix-rm">${esc((row.reasons || []).join(", "))}</div></div></div>`).join("");
  host.innerHTML = `<div class="ix-pad"><h1>${esc(lead.name || "Buyer")}</h1><p class="ix-c">${esc([lead.company, lead.phone, lead.email, lead.stage].filter(Boolean).join(" · "))}</p><dl class="ix-facts"><dt>Wants</dt><dd>${esc([want.make, want.model, want.category].filter(Boolean).join(" ") || "—")}</dd><dt>Budget</dt><dd>${want.budgetMax ? "$" + Number(want.budgetMax).toLocaleString() : "—"}</dd><dt>Stage</dt><dd>${esc(lead.stage || "Contacted")}</dd></dl><div class="ix-actions"><button type="button" class="ix-btn" id="ixEditBuyer">Edit buyer</button></div><div class="ix-sec"><span>Matched units</span></div>${machines || `<p class="ix-more">No ranked units yet.</p>`}<div class="ix-card" style="margin-top:14px"><div class="ix-name">Activity</div><div class="ix-tl">${activityHtml(lead.id, lead.name, lead.source || "")}</div></div></div>`;
}

function ensureFocusedLead() {
  const match = focusedMatch();
  if (!match) return;
  if (inboxLead && inboxLead.id === match.leadId) return;
  if (window.inboxLeadLoading === match.leadId) return;
  window.inboxLeadLoading = match.leadId;
  api("/api/leads/" + match.leadId).then(data => {
    window.inboxLeadLoading = "";
    inboxLead = data.lead;
    if (inbox.drawer) paintDrawer();
    paintDetail();
  }).catch(() => { window.inboxLeadLoading = ""; });
}

function paintDrawer() {
  const sheet = ix("deal");
  if (!sheet) return;
  document.body.classList.toggle("drawer-open", inbox.drawer);
  if (!inbox.drawer) return;
  const match = focusedMatch();
  const summary = currentDraft ? machineSummary(currentDraft.id) : null;
  const lead = (match && leadRow(match.leadId)) || {};
  const listing = listingOf();
  const title = (summary && summary.title) || "Deal";
  const ask = listing.askingPrice || (summary && summary.displayPrice) || "";
  const stage = lead.stage || "Contacted";
  sheet.innerHTML = `<header><b>Deal · ${esc(title)}</b><button type="button" class="ix-btn" id="ixClose">Close</button></header><div class="ix-fb">
    ${match ? `<div class="ix-alert"><b>${esc(match.score)}</b> Match score · ${esc(whyChips(match).join(" · "))}</div>` : ""}
    <div class="ix-field"><label>Buyer</label><input readonly value="${esc((lead.name || "") + (lead.company ? " · " + lead.company : ""))}" /></div>
    <div class="ix-field"><label>Stage</label><div class="ix-seg">${INBOX_STAGES.map(name => `<span class="${name === stage ? "on" : ""}" data-stage="${esc(name)}">${esc(name)}</span>`).join("")}</div></div>
    <div class="ix-field"><label>Asking</label><input readonly value="${esc(ask)}" /></div>
    <div class="ix-field"><label>Quote sheet message · SMS</label><textarea id="ixQuote" readonly>${esc(quoteText(summary, lead))}</textarea></div>
    <div class="ix-field"><label>Photos on the pull</label><div class="ix-why">${(listing.photos || []).length} saved</div></div>
  </div><div class="ix-sf"><button type="button" class="ix-btn" data-act="link">Link</button><button type="button" class="ix-btn" data-act="email">Email quote</button><button type="button" class="ix-btn ix-pri" data-act="quote">Send quote sheet</button></div>`;
}

function quoteText(summary, lead) {
  const title = (summary && summary.title) || "a unit";
  const name = (lead && lead.name) || "there";
  return name + ", this is Big Ass Motors. " + title + " lines up with what you asked for. Call or text +1-904-767-5232 and we will send the quote sheet.";
}

function paintChips() {
  document.querySelectorAll("[data-chip]").forEach(node => {
    const name = node.getAttribute("data-chip");
    const on = name === "Score" ? inbox.score85 : name === "Region" ? !!inbox.region : inbox.chip === name;
    node.classList.toggle("on", on);
    if (name === "Region") node.textContent = inbox.region ? inbox.region : "+ Region";
  });
  document.querySelectorAll("[data-saved]").forEach(node => node.classList.toggle("on", node.getAttribute("data-saved") === inbox.saved));
  document.querySelectorAll("[data-feed]").forEach(node => node.classList.toggle("on", node.getAttribute("data-feed") === inbox.feed));
  const counts = desk.counts || {};
  const leads = counts.buyers || (desk.leads || []).length;
  const machines = counts.units || (desk.drafts || []).length;
  const pipeline = (desk.leads || []).filter(row => (row.stage || "Contacted") !== "Won").length;
  const quotes = (desk.leads || []).reduce((n, row) => n + (row.packets || 0), 0);
  const set = (id, value) => { const node = ix(id); if (node) node.textContent = value; };
  set("navLeads", Number(leads).toLocaleString());
  set("navMachines", Number(machines).toLocaleString());
  set("navPipeline", Number(pipeline).toLocaleString());
  set("navQuotes", Number(quotes).toLocaleString());
  const node = ix("ixCounts");
  if (node) node.innerHTML = `<b>${(desk.matches || []).length}</b> matches · <b>${Number(leads).toLocaleString()}</b> leads · <b>${Number(machines).toLocaleString()}</b> machines`;
}

function keepSelectionVisible() {
  if (!currentDraft || inbox.view === "leads" || inbox.view === "pipeline" || inbox.view === "quotes" || inbox.view === "hot") return;
  const visible = [...document.querySelectorAll("#ixList [data-unit]")];
  if (!visible.length) return;
  if (visible.some(node => node.getAttribute("data-unit") === currentDraft.id)) return;
  go("#/unit/" + visible[0].getAttribute("data-unit"));
}

function paintInbox() {
  paintChips();
  setNav();
  paintInboxList();
  paintDetail();
  paintDrawer();
}

function inboxHome() {
  inbox.view = "inbox";
  inbox.saved = "";
  const fresh = (desk.drafts || []).find(row => row.status === "pending_verification" && !row.is_staged);
  const pick = fresh || (desk.drafts || []).find(row => !row.is_staged) || (desk.drafts || [])[0];
  if (pick && (!currentDraft || currentDraft.id !== pick.id)) {
    go("#/unit/" + pick.id);
    return;
  }
  paintInbox();
}

function openScheme(href) {
  if (!href) return;
  const link = document.createElement("a");
  link.href = href;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

async function runAct(name, stage) {
  const match = focusedMatch() || (currentLead ? { leadId: currentLead.id, leadName: currentLead.name } : null);
  const leadId = match && match.leadId;
  const listingId = currentDraft && currentDraft.id;
  if (!leadId) {
    toast("Choose a buyer first.");
    return;
  }
  if ((name === "quote" || name === "link") && !listingId) {
    toast("Choose a unit first.");
    return;
  }
  const lead = leadRow(leadId) || {};
  const who = lead.name || match.leadName || "buyer";
  const notes = {
    text: "Text sent to " + who,
    email: "Email sent to " + who,
    call: "Call logged with " + who,
    quote: "Quote sheet sent to " + who,
    link: "Linked this unit to " + who,
    stage: stage ? "Stage set to " + stage : ""
  };
  const data = await api("/api/desk/action", {
    act: name,
    listingId: listingId || "",
    leadId,
    note: notes[name] || "",
    stage: stage || ""
  });
  if (data.lead) inboxLead = data.lead;
  if (currentLead && data.lead && currentLead.id === data.lead.id) currentLead = data.lead;
  applyDesk(data);
  const phone = String((data.lead && data.lead.phone) || "").replace(/[^\d+]/g, "");
  const email = (data.lead && data.lead.email) || "";
  const title = (currentDraft && currentDraft.listing && currentDraft.listing.title) || "BAM unit";
  if (name === "text" && phone) openScheme("sms:" + phone);
  if (name === "email" && email) openScheme("mailto:" + email + "?subject=" + encodeURIComponent(title));
  if (name === "call" && phone) openScheme("tel:" + phone);
  toast(notes[name] || ((data.lead && data.lead.stage) ? "Stage set to " + data.lead.stage : "Saved"));
}

async function pullUrl(raw) {
  const url = marketplaceLink(raw);
  if (!url) {
    toast("Paste a facebook.com/marketplace item URL in the search bar.");
    return;
  }
  lastPullUrl = url;
  toast("Pulling the listing and photos…");
  try {
    const data = await api("/api/marketplace/scrape", { url });
    landed(data);
  } catch (err) {
    let message = err.message || "Could not pull that listing.";
    if (/marketplace listing|could not reach facebook|login|too large/i.test(message)) {
      message = "Facebook did not return that listing. Paste the page HTML below and pull it.";
    }
    toast(message);
    const paste = ix("pullPaste");
    if (paste) paste.hidden = false;
  }
}

async function pullHtml() {
  const html = ix("pullHtml").value.trim();
  if (!html) {
    toast("Paste the listing page HTML.");
    return;
  }
  const url = marketplaceLink(ix("inboxQ").value) || lastPullUrl || "https://www.facebook.com/marketplace/item/0/";
  toast("Reading the pasted listing…");
  try {
    const data = await api("/api/marketplace/parse", { url, html });
    ix("pullPaste").hidden = true;
    landed(data);
  } catch (err) {
    toast(err.message);
  }
}

function landed(data) {
  const box = ix("inboxQ");
  if (box) box.value = "";
  inbox.q = "";
  inbox.view = "inbox";
  inbox.chip = "All";
  applyDesk(data);
  const photos = ((data.draft.listing || {}).photos || []).length;
  toast(photos + (photos === 1 ? " photo" : " photos") + " pulled. It is at the top of third-party ingestion for verification.");
  go("#/unit/" + data.draft.id);
}

async function verifyUnit() {
  if (!currentDraft) return;
  toast("Verifying and packing the brochure…");
  try {
    const data = await api("/api/marketplace/verify", { id: currentDraft.id, brochure: currentBrochure() });
    showDraft(data.draft);
    await saveSheetPdf(data.draft);
    applyDesk(data);
    toast("Verified. Brochure packed for " + (data.packets || []).length + " hot buyer(s).");
  } catch (err) {
    toast(err.message);
  }
}

async function fileUnit() {
  if (!currentDraft) return;
  try {
    const data = await api("/api/marketplace/post", { id: currentDraft.id, brochure: currentBrochure() });
    showDraft(data.draft);
    await refreshDesk();
    toast("Filed as a hidden draft. It stays off the website.");
  } catch (err) {
    toast(err.message);
  }
}

function openBrochure() {
  document.body.classList.add("quote-open");
}

function openBuyerForm() {
  document.body.classList.add("quote-open");
  if (!currentLead || !currentLead.id) ix("newBuyer").click();
}

document.addEventListener("click", event => {
  const nav = event.target.closest("[data-nav]");
  if (nav && event.target.closest(".app")) {
    const view = nav.getAttribute("data-nav");
    inbox.saved = "";
    inbox.chip = view === "inbox" ? "All" : inbox.chip;
    inbox.view = view;
    if (view === "inbox") {
      inboxHome();
      return;
    }
    if (view === "leads" || view === "quotes" || view === "pipeline" || view === "hot") {
      const pool = (desk.leads || []).filter(row => view !== "quotes" || row.packets);
      paintInbox();
      if (pool[0]) go("#/lead/" + pool[0].id);
      return;
    }
    paintInbox();
    return;
  }
  const saved = event.target.closest("[data-saved]");
  if (saved) {
    const key = saved.getAttribute("data-saved");
    inbox.saved = inbox.saved === key ? "" : key;
    inbox.chip = "All";
    inbox.region = "";
    inbox.hoursMax = 0;
    inbox.score85 = false;
    inbox.feed = "";
    if (inbox.saved === "trench-se") { inbox.view = "inbox"; inbox.chip = "Trencher"; inbox.region = "Southeast"; }
    if (inbox.saved === "hdd-hours") { inbox.view = "inbox"; inbox.chip = "HDD Drill"; inbox.hoursMax = 2500; }
    if (inbox.saved === "rock-tx") { inbox.view = "inbox"; inbox.chip = "Rock Saw"; inbox.region = "Texas"; }
    if (inbox.saved === "hot") { inbox.view = "hot"; }
    paintInbox();
    keepSelectionVisible();
    return;
  }
  const feed = event.target.closest("[data-feed]");
  if (feed) {
    const key = feed.getAttribute("data-feed");
    inbox.feed = inbox.feed === key ? "" : key;
    inbox.view = "inbox";
    paintInbox();
    keepSelectionVisible();
    return;
  }
  const chip = event.target.closest("[data-chip]");
  if (chip) {
    const name = chip.getAttribute("data-chip");
    if (name === "Score") inbox.score85 = !inbox.score85;
    else if (name === "Region") inbox.region = inbox.region === "Southeast" ? "Texas" : inbox.region === "Texas" ? "" : "Southeast";
    else inbox.chip = name;
    paintInbox();
    keepSelectionVisible();
    return;
  }
  const brand = event.target.closest("[data-brand]");
  if (brand) {
    const name = brand.getAttribute("data-brand");
    inbox.brand = inbox.brand === name ? "" : name;
    paintInbox();
    keepSelectionVisible();
    return;
  }
  const tab = event.target.closest("[data-tab]");
  if (tab && event.target.closest("#ixDetail")) {
    inbox.tab = tab.getAttribute("data-tab");
    paintDetail();
    return;
  }
  const unit = event.target.closest("[data-unit]");
  if (unit && (event.target.closest("#ixList") || event.target.closest("#ixDetail"))) {
    const id = unit.getAttribute("data-unit");
    const forLead = unit.getAttribute("data-for") || "";
    go(forLead ? "#/unit/" + id + "/for/" + forLead : "#/unit/" + id);
    return;
  }
  const lead = event.target.closest("[data-lead]");
  if (lead && event.target.closest("#ixList")) {
    go("#/lead/" + lead.getAttribute("data-lead"));
    return;
  }
  const buyer = event.target.closest("[data-buyer]");
  if (buyer && currentDraft) {
    const rows = topBuyers();
    const row = rows[Number(buyer.getAttribute("data-buyer"))];
    if (row) go("#/unit/" + currentDraft.id + "/for/" + row.leadId);
    return;
  }
  if (event.target.closest("#ixVerify")) { verifyUnit(); return; }
  if (event.target.closest("#ixFile")) { fileUnit(); return; }
  if (event.target.closest("#ixBrochure")) { openBrochure(); return; }
  if (event.target.closest("#ixNewBuyer") || event.target.closest("#ixEditBuyer")) { openBuyerForm(); return; }
  if (event.target.closest("[data-drawer]") || event.target.closest("#ixOpenDeal")) {
    inbox.drawer = true;
    paintDrawer();
    return;
  }
  if (event.target.closest("#ixClose") || event.target.closest("[data-close]")) {
    inbox.drawer = false;
    paintDrawer();
    return;
  }
  const stage = event.target.closest("[data-stage]");
  if (stage) {
    runAct("stage", stage.getAttribute("data-stage")).catch(err => toast(err.message));
    return;
  }
  const act = event.target.closest("[data-act]");
  if (act) {
    runAct(act.getAttribute("data-act")).catch(err => toast(err.message));
  }
});

function bindInboxSearch() {
  const box = ix("inboxQ");
  if (!box) return;
  box.addEventListener("input", () => {
    inbox.q = box.value;
    paintInboxList();
    paintChips();
  });
  box.addEventListener("keydown", event => {
    if (event.key !== "Enter") return;
    if (marketplaceLink(box.value)) {
      event.preventDefault();
      pullUrl(box.value);
    }
  });
  box.addEventListener("paste", event => {
    const text = (event.clipboardData || window.clipboardData).getData("text");
    if (marketplaceLink(text)) setTimeout(() => pullUrl(text), 0);
  });
  const ingest = ix("ixIngest");
  if (ingest) ingest.addEventListener("click", () => pullUrl(box.value || lastPullUrl));
  const pasted = ix("pullHtmlBtn");
  if (pasted) pasted.addEventListener("click", pullHtml);
  const back = ix("backInbox");
  if (back) back.addEventListener("click", () => {
    document.body.classList.remove("quote-open");
    paintInbox();
  });
}

document.addEventListener("keydown", event => {
  const typing = event.target && (event.target.closest("input, textarea, select"));
  if (event.key === "/" && !typing) {
    event.preventDefault();
    ix("inboxQ").focus();
    return;
  }
  if (typing) return;
  const key = event.key.toLowerCase();
  if (key === "i") pullUrl((ix("inboxQ").value || lastPullUrl));
  if (key === "escape") { inbox.drawer = false; paintDrawer(); }
  if (key === "m") { inbox.tab = inbox.tab === "map" ? "ov" : "map"; paintDetail(); }
  if (key === "1" || key === "2" || key === "3") {
    const row = topBuyers()[Number(key) - 1];
    if (row && currentDraft) go("#/unit/" + currentDraft.id + "/for/" + row.leadId);
  }
  const acts = { t: "text", e: "email", c: "call", q: "quote", l: "link", s: "stage" };
  if (acts[key]) runAct(acts[key]).catch(err => toast(err.message));
});

window.paintInbox = paintInbox;
window.inboxHome = inboxHome;
bindInboxSearch();
if ((desk.drafts && desk.drafts.length) || (desk.leads && desk.leads.length)) {
  if (!location.hash || location.hash === "#" || location.hash === "#/") inboxHome();
  else paintInbox();
}
