/* OneDrive shared CSV — live table with refresh + auto-refresh. */

function onedrivePage() {
  return {
    configured: false,
    loading: false,
    error: null,
    rows: [],
    columns: [],
    rowCount: 0,
    search: "",
    autoRefresh: false,
    autoTimer: null,
    lastRefreshed: null,

    get filteredRows() {
      if (!this.search.trim()) return this.rows;
      const q = this.search.toLowerCase();
      return this.rows.filter((r) =>
        this.columns.some((c) => String(r[c] ?? "").toLowerCase().includes(q))
      );
    },

    async init() {
      try {
        const s = await fetch("/api/onedrive/status").then((r) => r.json());
        this.configured = s.configured;
        if (this.configured) await this.refresh();
      } catch (e) {
        this.error = `Init failed: ${e.message}`;
      }
    },

    async refresh() {
      if (!this.configured) return;
      this.loading = true;
      this.error = null;
      try {
        const res = await fetch("/api/onedrive/refresh", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        const data = await res.json();
        if (!data.ok) throw new Error(data.error || "Download failed");
        this.rows = data.rows;
        this.columns = data.columns;
        this.rowCount = data.row_count;
        this.lastRefreshed = new Date().toLocaleTimeString("en-GB");
      } catch (e) {
        this.error = `Refresh failed: ${e.message}`;
      } finally {
        this.loading = false;
      }
    },

    toggleAuto() {
      if (this.autoRefresh) {
        this.autoTimer = setInterval(() => this.refresh(), 30000);
      } else if (this.autoTimer) {
        clearInterval(this.autoTimer);
        this.autoTimer = null;
      }
    },
  };
}
