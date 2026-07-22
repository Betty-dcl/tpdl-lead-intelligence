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
      fresh_only: false,
      new_only: false,
    },
    showICP: false,
    topN: 0,                 // 0 = show all; otherwise 10/20/35/50/200
    sortKey: "assessed_score",
    sortDesc: true,
    expandedRow: null,
    // Run comparison ("bank-statement" period picker)
    runs: [],
    compare: { on: false, from_run: "", to_run: "", data: {}, summary: null, meta: null, loading: false },
    charts: { score: null, signals: null, sectors: null },
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
        // Default the comparison to oldest → newest run.
        if (this.runs.length >= 2) {
          this.compare.from_run = this.runs[0].run_id;
          this.compare.to_run = this.runs[this.runs.length - 1].run_id;
        }
        this.$nextTick(() => this.renderCharts());
      } catch (e) {
        this.error = `Couldn't load market intel: ${e.message}`;
      } finally {
        this.loading = false;
      }
    },

    /* ---- Run comparison (period picker) ---- */

    runLabel(id) {
      const r = this.runs.find(x => x.run_id === id);
      return r ? r.label : id;
    },
    async loadCompare() {
      if (!this.compare.from_run || !this.compare.to_run) return;
      this.compare.loading = true;
      try {
        const url = `/api/intel/compare?from_run=${encodeURIComponent(this.compare.from_run)}&to_run=${encodeURIComponent(this.compare.to_run)}`;
        const d = await fetch(url).then(r => r.json());
        const map = {};
        (d.companies || []).forEach(c => { map[c.company] = c; });
        this.compare.data = map;
        this.compare.summary = d.summary;
        this.compare.meta = { from: d.from, to: d.to };
      } catch (e) {
        console.error("compare load failed:", e);
      } finally {
        this.compare.loading = false;
      }
    },
    toggleCompare() {
      this.compare.on = !this.compare.on;
      if (this.compare.on && !this.compare.summary) this.loadCompare();
    },
    onCompareRunChange() {
      // Re-pull whenever a picker changes (only matters while compare is on).
      this.loadCompare();
    },
    // Entry for a company in the currently-selected period (or null).
    cmp(c) { return this.compare.on ? (this.compare.data[c.name] || null) : null; },
    // Effective delta / baseline / status — period-aware.
    effDelta(c)     { const e = this.cmp(c); return this.compare.on ? (e ? e.delta : null) : c.delta; },
    effBaseline(c)  { const e = this.cmp(c); return this.compare.on ? (e ? e.from_score : null) : c.neotek_score; },
    effReappeared(c){ const e = this.cmp(c); return this.compare.on ? !!(e && e.from_score != null) : c.reappeared; },
    effStatus(c)    { const e = this.cmp(c); return e ? e.status : null; },

    /* ---- Filtering / sorting ---- */

    get filteredCompanies() {
      const f = this.filters;
      const sectorOK = (c) => !f.sector_bucket || c.sector_bucket === f.sector_bucket;
      const signalOK = (c) => !f.signal_type || c.signals.some(s => s.category === f.signal_type);
      const geoOK    = (c) => !f.geo_region || c.geo_region === f.geo_region;
      const eligibleOK = (c) => !f.outreach_eligible || c.outreach_eligible;
      const reviewOK   = (c) => !f.review_flag       || c.review_flag;
      const icpOK      = (c) => this.showICP || !c.icp_flag;
      const freshOK    = (c) => !f.fresh_only || this.isFresh(c);
      // In compare mode, only show companies present in the "to" period, and
      // (optionally) only the ones that are new in that period.
      const compareOK  = (c) => {
        if (!this.compare.on) return true;
        const e = this.compare.data[c.name];
        if (!e || e.to_score == null) return false;     // not in the later run
        if (f.new_only && e.status !== "new") return false;
        return true;
      };
      const rows = this.companies.filter(c =>
        sectorOK(c) && signalOK(c) && geoOK(c) && eligibleOK(c) &&
        reviewOK(c) && icpOK(c) && freshOK(c) && compareOK(c));
      const dir = this.sortDesc ? -1 : 1;
      const key = this.sortKey;
      const val = (c) => (key === "delta" && this.compare.on) ? this.effDelta(c) : c[key];
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
               APAC: "APAC", Other: "Other / unknown" }[r] || r;
    },

    resetFilters() {
      this.filters = { sector_bucket: "", signal_type: "", geo_region: "",
                       outreach_eligible: false, review_flag: false,
                       fresh_only: false, new_only: false };
      this.showICP = false;
      this.topN = 0;
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
      return this.isFresh(c) ? "fresh" : `${this._day(c.run_date)} · stale`;
    },
    get freshCount() { return this.companies.filter(c => this.isFresh(c)).length; },

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

    /* ---- Movement vs the Neotek May reference run ---- */
    deltaLabel(d) {
      if (d == null) return "new";
      if (d === 0) return "±0";
      return (d > 0 ? "▲ +" : "▼ ") + Number(d).toFixed(1);
    },
    deltaChipStyle(d) {
      if (d == null) return "background:#e0e7ff;color:#3730a3";        // never in Neotek
      if (d === 0)  return "background:#f3f3ef;color:#5c5c5c";
      return d > 0 ? "background:#dcf7e7;color:#0a3a26" : "background:#fee2e2;color:#7f1d1d";
    },
    // Δ column display — vintage-aware. A row still on its Neotek-May score
    // hasn't been re-scored, so it shows "—", not a fake "±0" or "new".
    deltaText(c) {
      if (this.compare.on) return this.deltaLabel(this.effDelta(c));
      if (c.vintage === "neotek_may") return "—";
      return this.deltaLabel(c.delta);
    },
    deltaStyleFor(c) {
      if (this.compare.on) return this.deltaChipStyle(this.effDelta(c));
      if (c.vintage === "neotek_may") return "background:transparent;color:#8a8a8a";
      return this.deltaChipStyle(c.delta);
    },
    deltaTitleFor(c) {
      if (this.compare.on) {
        const e = this.cmp(c);
        return (e && e.from_score != null) ? ("From " + e.from_score.toFixed(1)) : "New in this period";
      }
      if (c.vintage === "neotek_may") return "Neotek May score — not re-scored since, so there's no movement to show";
      if (c.reappeared) return "Neotek May: " + c.neotek_score.toFixed(1);
      return "Not in the Neotek run";
    },

    // Left accent that marks a company already seen in the baseline run
    // (period-aware: reflects the selected comparison when compare mode is on).
    reappearedBorder(c) {
      if (!this.effReappeared(c)) return "3px solid transparent";
      const d = this.effDelta(c);
      if (d > 0) return "3px solid #34D591";
      if (d < 0) return "3px solid #ef4444";
      return "3px solid #94a3b8";
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

    /* ---- Charts ---- */

    renderCharts() {
      this.renderScoreChart();
      this.renderSignalsChart();
      this.renderSectorsChart();
    },

    renderScoreChart() {
      const canvas = document.getElementById("score-chart");
      if (!canvas || typeof Chart === "undefined") return;
      if (this.charts.score) this.charts.score.destroy();
      this.charts.score = new Chart(canvas, {
        type: "bar",
        data: {
          labels: this.stats.score_distribution.map(b => b.label),
          datasets: [{
            data: this.stats.score_distribution.map(b => b.count),
            backgroundColor: ["#34D591", "#fef3c7", "#fee2e2", "#f3f3ef"],
            borderRadius: 4,
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.05)" } },
            x: { grid: { display: false }, ticks: { font: { size: 10 } } },
          },
        },
      });
    },

    renderSignalsChart() {
      const canvas = document.getElementById("signals-chart");
      if (!canvas || typeof Chart === "undefined") return;
      if (this.charts.signals) this.charts.signals.destroy();
      this.charts.signals = new Chart(canvas, {
        type: "bar",
        data: {
          labels: this.stats.signal_coverage.map(s => SIGNAL_LABELS[s.signal_type]),
          datasets: [{
            data: this.stats.signal_coverage.map(s => s.count),
            backgroundColor: this.stats.signal_coverage.map(s => SIGNAL_COLORS[s.signal_type]),
            borderRadius: 4,
          }],
        },
        options: {
          indexAxis: "y", responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.05)" } },
            y: { grid: { display: false }, ticks: { font: { size: 11 } } },
          },
        },
      });
    },

    renderSectorsChart() {
      const canvas = document.getElementById("sectors-chart");
      if (!canvas || typeof Chart === "undefined") return;
      if (this.charts.sectors) this.charts.sectors.destroy();
      const palette = ["#094752", "#34D591", "#F59E0B", "#8B5CF6", "#0EA5E9", "#EC4899", "#6366f1", "#94a3b8"];
      this.charts.sectors = new Chart(canvas, {
        type: "doughnut",
        data: {
          labels: this.stats.sector_distribution.map(s => s.sector),
          datasets: [{
            data: this.stats.sector_distribution.map(s => s.count),
            backgroundColor: this.stats.sector_distribution.map((_, i) => palette[i % palette.length]),
            borderWidth: 2,
            borderColor: "#fafaf8",
          }],
        },
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: {
            legend: { position: "right", labels: { font: { size: 10 }, boxWidth: 10 } },
          },
        },
      });
    },
  };
}
