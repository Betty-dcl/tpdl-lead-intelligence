/* Open Space — shared Alpine state for the Manager chat, the team grid and the
   per-agent drawer chat. All chat state lives in $store.agents.chats so that
   closing and re-opening the drawer never loses a conversation in flight. */

const KNOWN_AGENT_IDS = ["manager", "hugo", "maya", "ines", "julie", "iris", "marc", "oliver", "vera"];
const INTEL_TEAM     = ["hugo", "maya", "ines", "julie"];
const MARKETING_TEAM = ["iris", "marc", "oliver"];
const TEAM_ORDER     = [...INTEL_TEAM, ...MARKETING_TEAM];

function emptyChat() {
  return {
    conversationId: null,
    messages: [],
    sending: false,
    error: null,
    input: "",
  };
}

/* Backend timestamps are naive UTC; treat strings without timezone as UTC. */
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

document.addEventListener("alpine:init", () => {
  Alpine.store("agents", {
    list: [],
    byId: {},
    chats: Object.fromEntries(KNOWN_AGENT_IDS.map((id) => [id, emptyChat()])),

    async load() {
      try {
        const res = await fetch("/api/agents");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        this.list = data;
        this.byId = Object.fromEntries(data.map((a) => [a.id, a]));
      } catch (e) {
        console.error("Failed to load agents:", e);
      }
    },

    get team() {
      return TEAM_ORDER.map((id) => this.byId[id]).filter(Boolean);
    },
    get intelTeam() {
      return INTEL_TEAM.map((id) => this.byId[id]).filter(Boolean);
    },
    get marketingTeam() {
      return MARKETING_TEAM.map((id) => this.byId[id]).filter(Boolean);
    },
  });

  Alpine.store("drawer", {
    open: false,
    agentId: null,
    show(id) {
      this.agentId = id;
      this.open = true;
    },
    close() {
      this.open = false;
    },
  });

  Alpine.store("agents").load().then(() => {
    // Allow other pages to deep-link into a specialist's chat via
    //   ?drawer=<id>            → open that drawer
    //   ?drawer=<id>&prefill=…  → also pre-fill the chat input
    const params = new URLSearchParams(window.location.search);
    const drawerAgent = params.get("drawer");
    if (drawerAgent && KNOWN_AGENT_IDS.includes(drawerAgent)) {
      Alpine.store("drawer").show(drawerAgent);
      const prefill = params.get("prefill");
      if (prefill) {
        const chat = Alpine.store("agents").chats[drawerAgent];
        if (chat) chat.input = prefill;
      }
    }
  });
});

async function sendMessage(agentId) {
  if (!agentId) return;
  const chat = Alpine.store("agents").chats[agentId];
  if (!chat) return;

  const text = chat.input.trim();
  if (!text || chat.sending) return;

  chat.error = null;
  chat.messages.push({ role: "user", content: text });
  chat.input = "";
  chat.sending = true;
  scrollChatToBottom(agentId);

  try {
    const res = await fetch(`/api/chat/${agentId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: chat.conversationId,
        message: text,
      }),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    chat.conversationId = data.conversation_id;
    chat.messages.push({
      role: "assistant",
      content: data.message.content,
      routed_to: data.routed_to,
    });
    // Refresh last_activity on the card after every successful exchange.
    Alpine.store("agents").load();
  } catch (e) {
    chat.error = `Couldn't reach the agent: ${e.message}`;
  } finally {
    chat.sending = false;
    scrollChatToBottom(agentId);
  }
}

function resetChat(agentId) {
  Alpine.store("agents").chats[agentId] = emptyChat();
}

function suggest(agentId, text) {
  const chat = Alpine.store("agents").chats[agentId];
  if (chat) chat.input = text;
}

function scrollChatToBottom(agentId) {
  requestAnimationFrame(() => {
    const el = document.querySelector(`[data-chat-scroll="${agentId}"]`);
    if (el) el.scrollTop = el.scrollHeight;
  });
}
