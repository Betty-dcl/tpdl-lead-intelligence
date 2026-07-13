/* Today view — one aggregated fetch, refreshed every 60s. */

function todayPage() {
  return {
    loading: true,
    error: null,
    data: {},
    timer: null,

    get dateLabel() {
      return new Date().toLocaleDateString("en-GB", {
        weekday: "long", day: "numeric", month: "long", year: "numeric",
      });
    },

    async init() {
      await this.load();
      this.timer = setInterval(() => this.load(), 60000);
    },

    async load() {
      try {
        const res = await fetch("/api/today");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        this.data = await res.json();
        this.error = null;
      } catch (e) {
        this.error = `Couldn't load your day: ${e.message}`;
      } finally {
        this.loading = false;
      }
    },

    jobBadgeStyle(status) {
      const map = {
        done:    "background:#dcf7e7;color:#0a3a26",
        running: "background:#dbeafe;color:#1e40af",
        queued:  "background:#e0e7ff;color:#3730a3",
        error:   "background:#fee2e2;color:#991b1b",
      };
      return map[status] || "background:#f3f3ef;color:#5c5c5c";
    },

    formatDate(iso) {
      if (!iso) return "";
      return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "long" });
    },

    relativeTime(iso) {
      if (!iso) return "";
      const d = new Date(iso.endsWith("Z") ? iso : iso + "Z");
      const diff = (Date.now() - d.getTime()) / 1000;
      if (diff < 60)    return "now";
      if (diff < 3600)  return `${Math.floor(diff / 60)}m`;
      if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
      return `${Math.floor(diff / 86400)}d`;
    },
  };
}
