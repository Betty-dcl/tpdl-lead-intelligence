/* Global auth store + small badge component.
   Fetches /api/me once on load; exposes Alpine.store('me') with the user (or null). */

function _setupMeStore() {
  Alpine.store("me", {
    user: null,
    authGate: false,  // when false, login screen is hidden — public-demo mode
    loaded: false,
    async load() {
      try {
        const res = await fetch("/api/me");
        const data = await res.json();
        this.authGate = !!data.auth_gate;
        this.user = data.authenticated ? data : null;
      } catch (e) {
        console.error("Failed to fetch /api/me", e);
        this.user = null;
      }
      this.loaded = true;
    },
    async logout() {
      try { await fetch("/api/logout", { method: "POST" }); } catch (_) {}
      this.user = null;
      location.href = "/login";
    },
  });
  Alpine.store("me").load();
}

// Handle both timings: alpine:init has fired already OR is yet to fire.
if (window.Alpine && Alpine.store) {
  _setupMeStore();
} else {
  document.addEventListener("alpine:init", _setupMeStore);
}

/* x-data factory used by the header badge in base.html */
function userBadge() {
  return {
    get me() { return Alpine.store("me")?.user || null; },
    logout() { Alpine.store("me")?.logout(); },
    load() { /* triggered by x-init; the store already self-loads */ },
  };
}
