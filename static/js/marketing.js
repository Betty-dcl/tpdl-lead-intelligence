/* Marketing dashboard — sidebar + 7 sections + Chart.js engagement line. */

function toUTCDate(iso) {
  if (!iso) return null;
  return iso.endsWith("Z") || /[+-]\d\d:?\d\d$/.test(iso)
    ? new Date(iso)
    : new Date(iso + "Z");
}

function relativeTime(iso) {
  const d = toUTCDate(iso);
  if (!d) return "";
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 5) return "just now";
  if (diff < 60) return `${Math.floor(diff)} s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} h ago`;
  return `${Math.floor(diff / 86400)} d ago`;
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-GB", { month: "short", day: "numeric" });
}

function formatNumber(n) {
  if (n == null) return "—";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return String(n);
}

/* ── Newsletter editorial calendar — loaded from the API (DB-backed) ── */
const NEWSLETTER_SEASONS = [
  { id: "s1", label: "S1 · Who we are" },
  { id: "s2", label: "S2 · Sector insights" },
  { id: "s3", label: "S3 · Community" },
];

function buildMonthView(editions) {
  const today = new Date();
  const months = [];
  for (let i = 0; i < 6; i++) {
    const d = new Date(today.getFullYear(), today.getMonth() + i, 1);
    const label = d.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
    const ym = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    const edition = editions.find(e => e.date.startsWith(ym)) || null;
    months.push({ label, edition });
  }
  return months;
}

function marketingPage() {
  return {
    section: "linkedin",
    drafts: [],
    kpis: {},
    engagement: [],
    caseStudies: [],
    websitePages: [],
    outreach: { pipeline: [], templates: [] },
    pipeline: {
      subject: "",
      running: false,
      error: null,
      lastRun: null,
      history: [],
      formatOptions: [
        { id: "linkedin", label: "LinkedIn", icon: "💼", selected: true },
        { id: "pdf_a4",   label: "PDF A4",   icon: "📄", selected: true },
        { id: "website",  label: "Website",  icon: "🌐", selected: false },
        { id: "ppt",      label: "PPT",      icon: "📊", selected: false },
      ],
    },
    carousel: {
      subject: "",
      context: "",
      webSearch: true,
      generating: false,
      exportingPdf: {},   // { [formatId]: bool }
      results: null,
      error: null,
      formatOptions: [
        { id: "linkedin", label: "LinkedIn Carousel", icon: "💼", hint: "6-8 slides, punchy", selected: false },
        { id: "pdf_a4",   label: "PDF A4",            icon: "📄", hint: "Detailed analysis",  selected: false },
        { id: "website",  label: "Website Article",   icon: "🌐", hint: "SEO-ready article",  selected: false },
        { id: "ppt",      label: "PowerPoint",        icon: "📊", hint: "Deck outline",        selected: false },
      ],
    },
    newsletter: {
      seasons: NEWSLETTER_SEASONS,
      editions: [],
      activeSeason: "s1",
      selected: null,
      editing: null,        // edition id currently in edit mode
      editDraft: {},        // working copy of the edited fields
      saving: false,
      error: null,
      get nextEdition() {
        const today = new Date().toISOString().slice(0, 10);
        return this.editions
          .filter(e => e.date >= today && e.status !== "published")
          .sort((a, b) => a.date.localeCompare(b.date))[0] || null;
      },
      get monthView() { return buildMonthView(this.editions); },
    },
    chart: null,
    loading: true,
    error: null,
    actionFeedback: null,

    async init() {
      this.loading = true;
      this.error = null;
      try {
        const [drafts, metrics, caseStudies, websitePages, outreach] = await Promise.all([
          fetch("/api/marketing/linkedin/drafts").then((r) => r.json()),
          fetch("/api/marketing/linkedin/metrics").then((r) => r.json()),
          fetch("/api/marketing/case-studies").then((r) => r.json()),
          fetch("/api/marketing/website-pages").then((r) => r.json()),
          fetch("/api/marketing/outreach").then((r) => r.json()),
        ]);
        this.drafts = drafts;
        this.kpis = metrics.kpis;
        this.engagement = metrics.series;
        this.caseStudies = caseStudies;
        this.websitePages = websitePages;
        this.outreach = outreach;
        this.$nextTick(() => this.renderChart());
        await Promise.all([this.loadPipelineHistory(), this.loadEditions()]);
      } catch (e) {
        this.error = `Couldn't load marketing data: ${e.message}`;
      } finally {
        this.loading = false;
      }
    },

    renderChart() {
      const canvas = document.getElementById("engagement-chart");
      if (!canvas || typeof Chart === "undefined") return;
      if (this.chart) this.chart.destroy();
      this.chart = new Chart(canvas, {
        type: "line",
        data: {
          labels: this.engagement.map((p) => formatDate(p.date)),
          datasets: [
            {
              label: "Impressions",
              data: this.engagement.map((p) => p.impressions),
              borderColor: "#0A0A0A",
              backgroundColor: "rgba(52, 213, 145, 0.18)",
              tension: 0.35,
              fill: true,
              pointRadius: 3,
              pointHoverRadius: 5,
              borderWidth: 2,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { mode: "index", intersect: false },
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: { callback: (v) => formatNumber(v) },
              grid: { color: "rgba(0,0,0,0.05)" },
            },
            x: {
              grid: { display: false },
              ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 },
            },
          },
        },
      });
    },

    async approveDraft(id) {
      await this._mutateDraft(id, "approve", "approved");
    },

    async rejectDraft(id) {
      await this._mutateDraft(id, "reject", "rejected");
    },

    async _mutateDraft(id, action, pastTense) {
      try {
        const res = await fetch(`/api/marketing/linkedin/drafts/${id}/${action}`, {
          method: "POST",
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        this.drafts = this.drafts.filter((d) => d.id !== id);
        this.flash(`Draft ${pastTense}.`);
      } catch (e) {
        this.error = `Couldn't ${action} draft: ${e.message}`;
      }
    },

    async loadEditions() {
      try {
        const res = await fetch("/api/marketing/newsletter/editions");
        if (res.ok) this.newsletter.editions = await res.json();
      } catch (e) {
        this.newsletter.error = `Couldn't load editions: ${e.message}`;
      }
    },

    startEditEdition(ed) {
      this.newsletter.editing = ed.id;
      this.newsletter.editDraft = {
        title: ed.title, angle: ed.angle, date: ed.date, status: ed.status,
      };
    },

    cancelEditEdition() {
      this.newsletter.editing = null;
      this.newsletter.editDraft = {};
    },

    async saveEdition(id) {
      this.newsletter.saving = true;
      this.newsletter.error = null;
      try {
        const res = await fetch(`/api/marketing/newsletter/editions/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.newsletter.editDraft),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const updated = await res.json();
        const idx = this.newsletter.editions.findIndex(e => e.id === id);
        if (idx !== -1) this.newsletter.editions[idx] = updated;
        this.cancelEditEdition();
        this.flash("Edition saved.");
      } catch (e) {
        this.newsletter.error = `Save failed: ${e.message}`;
      } finally {
        this.newsletter.saving = false;
      }
    },

    async addEdition() {
      const today = new Date();
      const next = new Date(today.getFullYear(), today.getMonth() + 1, 15)
        .toISOString().slice(0, 10);
      try {
        const res = await fetch("/api/marketing/newsletter/editions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: "New edition — edit me",
            date: next,
            season: this.newsletter.activeSeason,
          }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const created = await res.json();
        this.newsletter.editions.push(created);
        this.newsletter.selected = created.id;
        this.startEditEdition(created);
      } catch (e) {
        this.newsletter.error = `Create failed: ${e.message}`;
      }
    },

    async deleteEdition(id) {
      if (!confirm("Delete this edition?")) return;
      try {
        const res = await fetch(`/api/marketing/newsletter/editions/${id}`, { method: "DELETE" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        this.newsletter.editions = this.newsletter.editions.filter(e => e.id !== id);
        this.cancelEditEdition();
        this.flash("Edition deleted.");
      } catch (e) {
        this.newsletter.error = `Delete failed: ${e.message}`;
      }
    },

    async runPipeline() {
      const formats = this.pipeline.formatOptions.filter(f => f.selected).map(f => f.id);
      if (formats.length === 0) return;
      this.pipeline.running = true;
      this.pipeline.error = null;
      this.pipeline.lastRun = null;
      try {
        const res = await fetch("/api/pipeline/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            subject: this.pipeline.subject.trim() || null,
            formats,
            web_search: true,
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        this.pipeline.lastRun = await res.json();
        await this.loadPipelineHistory();
      } catch(e) {
        this.pipeline.error = `Pipeline failed: ${e.message}`;
      } finally {
        this.pipeline.running = false;
      }
    },

    async loadPipelineHistory() {
      try {
        const res = await fetch("/api/pipeline/runs");
        if (res.ok) this.pipeline.history = await res.json();
      } catch(e) { /* non-blocking */ }
    },

    copyPipelineContent(formatId) {
      const r = this.pipeline.lastRun?.results?.[formatId];
      if (r?.content) navigator.clipboard.writeText(r.content).then(() => this.flash("Copied!"));
    },

    async exportPipelinePDF(formatId) {
      const r = this.pipeline.lastRun?.results?.[formatId];
      if (!r?.content) return;
      try {
        const res = await fetch("/api/marketing/carousel/export-pdf", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            subject: this.pipeline.lastRun.subject,
            content: r.content,
            format_label: r.label || formatId,
          }),
        });
        const blob = await res.blob();
        const slug = this.pipeline.lastRun.subject.slice(0, 40).replace(/[^a-z0-9]/gi, "_").toLowerCase();
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = `TPDL_pipeline_${formatId}_${slug}.pdf`;
        a.click();
        this.flash("PDF downloaded!");
      } catch(e) { this.error = `PDF failed: ${e.message}`; }
    },

    async generateCarousel() {
      const selected = this.carousel.formatOptions.filter(f => f.selected).map(f => f.id);
      if (!this.carousel.subject.trim() || selected.length === 0) return;
      this.carousel.generating = true;
      this.carousel.error = null;
      this.carousel.results = null;
      try {
        // Submit as a background job — the UI stays free while Marc & Oliver work
        const res = await fetch("/api/marketing/carousel/generate-async", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            subject: this.carousel.subject.trim(),
            formats: selected,
            context: this.carousel.context.trim() || null,
            web_search: this.carousel.webSearch,
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const { job_id } = await res.json();
        const result = await this.pollJob(job_id);
        this.carousel.results = result;
        this.flash("Generation ready!");
      } catch (e) {
        this.carousel.error = `Generation failed: ${e.message}`;
      } finally {
        this.carousel.generating = false;
      }
    },

    async pollJob(jobId, { intervalMs = 2500, timeoutMs = 360000 } = {}) {
      const deadline = Date.now() + timeoutMs;
      while (Date.now() < deadline) {
        await new Promise(r => setTimeout(r, intervalMs));
        const job = await fetch(`/api/marketing/jobs/${jobId}`).then(r => r.json());
        if (job.status === "done") return job.result;
        if (job.status === "error") throw new Error(job.error || "Job failed");
      }
      throw new Error("Timed out waiting for the generation job.");
    },

    copyContent(formatId) {
      const result = this.carousel.results?.results?.[formatId];
      if (!result?.content) return;
      navigator.clipboard.writeText(result.content).then(() => this.flash("Copied!"));
    },

    downloadContent(formatId, subject) {
      const result = this.carousel.results?.results?.[formatId];
      if (!result?.content) return;
      const slug = subject.slice(0, 40).replace(/[^a-z0-9]/gi, "_").toLowerCase();
      const filename = `TPDL_${formatId}_${slug}.txt`;
      const blob = new Blob([result.content], { type: "text/plain" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
    },

    async exportPDF(formatId) {
      const result = this.carousel.results?.results?.[formatId];
      if (!result?.content) return;
      this.carousel.exportingPdf = { ...this.carousel.exportingPdf, [formatId]: true };
      try {
        const res = await fetch("/api/marketing/carousel/export-pdf", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            subject: this.carousel.results.subject,
            content: result.content,
            format_label: result.label,
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || `HTTP ${res.status}`);
        }
        const blob = await res.blob();
        const slug = this.carousel.results.subject.slice(0, 40).replace(/[^a-z0-9]/gi, "_").toLowerCase();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `TPDL_${formatId}_${slug}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        this.flash("PDF downloaded!");
      } catch (e) {
        this.error = `PDF export failed: ${e.message}`;
      } finally {
        this.carousel.exportingPdf = { ...this.carousel.exportingPdf, [formatId]: false };
      }
    },

    flash(text) {
      this.actionFeedback = text;
      setTimeout(() => {
        if (this.actionFeedback === text) this.actionFeedback = null;
      }, 2500);
    },

    relativeTime,
    formatDate,
    formatNumber,

    scoreBadgeStyle(score) {
      if (score >= 7.5) return "background:#dcf7e7;color:#0a3a26";
      if (score >= 5)   return "background:#fef3c7;color:#854d0e";
      return "background:#fee2e2;color:#991b1b";
    },

    edMonth(iso) {
      if (!iso) return "";
      return new Date(iso).toLocaleDateString("en-GB", { month: "short" }).toUpperCase();
    },
    edDay(iso) {
      if (!iso) return "";
      return new Date(iso).getDate();
    },
    statusColor(status) {
      const map = { published: "#34D591", draft: "#f59e0b", planned: "#a5b4fc", review: "#60a5fa" };
      return map[status] || "#ccc";
    },
  };
}
