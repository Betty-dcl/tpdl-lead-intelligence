/* Performance dashboard */

const CHART_COLORS = [
  "#094752", "#34D591", "#6366f1", "#f59e0b",
  "#10b981", "#ec4899", "#0ea5e9", "#d946ef",
];

function relativeTime(iso) {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 60)    return "just now";
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function performancePage() {
  return {
    loading: true,
    error: null,
    summary: {},
    agentStats: [],
    actions: [],
    timeline: null,
    subjects: [],
    contentTypes: [],
    chartColors: CHART_COLORS,
    timelineChart: null,
    contentChart: null,

    get maxOutput() {
      return Math.max(...this.agentStats.map(a => a.tasks + a.messages), 1);
    },
    get totalActions() {
      return this.actions.reduce((s, r) => s + r.count, 0);
    },

    async init() {
      this.loading = true;
      this.error = null;
      try {
        const [summary, agentStats, actions, timeline, subjects, contentTypes] =
          await Promise.all([
            fetch("/api/performance/summary").then(r => r.json()),
            fetch("/api/performance/by-agent").then(r => r.json()),
            fetch("/api/performance/actions").then(r => r.json()),
            fetch("/api/performance/timeline").then(r => r.json()),
            fetch("/api/performance/subjects").then(r => r.json()),
            fetch("/api/performance/content-types").then(r => r.json()),
          ]);
        this.summary      = summary;
        this.agentStats   = agentStats;
        this.actions      = actions;
        this.timeline     = timeline;
        this.subjects     = subjects;
        this.contentTypes = contentTypes;
        this.$nextTick(() => {
          this.renderTimelineChart();
          this.renderContentChart();
        });
      } catch (e) {
        this.error = `Failed to load analytics: ${e.message}`;
      } finally {
        this.loading = false;
      }
    },

    renderTimelineChart() {
      const canvas = document.getElementById("timeline-chart");
      if (!canvas || !this.timeline || typeof Chart === "undefined") return;
      if (this.timelineChart) this.timelineChart.destroy();
      // Compact date labels
      const labels = this.timeline.labels.map(d => {
        const dt = new Date(d + "T00:00:00Z");
        return dt.toLocaleDateString("en-GB", { month: "short", day: "numeric" });
      });
      this.timelineChart = new Chart(canvas, {
        type: "bar",
        data: {
          labels,
          datasets: [
            {
              label: "All activity",
              data: this.timeline.all,
              backgroundColor: "rgba(9,71,82,0.18)",
              borderColor: "#094752",
              borderWidth: 1.5,
              borderRadius: 3,
            },
            {
              label: "Marketing",
              data: this.timeline.marketing,
              backgroundColor: "rgba(52,213,145,0.5)",
              borderColor: "#34D591",
              borderWidth: 1.5,
              borderRadius: 3,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: "top", labels: { boxWidth: 12, font: { size: 11 } } },
            tooltip: { mode: "index", intersect: false },
          },
          scales: {
            x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 10 } } },
            y: { beginAtZero: true, grid: { color: "rgba(0,0,0,0.05)" }, ticks: { stepSize: 1 } },
          },
        },
      });
    },

    renderContentChart() {
      const canvas = document.getElementById("content-chart");
      if (!canvas || !this.contentTypes || typeof Chart === "undefined") return;
      if (this.contentChart) this.contentChart.destroy();
      const filtered = this.contentTypes.filter(ct => ct.count > 0);
      if (filtered.length === 0) return;
      this.contentChart = new Chart(canvas, {
        type: "doughnut",
        data: {
          labels: filtered.map(ct => ct.label),
          datasets: [{
            data: filtered.map(ct => ct.count),
            backgroundColor: CHART_COLORS.slice(0, filtered.length),
            borderWidth: 2,
            borderColor: "#fafaf8",
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed}` } },
          },
          cutout: "68%",
        },
      });
    },

    relativeTime,
  };
}
