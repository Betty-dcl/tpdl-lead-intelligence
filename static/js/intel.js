/* Market Intel — backed by the real 492-row CSV via /api/intel/*. */

const SIGNAL_COLORS = {
  leadership_change:  "#6366f1",   // indigo
  hiring:             "#10B981",   // emerald
  ma_expansion:       "#8B5CF6",   // violet
  pe_event:           "#0EA5E9",   // cyan
  digital_initiative: "#f97316",   // orange
  org_restructuring:  "#d946ef",   // fuchsia
};

const SIGNAL_LABELS = {
  leadership_change:  "Leadership change",
  hiring:             "Hiring",
  ma_expansion:       "M&A / Expansion",
  pe_event:           "PE event",
  digital_initiative: "Digital initiative",
  org_restructuring:  "Org restructuring",
};

// Specialist agent IDs (will hook to drawers in Phase B once they exist).
// Roster v3: deep research + scoring is Hugo; interpretation/trends is Maya.
const SIGNAL_SPECIALIST = {
  leadership_change:  "hugo",
  hiring:             "maya",
  ma_expansion:       "hugo",
  pe_event:           "hugo",
  digital_initiative: "hugo",
  org_restructuring:  "maya",
};

const CONFIDENCE_STYLE = {
  high:   { bg: "#dcf7e7", color: "#0a3a26" },
  medium: { bg: "#fef3c7", color: "#854d0e" },
  low:    { bg: "#f3f3ef", color: "#5c5c5c" },
};

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "numeric" });
}

/* Parse the flat tech_stack_summary string into 3 chunks.
   Format from CSV: "CRM: Salesforce | Marketing automation: none detected | Analytics: GA4 | Advertising: none detected" */
function parseTechStack(s) {
  if (!s) return { crm: "—", marketing_automation: "—", analytics: "—", advertising: "—" };
  const out = { crm: "—", marketing_automation: "—", analytics: "—", advertising: "—" };
  s.split("|").forEach(part => {
    const [k, ...rest] = part.split(":");
    if (!k || rest.length === 0) return;
    const key = k.trim().toLowerCase();
    const val = rest.join(":").trim();
    if (key.startsWith("crm")) out.crm = val;
    else if (key.startsWith("marketing")) out.marketing_automation = val;
    else if (key.startsWith("analytics")) out.analytics = val;
    else if (key.startsWith("advertising")) out.advertising = val;
  });
  return out;
}

const STATUS_LABELS = {
  new:                "New",
  in_review:          "In review",
  outreach_drafted:   "Outreach drafted",
  sent:               "Sent",
  replied:            "Replied",
  won:                "Won",
  lost:               "Lost",
};
const STATUS_STYLE = {
  new:              { bg: "#f3f3ef", color: "#5c5c5c" },
  in_review:        { bg: "#fef3c7", color: "#854d0e" },
  outreach_drafted: { bg: "#e0e7ff", color: "#3730a3" },
  sent:             { bg: "#dbeafe", color: "#1e40af" },
  replied:          { bg: "#dcf7e7", color: "#0a3a26" },
  won:              { bg: "#34D591", color: "#0a3a26" },
  lost:             { bg: "#fee2e2", color: "#7f1d1d" },
};
const ACTION_VERB = {
  claimed:          "claimed",
  released:         "released",
  status_changed:   "moved",
  commented:        "commented on",
  generated_brief:  "briefed",
};

function intelPage() {
  return {
    companies: [],
    signals: [],
    stats: null,
    run: null,
    activity: [],
    workspaces: {}, // company_name → { assignment, status, comments, loading }
    briefs: {},     // company_name → { agent_id → brief | null }, plus _loading: bool, _generating: Set<agent_id>
    commentDrafts: {}, // company_name → string (input buffer)
    filters: {
      sector_bucket: "",
      signal_type: "",
      geo_region: "",
      outreach_eligible: false,
      review_flag: false,
      vintage: "",          // "" all · exact scan label ("May 25" / "Jul 23"…)
    },
    showICP: false,
    topN: 0,                 // 0 = show all; otherwise 10/20/35/50/200
    sortKey: "assessed_score",
    sortDesc: true,
    expandedRow: null,
    runs: [],                // every scan date, oldest → newest (from /api/intel/runs)
    // "Frise" — bank-statement style period picker. Pick a From run and a To run;
    // the table narrows to the To run and the period-Δ column shows To − From.
    // Empty by default → period-Δ shows "—" and the story rests on the May column.
    period: { from: "", to: "", newOnly: false },
    periodData: {},          // company → { from_score, to_score, delta, status }
    periodSummary: null,
    periodMeta: null,
    periodLoading: false,
    loading: true,
    error: null,

    async init() {
      this.loading = true;
      try {
        const [companies, signals, stats, run, activity, runs] = await Promise.all([
          fetch("/api/intel/companies?limit=2000").then(r => r.json()),
          fetch("/api/intel/signals?limit=30").then(r => r.json()),
          fetch("/api/intel/stats").then(r => r.json()),
          fetch("/api/intel/run").then(r => r.json()).catch(() => null),
          fetch("/api/team/activity?limit=15").then(r => r.json()).catch(() => []),
          fetch("/api/intel/runs").then(r => r.json()).catch(() => ({ runs: [] })),
        ]);
        this.companies = companies;
        this.signals = signals;
        this.stats = stats;
        this.run = run;
        this.activity = activity;
        this.runs = runs.runs || [];
      } catch (e) {
        this.error = `Couldn't load market intel: ${e.message}`;
      } finally {
        this.loading = false;
      }
    },

    /* ---- Frise: bank-statement style run period picker ---- */

    // Short, friendly label for a run date: "May 25" / "Jul 23".
    shortRunDate(iso) {
      if (!iso) return "—";
      const d = new Date(iso + "T00:00:00");
      return d.toLocaleDateString("en-GB", { month: "short", day: "numeric" });
    },
    // Label for a run date, matching the row badges. Neotek May is the base.
    runLabelFor(day) {
      const r = this.runs.find(x => x.run_id === day);
      if (!r) return this.shortRunDate(day);
      return this.shortRunDate(r.run_date) + (r.is_neotek ? " · base" : "");
    },
    // Both ends chosen and different → a real period is selected.
    get periodOn() {
      return !!(this.period.from && this.period.to && this.period.from !== this.period.to);
    },
    async loadPeriod() {
      if (!this.periodOn) {
        this.periodData = {}; this.periodSummary = null; this.periodMeta = null;
        return;
      }
      this.periodLoading = true;
      try {
        const url = `/api/intel/compare?from_run=${encodeURIComponent(this.period.from)}&to_run=${encodeURIComponent(this.period.to)}`;
        const d = await fetch(url).then(r => r.json());
        const map = {};
        (d.companies || []).forEach(c => { map[c.company] = c; });
        this.periodData = map;
        this.periodSummary = d.summary;
        this.periodMeta = { from: d.from, to: d.to };
      } catch (e) {
        console.error("period load failed:", e);
        this.periodData = {}; this.periodSummary = null;
      } finally {
        this.periodLoading = false;
      }
    },
    clearPeriod() {
      this.period = { from: "", to: "", newOnly: false };
      this.periodData = {}; this.periodSummary = null; this.periodMeta = null;
      if (this.sortKey === "period_delta") this.sortKey = "assessed_score";
    },

    /* ---- Filtering / sorting ---- */

    get filteredCompanies() {
      const f = this.filters;
      const sectorOK = (c) => !f.sector_bucket || c.sector_bucket === f.sector_bucket;
      const signalOK = (c) => !f.signal_type || c.signals.some(s => s.category === f.signal_type);
      const geoOK    = (c) => !f.geo_region || c.geo_region === f.geo_region;
      const eligibleOK = (c) => !f.outreach_eligible || c.outreach_eligible;
      const reviewOK   = (c) => !f.review_flag       || c.review_flag;
      const icpOK      = (c) => this.showICP || !c.icp_flag;
      // Run filter matches the EXACT scan (run_label: "May 25" / "Jul 17" / "Jul 23").
      const vintageOK  = (c) => !f.vintage || c.run_label === f.vintage;
      // With a frise selected, narrow to the "To" run, and (optionally) only the
      // companies that are new in that run vs the "From" run.
      const periodOK   = (c) => {
        if (!this.periodOn) return true;
        const e = this.periodData[c.name];
        if (!e || e.to_score == null) return false;     // not in the To run
        if (this.period.newOnly && e.status !== "new") return false;
        return true;
      };
      const rows = this.companies.filter(c =>
        sectorOK(c) && signalOK(c) && geoOK(c) && eligibleOK(c) &&
        reviewOK(c) && icpOK(c) && vintageOK(c) && periodOK(c));
      const dir = this.sortDesc ? -1 : 1;
      const key = this.sortKey;
      const val = (c) => {
        if (key === "period_delta") { const v = this.periodDelta(c); return typeof v === "number" ? v : -999; }
        if (key === "may_delta")    { const v = this.mayDelta(c);    return typeof v === "number" ? v : -999; }
        return c[key];
      };
      return [...rows].sort((a, b) => {
        const av = val(a), bv = val(b);
        if (av === bv) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        return av > bv ? dir : -dir;
      });
    },

    // Top-N slice of the sorted list (0 = all). This is what the table renders,
    // and the rank number shown is the position in THIS list.
    get displayedCompanies() {
      const rows = this.filteredCompanies;
      return this.topN > 0 ? rows.slice(0, this.topN) : rows;
    },

    setSort(key) {
      if (this.sortKey === key) this.sortDesc = !this.sortDesc;
      else { this.sortKey = key; this.sortDesc = true; }
    },

    setTopN(n) { this.topN = (this.topN === n) ? 0 : n; },

    distinctRegions() {
      const order = ["CH", "ES", "USA", "Middle East", "Europe", "APAC", "Other"];
      const present = new Set(this.companies.map(c => c.geo_region).filter(Boolean));
      return order.filter(r => present.has(r));
    },
    regionLabel(r) {
      return { CH: "Switzerland", ES: "Spain", USA: "USA",
               "Middle East": "Middle East", Europe: "Europe (rest)",
               APAC: "APAC", Other: "Unknown" }[r] || r;
    },

    resetFilters() {
      this.filters = { sector_bucket: "", signal_type: "", geo_region: "",
                       outreach_eligible: false, review_flag: false,
                       vintage: "" };
      this.showICP = false;
      this.topN = 0;
      this.clearPeriod();
    },

    /* ---- Freshness (the universe mixes vintages: latest run vs older stock) ---- */

    _day(iso) { return iso ? String(iso).slice(0, 10) : null; },   // YYYY-MM-DD

    // The most recent run date across the universe = "fresh".
    get latestRunDay() {
      if (this.stats?.pipeline?.last_run) return this._day(this.stats.pipeline.last_run);
      const days = this.companies.map(c => this._day(c.run_date)).filter(Boolean).sort();
      return days.length ? days[days.length - 1] : null;
    },
    isFresh(c) { return !!c.run_date && this._day(c.run_date) === this.latestRunDay; },
    freshLabel(c) {
      if (!c.run_date) return "no date";
      // Exact scan date the row was scored in — "May 25" / "Jul 17" / "Jul 23".
      // Run-specific so "Jul" is never ambiguous once there are several July runs.
      return c.run_label || (this.isFresh(c) ? "latest run" : "older run");
    },
    get freshCount() { return this.companies.filter(c => this.isFresh(c)).length; },

    // Distinct scan dates present, newest first, with a count — drives the Run
    // filter dropdown dynamically (grows on its own as new runs are imported).
    get runOptions() {
      const by = {};
      for (const c of this.companies) {
        const label = c.run_label, day = this._day(c.run_date);
        if (!label || !day) continue;
        (by[day] ||= { day, label, count: 0 }).count++;
      }
      return Object.values(by).sort((a, b) => b.day.localeCompare(a.day));
    },

    // Accurate one-line descriptor of what the latest run contained, instead of
    // a hardcoded "CH + ES Lunch set" that goes stale run to run.
    runComposition(run) {
      const total = run.companies || 0;
      const fresh = run.net_new_scored || 0;
      const back  = total - fresh;
      if (fresh >= total) return `${total} new to our database`;
      if (fresh === 0)    return "re-scored existing companies";
      return `${fresh} new + ${back} re-scored`;
    },

    distinctBuckets() {
      return [...new Set(this.companies.map(c => c.sector_bucket).filter(Boolean))].sort();
    },

    /* ---- Visual helpers ---- */

    signalColor(t)    { return SIGNAL_COLORS[t] || "#5c5c5c"; },
    signalLabel(t)    { return SIGNAL_LABELS[t] || t; },
    confidenceStyle(c){ return CONFIDENCE_STYLE[c] || CONFIDENCE_STYLE.low; },

    scoreClass(score) {
      if (score >= 8) return { bg: "#34D591", color: "#0a3a26" };
      if (score >= 5) return { bg: "#fef3c7", color: "#854d0e" };
      if (score === 0) return { bg: "#f3f3ef", color: "#8a8a8a" };
      return { bg: "#fee2e2", color: "#7f1d1d" };
    },

    /* ---- Δ period column (the frise) ---- */
    // "off" (no frise) | "absent" (not in To run) | "new" (only in To) | number
    periodDelta(c) {
      if (!this.periodOn) return "off";
      const e = this.periodData[c.name];
      if (!e || e.to_score == null) return "absent";
      if (e.from_score == null)     return "new";
      return e.delta;
    },
    periodText(c) {
      const v = this.periodDelta(c);
      if (v === "off" || v === "absent") return "—";
      if (v === "new") return "new";
      if (v === 0)     return "±0";
      return (v > 0 ? "▲ +" : "▼ ") + Math.abs(v).toFixed(1);
    },
    periodStyle(c) {
      const v = this.periodDelta(c);
      if (v === "new") return "background:#e0e7ff;color:#3730a3";
      if (v === "off" || v === "absent") return "background:transparent;color:#8a8a8a";
      if (v === 0)     return "background:#f3f3ef;color:#5c5c5c";
      return v > 0 ? "background:#dcf7e7;color:#0a3a26" : "background:#fee2e2;color:#7f1d1d";
    },
    periodTitle(c) {
      if (!this.periodOn) return "Pick two runs above to compare them (like a bank statement)";
      const v = this.periodDelta(c);
      if (v === "absent") return "Not scored in the " + this.runLabelFor(this.period.to) + " run";
      if (v === "new")    return "New in " + this.runLabelFor(this.period.to) + " — wasn't in " + this.runLabelFor(this.period.from);
      const e = this.periodData[c.name];
      return `${this.runLabelFor(this.period.from)}: ${e.from_score.toFixed(1)}  →  ${this.runLabelFor(this.period.to)}: ${e.to_score.toFixed(1)}`;
    },

    /* ---- Δ vs May column (the base of the base — Neotek) — always shown ---- */
    // "new" (never in May) | "base" (this IS its May row) | number
    mayDelta(c) {
      if (c.neotek_score == null) return "new";
      if (c.delta == null)        return "base";
      return c.delta;
    },
    mayText(c) {
      const v = this.mayDelta(c);
      if (v === "new")  return "new";
      if (v === "base") return "—";
      if (v === 0)      return "±0";
      return (v > 0 ? "▲ +" : "▼ ") + Math.abs(v).toFixed(1);
    },
    mayStyle(c) {
      const v = this.mayDelta(c);
      if (v === "new")  return "background:#e0e7ff;color:#3730a3";
      if (v === "base") return "background:transparent;color:#8a8a8a";
      if (v === 0)      return "background:#f3f3ef;color:#5c5c5c";
      return v > 0 ? "background:#dcf7e7;color:#0a3a26" : "background:#fee2e2;color:#7f1d1d";
    },
    mayTitle(c) {
      const v = this.mayDelta(c);
      if (v === "new")  return "Net-new — not in the Neotek May base";
      if (v === "base") return "This is its Neotek May score (the base) — not re-scored since";
      return `Neotek May: ${c.neotek_score.toFixed(1)}  →  now: ${c.assessed_score.toFixed(1)}`;
    },

    // Left accent — reflects the chosen frise if one is set, otherwise movement
    // since the May base. Green up / red down / grey flat / indigo new.
    reappearedBorder(c) {
      const v = this.periodOn ? this.periodDelta(c) : this.mayDelta(c);
      if (v === "new") return "3px solid #6366f1";
      if (v === "off" || v === "absent" || v === "base") return "3px solid transparent";
      if (typeof v === "number") {
        if (v > 0) return "3px solid #34D591";
        if (v < 0) return "3px solid #ef4444";
        return "3px solid #94a3b8";
      }
      return "3px solid transparent";
    },
    companyUrl(c) { return `/intel/company?c=${encodeURIComponent(c.name)}`; },

    parseTechStack,

    /* Deep-link to the specialist whose signal matches.
       Specialists land in Phase B — for now this opens a drawer if the agent
       exists, otherwise falls back to Alex. */
    specialistFor(signalCategory) {
      return SIGNAL_SPECIALIST[signalCategory] || "manager";
    },

    briefBySpecialistUrl(company, signalCategory) {
      const aid = this.specialistFor(signalCategory);
      const prefill = encodeURIComponent(`/generate ${company.name}`);
      return `/?drawer=${aid}&prefill=${prefill}`;
    },

    /* ---- Collaborative workspace ---- */

    statusLabel(s)  { return STATUS_LABELS[s] || s; },
    statusStyle(s)  { return STATUS_STYLE[s]  || STATUS_STYLE.new; },
    actionVerb(a)   { return ACTION_VERB[a]   || a; },
    relativeTime(iso) {
      if (!iso) return "";
      const d = new Date(iso);
      const diff = (Date.now() - d.getTime()) / 1000;
      if (diff < 5)     return "just now";
      if (diff < 60)    return `${Math.floor(diff)}s ago`;
      if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
      return `${Math.floor(diff / 86400)}d ago`;
    },

    workspace(companyName) {
      return this.workspaces[companyName] || {
        loading: true, assignment: null, status: null, comments: [],
      };
    },

    async loadWorkspace(companyName) {
      // Only fetch once per row expansion (cache until manual refresh).
      if (this.workspaces[companyName] && !this.workspaces[companyName].loading) {
        // Still kick off the briefs fetch if not already cached.
        if (!this.briefs[companyName]) this.loadBriefs(companyName);
        return;
      }
      this.workspaces[companyName] = { loading: true, assignment: null, status: null, comments: [] };
      this.loadBriefs(companyName);
      try {
        const url = `/api/companies/${encodeURIComponent(companyName)}/workspace`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        this.workspaces[companyName] = {
          loading: false,
          assignment: data.assignment,
          status: data.status,
          comments: data.comments,
        };
      } catch (e) {
        console.error("workspace load failed:", e);
        this.workspaces[companyName] = { loading: false, assignment: {user:null}, status: {value:"new"}, comments: [], error: e.message };
      }
    },

    async loadBriefs(companyName) {
      if (this.briefs[companyName] && !this.briefs[companyName]._loading) return;
      this.briefs[companyName] = { _loading: true, _generating: new Set() };
      try {
        const url = `/api/companies/${encodeURIComponent(companyName)}/briefs`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const rows = await res.json();
        // Keep only the newest brief per agent_id (rows arrive newest-first).
        const byAgent = {};
        for (const b of rows) if (!byAgent[b.agent.id]) byAgent[b.agent.id] = b;
        this.briefs[companyName] = { ...byAgent, _loading: false, _generating: new Set() };
      } catch (e) {
        console.error("briefs load failed:", e);
        this.briefs[companyName] = { _loading: false, _generating: new Set(), _error: e.message };
      }
    },

    getBrief(companyName, agentId) {
      const bucket = this.briefs[companyName];
      if (!bucket) return null;
      return bucket[agentId] || null;
    },

    isGenerating(companyName, agentId) {
      const bucket = this.briefs[companyName];
      return bucket && bucket._generating && bucket._generating.has(agentId);
    },

    async generateBrief(companyName, agentId) {
      if (!this.briefs[companyName]) this.briefs[companyName] = { _loading: false, _generating: new Set() };
      this.briefs[companyName]._generating.add(agentId);
      try {
        const url = `/api/companies/${encodeURIComponent(companyName)}/briefs/${encodeURIComponent(agentId)}/generate`;
        const res = await fetch(url, { method: "POST" });
        if (!res.ok) {
          const e = await res.json().catch(() => ({}));
          throw new Error(e.detail || `HTTP ${res.status}`);
        }
        const brief = await res.json();
        // Mutate the bucket so Alpine reacts (assignment via spread to keep new identity)
        const bucket = { ...this.briefs[companyName] };
        bucket[agentId] = brief;
        bucket._generating = new Set([...this.briefs[companyName]._generating].filter(x => x !== agentId));
        this.briefs[companyName] = bucket;
        this.refreshActivity();
      } catch (e) {
        alert(`Couldn't generate brief: ${e.message}`);
        this.briefs[companyName]._generating.delete(agentId);
      }
    },

    async regenerateBrief(companyName, agentId) {
      // Drop cache then generate fresh
      try {
        await fetch(`/api/companies/${encodeURIComponent(companyName)}/briefs/${encodeURIComponent(agentId)}`, { method: "DELETE" });
        const bucket = { ...this.briefs[companyName] };
        delete bucket[agentId];
        this.briefs[companyName] = bucket;
      } catch (_) {}
      await this.generateBrief(companyName, agentId);
    },

    async refreshActivity() {
      try {
        this.activity = await fetch("/api/team/activity?limit=15").then(r => r.json());
      } catch (_) {}
    },

    async claimCompany(companyName) {
      const r = await fetch(`/api/companies/${encodeURIComponent(companyName)}/claim`, { method: "POST" });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        alert(e.detail || `Claim failed (HTTP ${r.status})`);
        return;
      }
      delete this.workspaces[companyName];
      await this.loadWorkspace(companyName);
      this.refreshActivity();
    },

    async releaseCompany(companyName) {
      const r = await fetch(`/api/companies/${encodeURIComponent(companyName)}/release`, { method: "POST" });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        alert(e.detail || `Release failed (HTTP ${r.status})`);
        return;
      }
      delete this.workspaces[companyName];
      await this.loadWorkspace(companyName);
      this.refreshActivity();
    },

    async setStatus(companyName, value) {
      const r = await fetch(`/api/companies/${encodeURIComponent(companyName)}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: value }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        alert(e.detail || `Status change failed (HTTP ${r.status})`);
        return;
      }
      delete this.workspaces[companyName];
      await this.loadWorkspace(companyName);
      this.refreshActivity();
    },

    async postComment(companyName) {
      const text = (this.commentDrafts[companyName] || "").trim();
      if (!text) return;
      const r = await fetch(`/api/companies/${encodeURIComponent(companyName)}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text }),
      });
      if (!r.ok) {
        const e = await r.json().catch(() => ({}));
        alert(e.detail || `Comment failed (HTTP ${r.status})`);
        return;
      }
      const created = await r.json();
      if (!this.workspaces[companyName]) {
        await this.loadWorkspace(companyName);
      } else {
        this.workspaces[companyName].comments.push(created);
      }
      this.commentDrafts[companyName] = "";
      this.refreshActivity();
    },

    formatDate,
  };
}
