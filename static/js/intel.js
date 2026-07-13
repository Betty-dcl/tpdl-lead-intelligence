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
    activity: [],
    workspaces: {}, // company_name → { assignment, status, comments, loading }
    briefs: {},     // company_name → { agent_id → brief | null }, plus _loading: bool, _generating: Set<agent_id>
    commentDrafts: {}, // company_name → string (input buffer)
    filters: {
      sector_bucket: "",
      signal_type: "",
      outreach_eligible: false,
      review_flag: false,
    },
    showICP: false,
    sortKey: "assessed_score",
    sortDesc: true,
    expandedRow: null,
    charts: { score: null, signals: null, sectors: null },
    loading: true,
    error: null,

    async init() {
      this.loading = true;
      try {
        const [companies, signals, stats, activity] = await Promise.all([
          fetch("/api/intel/companies?limit=2000").then(r => r.json()),
          fetch("/api/intel/signals?limit=30").then(r => r.json()),
          fetch("/api/intel/stats").then(r => r.json()),
          fetch("/api/team/activity?limit=15").then(r => r.json()).catch(() => []),
        ]);
        this.companies = companies;
        this.signals = signals;
        this.stats = stats;
        this.activity = activity;
        this.$nextTick(() => this.renderCharts());
      } catch (e) {
        this.error = `Couldn't load market intel: ${e.message}`;
      } finally {
        this.loading = false;
      }
    },

    /* ---- Filtering / sorting ---- */

    get filteredCompanies() {
      const f = this.filters;
      const sectorOK = (c) => !f.sector_bucket || c.sector_bucket === f.sector_bucket;
      const signalOK = (c) => !f.signal_type || c.signals.some(s => s.category === f.signal_type);
      const eligibleOK = (c) => !f.outreach_eligible || c.outreach_eligible;
      const reviewOK   = (c) => !f.review_flag       || c.review_flag;
      const icpOK      = (c) => this.showICP || !c.icp_flag;
      const rows = this.companies.filter(c => sectorOK(c) && signalOK(c) && eligibleOK(c) && reviewOK(c) && icpOK(c));
      const dir = this.sortDesc ? -1 : 1;
      return [...rows].sort((a, b) => {
        const av = a[this.sortKey], bv = b[this.sortKey];
        if (av === bv) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        return av > bv ? dir : -dir;
      });
    },

    setSort(key) {
      if (this.sortKey === key) this.sortDesc = !this.sortDesc;
      else { this.sortKey = key; this.sortDesc = true; }
    },

    resetFilters() {
      this.filters = { sector_bucket: "", signal_type: "", outreach_eligible: false, review_flag: false };
      this.showICP = false;
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
