/* Agent profile page — conversations list with inline message viewer + activity feed. */

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

function formatAbsolute(iso) {
  const d = toUTCDate(iso);
  if (!d) return "";
  return d.toLocaleString();
}

function agentProfile(agentId) {
  return {
    agentId,
    conversations: [],
    activity: [],
    selectedConvId: null,
    messages: [],
    loadingMessages: false,
    error: null,

    async init() {
      try {
        const [convRes, actRes] = await Promise.all([
          fetch(`/api/agents/${this.agentId}/conversations`),
          fetch(`/api/agents/${this.agentId}/activity?limit=30`),
        ]);
        if (!convRes.ok) throw new Error(`conversations: HTTP ${convRes.status}`);
        if (!actRes.ok) throw new Error(`activity: HTTP ${actRes.status}`);
        this.conversations = await convRes.json();
        this.activity = await actRes.json();

        if (this.conversations.length > 0) {
          this.selectConversation(this.conversations[0].id);
        }
      } catch (e) {
        this.error = `Couldn't load profile: ${e.message}`;
      }
    },

    async selectConversation(convId) {
      this.selectedConvId = convId;
      this.loadingMessages = true;
      this.messages = [];
      try {
        const res = await fetch(`/api/conversations/${convId}/messages`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        this.messages = await res.json();
      } catch (e) {
        this.error = `Couldn't load messages: ${e.message}`;
      } finally {
        this.loadingMessages = false;
      }
    },

    relativeTime,
    formatAbsolute,
  };
}
