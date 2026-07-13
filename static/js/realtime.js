/* TPDL Realtime — Supabase subscriptions for the team dashboard.
 *
 * Loads the Supabase JS client from CDN (no build step, matches the stack),
 * fetches the public config from /api/realtime/config, and exposes a tiny
 * global `TPDLRealtime` with subscribe helpers.
 *
 * If Supabase isn't configured, everything is a no-op and the app behaves
 * exactly as before (manual refresh).
 */
window.TPDLRealtime = (function () {
  let client = null;
  let ready = false;
  const pending = [];   // subscriptions queued before client is ready

  async function init() {
    try {
      const cfg = await fetch("/api/realtime/config").then((r) => r.json());
      if (!cfg.enabled) {
        console.info("[realtime] Supabase not configured — live updates off.");
        return;
      }
      // Load Supabase client from CDN once
      if (!window.supabase) {
        await loadScript("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2");
      }
      client = window.supabase.createClient(cfg.url, cfg.anon_key, {
        realtime: { params: { eventsPerSecond: 5 } },
      });
      ready = true;
      console.info("[realtime] connected to Supabase.");
      // Flush queued subscriptions
      pending.forEach((fn) => fn());
      pending.length = 0;
    } catch (e) {
      console.warn("[realtime] init failed:", e);
    }
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  /**
   * Subscribe to changes on a table.
   * @param {string} table   e.g. "content_formats"
   * @param {function} cb    called with the change payload
   * @param {string} event   "INSERT" | "UPDATE" | "DELETE" | "*"  (default "*")
   * @returns {function} unsubscribe
   */
  function subscribe(table, cb, event = "*") {
    const doSub = () => {
      const channel = client
        .channel(`tpdl:${table}`)
        .on("postgres_changes", { event, schema: "public", table }, (payload) => {
          try { cb(payload); } catch (e) { console.warn("[realtime] cb error", e); }
        })
        .subscribe();
      return channel;
    };
    if (ready) {
      return doSub();
    }
    // Queue until ready
    pending.push(doSub);
    return null;
  }

  function isReady() { return ready; }

  // Auto-init on load
  init();

  return { subscribe, isReady };
})();
