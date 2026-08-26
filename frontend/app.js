"use strict";

const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const POLL_INTERVAL_MS = 2500;

const state = {
  apiBase: localStorage.getItem("ava_api_base") || DEFAULT_API_BASE,
  videos: new Map(),        // video_id -> VideoStatus object from the API
  selectedId: null,
  polls: new Map(),         // video_id -> interval id
  insightsCache: new Map(), // video_id -> InsightsResponse
  chats: new Map(),         // video_id -> [{ role: "q"|"a", text, pending? }]
  uploadFile: null,
};

/* ============================================================
   Small helpers
   ============================================================ */

function $(sel, root = document) { return root.querySelector(sel); }
function $all(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatWhen(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function displayName(video) {
  return video.title || video.source_title || video.source || "Untitled";
}

function toast(message, kind = "default") {
  const stack = $("#toastStack");
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 0.2s ease";
    setTimeout(() => el.remove(), 220);
  }, 4200);
}

/* ============================================================
   API layer
   ============================================================ */

async function apiFetch(path, options = {}) {
  const url = `${state.apiBase}${path}`;
  let res;
  try {
    res = await fetch(url, options);
  } catch (err) {
    throw new Error(`Could not reach the backend at ${state.apiBase}. Is it running? (${err.message})`);
  }

  if (res.status === 204) return null;

  let data = null;
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    data = await res.json().catch(() => null);
  }

  if (!res.ok) {
    const detail = (data && data.detail) ? data.detail : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return data;
}

const api = {
  listVideos: () => apiFetch("/videos"),
  getVideo: (id) => apiFetch(`/videos/${id}`),
  submitUrl: (url, translate, chunkMinutes) => apiFetch("/videos/url", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url,
      translate_to_english: translate,
      chunk_minutes: chunkMinutes,
    }),
  }),
  submitUpload: (file, translate) => {
    const form = new FormData();
    form.append("file", file);
    const qs = translate ? "?translate_to_english=true" : "";
    return apiFetch(`/videos/upload${qs}`, { method: "POST", body: form });
  },
  retryVideo: (id, translate, chunkMinutes) => apiFetch(`/videos/${id}/retry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      translate_to_english: translate === undefined ? null : translate,
      chunk_minutes: chunkMinutes === undefined ? null : chunkMinutes,
    }),
  }),
  deleteVideo: (id) => apiFetch(`/videos/${id}`, { method: "DELETE" }),
  getInsights: (id) => apiFetch(`/videos/${id}/insights`),
  ask: (id, question) => apiFetch(`/videos/${id}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k: 8 }),
  }),
  transcriptDownloadUrl: (id) => `${state.apiBase}/videos/${id}/transcript/download`,
};

/* ============================================================
   Polling — one independent loop per video_id
   ============================================================ */

const TERMINAL_STATUSES = new Set(["ready", "failed"]);

function startPolling(id) {
  if (state.polls.has(id)) return; // already being watched, never double-poll
  const jitter = Math.floor(Math.random() * 400);
  const timer = setInterval(() => refreshVideo(id), POLL_INTERVAL_MS + jitter);
  state.polls.set(id, timer);
}

function stopPolling(id) {
  const timer = state.polls.get(id);
  if (timer) {
    clearInterval(timer);
    state.polls.delete(id);
  }
}

async function refreshVideo(id) {
  // If the video was deleted from local state (e.g. user deleted it) while
  // a poll tick was already in flight, just stop -- nothing to update.
  if (!state.videos.has(id)) {
    stopPolling(id);
    return;
  }
  try {
    const fresh = await api.getVideo(id);
    state.videos.set(id, fresh);
    renderVideoCard(id);
    if (state.selectedId === id) renderDeck();

    if (TERMINAL_STATUSES.has(fresh.status)) {
      stopPolling(id);
      if (fresh.status === "ready" && state.selectedId === id) {
        loadInsights(id); // auto-display extracted material the moment it's ready
      }
    }
  } catch (err) {
    // A transient network hiccup shouldn't kill the poll loop or spam
    // toasts every 2.5s -- just skip this tick and try again next time.
    console.warn(`Poll failed for ${id}:`, err.message);
  }
}

/* ============================================================
   Rendering — video list
   ============================================================ */

function vuMeterHtml(status, size = "small", bars = 5) {
  const stateClass = status === "processing" || status === "queued"
    ? `state-${status}`
    : status === "ready" ? "state-ready"
    : status === "failed" ? "state-failed"
    : "idle";
  const spans = Array.from({ length: bars }, () => "<span></span>").join("");
  return `<div class="vu-meter ${size} ${stateClass}" aria-hidden="true">${spans}</div>`;
}

function statusLabel(video) {
  if (video.status === "failed") return "Failed";
  if (video.status === "ready") return "Ready";
  if (video.status === "processing") return video.progress || "Processing\u2026";
  return "Queued";
}

function renderVideoList() {
  const list = $("#videoList");
  const count = $("#railCount");

  const videos = Array.from(state.videos.values()).sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
  count.textContent = String(videos.length);

  if (videos.length === 0) {
    list.innerHTML = `<div class="rail-empty">No videos yet. Load one above.</div>`;
    return;
  }

  list.innerHTML = videos.map((v) => videoCardHtml(v)).join("");
}

function videoCardHtml(video) {
  const selected = state.selectedId === video.video_id ? "selected" : "";
  const source = video.source_type === "youtube" ? "YouTube" : "Upload";
  return `
    <button class="video-card ${selected}" data-id="${video.video_id}" data-action="select" type="button">
      ${vuMeterHtml(video.status, "small")}
      <span class="video-card-info">
        <span class="video-card-title">${escapeHtml(displayName(video))}</span>
        <span class="video-card-meta">
          <span class="source-badge">${source}</span>
          <span class="status-text status-${video.status}">${escapeHtml(statusLabel(video))}</span>
        </span>
      </span>
      <span class="video-card-delete" data-action="delete" data-id="${video.video_id}" title="Delete">&times;</span>
    </button>
  `;
}

function renderVideoCard(id) {
  // Cheap path: only re-render the whole list (simplest correct option,
  // fine at the scale this app runs at). Kept as its own function so call
  // sites read clearly.
  renderVideoList();
}

/* ============================================================
   Rendering — deck (detail panel)
   ============================================================ */

function renderDeck() {
  const deck = $("#deck");
  const video = state.selectedId ? state.videos.get(state.selectedId) : null;

  if (!video) {
    deck.innerHTML = `
      <div class="deck-empty">
        ${vuMeterHtml("idle", "large", 7)}
        <h2>Nothing selected</h2>
        <p>Paste a YouTube URL or upload a file on the left to get a transcript, a summary, and an assistant that can answer questions about it.</p>
      </div>
    `;
    return;
  }

  if (video.status === "failed") {
    deck.innerHTML = `
      <div class="deck-status">
        ${vuMeterHtml("failed", "large", 7)}
        <h2>Processing failed</h2>
        <p>${escapeHtml(displayName(video))}</p>
        <div class="source-line">${escapeHtml(video.source)}</div>
        <div class="error-box">${escapeHtml(video.error || "Unknown error")}</div>
        <div class="status-actions">
          <button class="btn btn-primary" data-action="retry" data-id="${video.video_id}" type="button">Retry</button>
          <button class="btn btn-danger" data-action="delete" data-id="${video.video_id}" type="button">Delete</button>
        </div>
      </div>
    `;
    return;
  }

  if (video.status !== "ready") {
    deck.innerHTML = `
      <div class="deck-status">
        ${vuMeterHtml("processing", "large", 7)}
        <h2>${escapeHtml(displayName(video))}</h2>
        <p>This can take a while for longer videos &mdash; local transcription runs chunk by chunk.</p>
        <div class="progress-text"><span class="rec-dot"></span>${escapeHtml(video.progress || "Queued")}</div>
        <div class="source-line">${escapeHtml(video.source)}</div>
        <div class="status-actions">
          <button class="btn btn-danger" data-action="delete" data-id="${video.video_id}" type="button">Cancel &amp; delete</button>
        </div>
      </div>
    `;
    return;
  }

  // status === "ready"
  const insights = state.insightsCache.get(video.video_id);
  deck.innerHTML = readyDeckHtml(video, insights);
  wireInsightTabs();
  renderChatThread(video.video_id);

  if (!insights) loadInsights(video.video_id);
}

function readyDeckHtml(video, insights) {
  const source = video.source_type === "youtube" ? "YouTube" : "Upload";
  const chips = [
    `<span class="meta-chip">${source}</span>`,
    video.translate_to_english ? `<span class="meta-chip">Translated to English</span>` : "",
    video.chunk_minutes ? `<span class="meta-chip">${video.chunk_minutes}min chunks</span>` : "",
    `<span class="meta-chip">${escapeHtml(formatWhen(video.created_at))}</span>`,
  ].filter(Boolean).join("");

  const tabs = [
    ["summary", "Summary"],
    ["questions", "Questions"],
    ["decisions", "Decisions"],
    ["actions", "Action items"],
    ["transcript", "Transcript"],
  ];

  const tabButtons = tabs.map(([key, label], i) =>
    `<button class="insight-tab ${i === 0 ? "active" : ""}" data-tab="${key}" type="button">${label}</button>`
  ).join("");

  const loadingBody = `<p class="insight-body" style="color:var(--ink-faint)">Loading&hellip;</p>`;

  const panels = tabs.map(([key], i) => {
    const active = i === 0 ? "active" : "";
    let body;
    if (key === "transcript") {
      body = insights
        ? `<div class="transcript-toolbar">
             <a class="btn btn-ghost" href="${api.transcriptDownloadUrl(video.video_id)}" download>Download .txt</a>
           </div>
           <div class="transcript-box" id="transcriptBox">Loading transcript&hellip;</div>`
        : loadingBody;
    } else {
      const text = insights ? insights[key] : null;
      body = insights
        ? `<div class="insight-body">${escapeHtml(text || "Nothing extracted for this section.")}</div>`
        : loadingBody;
    }
    return `<div class="insight-panel ${active}" data-panel="${key}">${body}</div>`;
  }).join("");

  return `
    <div class="deck-content">
      <div class="deck-header">
        <div class="deck-eyebrow">
          <span>${escapeHtml(source)}</span>
          <span>&middot;</span>
          <span>${escapeHtml(formatWhen(video.created_at))}</span>
        </div>
        <h1 class="deck-title">${escapeHtml(displayName(video))}</h1>
        <div class="deck-meta-row">
          ${chips}
          <span class="deck-actions">
            <button class="btn btn-ghost" data-action="delete" data-id="${video.video_id}" type="button">Delete</button>
          </span>
        </div>
      </div>

      <div class="insight-tabs">${tabButtons}</div>
      ${panels}
    </div>

    <div class="chat-dock">
      <div class="chat-dock-inner">
        <div class="chat-heading">Ask about this video</div>
        <div class="chat-thread" id="chatThread"></div>
        <form class="chat-input-row" id="chatForm">
          <input class="text-input" type="text" id="chatInput" placeholder="e.g. what did they decide about the deadline?" autocomplete="off" />
          <button class="btn btn-primary" type="submit">Ask</button>
        </form>
      </div>
    </div>
  `;
}

function wireInsightTabs() {
  $all(".insight-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      $all(".insight-tab").forEach((b) => b.classList.remove("active"));
      $all(".insight-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $(`.insight-panel[data-panel="${btn.dataset.tab}"]`).classList.add("active");
    });
  });

  const chatForm = $("#chatForm");
  if (chatForm) {
    chatForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const input = $("#chatInput");
      const question = input.value.trim();
      if (!question) return;
      input.value = "";
      submitQuestion(state.selectedId, question);
    });
  }
}

async function loadInsights(id) {
  try {
    const data = await api.getInsights(id);
    state.insightsCache.set(id, data);
    if (state.selectedId === id) {
      renderDeck();
      const box = $("#transcriptBox");
      if (box) loadTranscriptText(id);
    }
  } catch (err) {
    toast(`Couldn't load insights: ${err.message}`, "error");
  }
}

async function loadTranscriptText(id) {
  try {
    const data = await apiFetch(`/videos/${id}/transcript`);
    const box = $("#transcriptBox");
    if (box && state.selectedId === id) box.textContent = data.transcript || "(empty transcript)";
  } catch (err) {
    const box = $("#transcriptBox");
    if (box) box.textContent = `Couldn't load transcript: ${err.message}`;
  }
}

/* ============================================================
   Chat
   ============================================================ */

function renderChatThread(id) {
  const thread = $("#chatThread");
  if (!thread) return;
  const messages = state.chats.get(id) || [];
  if (messages.length === 0) {
    thread.innerHTML = `<div class="chat-empty">No questions asked yet.</div>`;
    return;
  }
  thread.innerHTML = messages.map((m) => {
    if (m.role === "q") return `<div class="chat-bubble q">${escapeHtml(m.text)}</div>`;
    const pendingClass = m.pending ? "pending" : "";
    return `<div class="chat-bubble a ${pendingClass}">${escapeHtml(m.text)}</div>`;
  }).join("");
  thread.scrollTop = thread.scrollHeight;
}

async function submitQuestion(id, question) {
  if (!state.chats.has(id)) state.chats.set(id, []);
  const messages = state.chats.get(id);
  messages.push({ role: "q", text: question });
  messages.push({ role: "a", text: "Thinking\u2026", pending: true });
  if (state.selectedId === id) renderChatThread(id);

  try {
    const res = await api.ask(id, question);
    const pendingMsg = messages[messages.length - 1];
    pendingMsg.text = res.answer;
    pendingMsg.pending = false;
  } catch (err) {
    const pendingMsg = messages[messages.length - 1];
    pendingMsg.text = `Couldn't get an answer: ${err.message}`;
    pendingMsg.pending = false;
  }
  if (state.selectedId === id) renderChatThread(id);
}

/* ============================================================
   Actions
   ============================================================ */

function selectVideo(id) {
  state.selectedId = id;
  renderVideoList();
  renderDeck();
  refreshVideo(id); // fetch immediately so a just-opened video feels responsive
}

async function retryVideo(id) {
  try {
    const updated = await api.retryVideo(id);
    state.videos.set(id, updated);
    state.insightsCache.delete(id);
    renderVideoList();
    if (state.selectedId === id) renderDeck();
    startPolling(id);
    toast("Retrying\u2026");
  } catch (err) {
    toast(`Retry failed: ${err.message}`, "error");
  }
}

async function deleteVideo(id) {
  const video = state.videos.get(id);
  const label = video ? displayName(video) : id;
  if (!confirm(`Delete "${label}"? This removes its transcript, insights, and search index.`)) return;

  stopPolling(id);
  try {
    await api.deleteVideo(id);
  } catch (err) {
    toast(`Couldn't delete: ${err.message}`, "error");
    return; // keep local state so the user can retry the delete
  }
  state.videos.delete(id);
  state.insightsCache.delete(id);
  state.chats.delete(id);
  if (state.selectedId === id) state.selectedId = null;
  renderVideoList();
  renderDeck();
  toast("Deleted", "success");
}

/* ============================================================
   Submission form (URL / upload)
   ============================================================ */

function activeSubmitTab() {
  return $(".tab.active").dataset.tab;
}

function wireTabs() {
  $all(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      $all(".tab").forEach((t) => { t.classList.remove("active"); t.setAttribute("aria-selected", "false"); });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      $all(".tab-panel").forEach((p) => { p.hidden = p.dataset.panel !== tab.dataset.tab; });
      $("#chunkMinutes").closest(".advanced").style.display = tab.dataset.tab === "url" ? "" : "none";
    });
  });
}

function wireDropzone() {
  const dz = $("#dropzone");
  const input = $("#fileInput");
  const filenameEl = $("#dzFilename");

  dz.addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    state.uploadFile = input.files[0] || null;
    filenameEl.textContent = state.uploadFile ? state.uploadFile.name : "";
  });

  ["dragenter", "dragover"].forEach((evt) => {
    dz.addEventListener(evt, (e) => { e.preventDefault(); dz.classList.add("drag-over"); });
  });
  ["dragleave", "drop"].forEach((evt) => {
    dz.addEventListener(evt, (e) => { e.preventDefault(); dz.classList.remove("drag-over"); });
  });
  dz.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (file) {
      state.uploadFile = file;
      input.files = e.dataTransfer.files;
      filenameEl.textContent = file.name;
    }
  });
}

function addVideoToState(video) {
  state.videos.set(video.video_id, video);
  renderVideoList();
  startPolling(video.video_id);
}

async function handleSubmit() {
  const btn = $("#submitBtn");
  const tab = activeSubmitTab();
  const translate = $("#translateCheckbox").checked;
  const chunkRaw = $("#chunkMinutes").value.trim();
  const chunkMinutes = chunkRaw ? Math.max(1, parseInt(chunkRaw, 10)) : null;

  if (tab === "url") {
    const url = $("#urlInput").value.trim();
    if (!url) { toast("Enter a video URL first", "error"); return; }
    btn.disabled = true;
    try {
      const video = await api.submitUrl(url, translate, chunkMinutes);
      addVideoToState(video);
      selectVideo(video.video_id);
      $("#urlInput").value = "";
      toast("Video queued for processing");
    } catch (err) {
      toast(`Couldn't submit URL: ${err.message}`, "error");
    } finally {
      btn.disabled = false;
    }
  } else {
    const file = state.uploadFile;
    if (!file) { toast("Choose a file first", "error"); return; }
    btn.disabled = true;
    try {
      const video = await api.submitUpload(file, translate);
      addVideoToState(video);
      selectVideo(video.video_id);
      state.uploadFile = null;
      $("#fileInput").value = "";
      $("#dzFilename").textContent = "";
      toast("Video queued for processing");
    } catch (err) {
      toast(`Couldn't upload file: ${err.message}`, "error");
    } finally {
      btn.disabled = false;
    }
  }
}

/* ============================================================
   Delegated click handling (video cards, delete, retry)
   ============================================================ */

function wireDelegatedClicks() {
  $("#videoList").addEventListener("click", (e) => {
    const target = e.target.closest("[data-action]");
    if (!target) return;
    const id = target.dataset.id;
    if (target.dataset.action === "delete") {
      e.stopPropagation();
      deleteVideo(id);
    } else if (target.dataset.action === "select") {
      selectVideo(id);
    }
  });

  $("#deck").addEventListener("click", (e) => {
    const target = e.target.closest("[data-action]");
    if (!target) return;
    const id = target.dataset.id;
    if (target.dataset.action === "delete") deleteVideo(id);
    if (target.dataset.action === "retry") retryVideo(id);
  });
}

/* ============================================================
   Settings modal (API base URL)
   ============================================================ */

function wireSettings() {
  const overlay = $("#settingsOverlay");
  const input = $("#apiBaseInput");

  $("#settingsBtn").addEventListener("click", () => {
    input.value = state.apiBase;
    overlay.hidden = false;
    input.focus();
  });
  $("#apiBaseCancel").addEventListener("click", () => { overlay.hidden = true; });
  overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.hidden = true; });

  $("#apiBaseSave").addEventListener("click", () => {
    const value = input.value.trim().replace(/\/+$/, "");
    if (!value) return;
    state.apiBase = value;
    localStorage.setItem("ava_api_base", value);
    overlay.hidden = true;
    toast("Backend address updated");
    bootstrap();
  });
}

/* ============================================================
   Boot
   ============================================================ */

async function bootstrap() {
  // Stop any polling from a previous backend before reloading the list.
  state.polls.forEach((timer) => clearInterval(timer));
  state.polls.clear();

  try {
    const data = await api.listVideos();
    state.videos = new Map(data.videos.map((v) => [v.video_id, v]));
  } catch (err) {
    toast(`Couldn't load videos: ${err.message}`, "error");
    state.videos = new Map();
  }

  renderVideoList();
  renderDeck();

  state.videos.forEach((video) => {
    if (!TERMINAL_STATUSES.has(video.status)) startPolling(video.video_id);
  });
}

function init() {
  wireTabs();
  wireDropzone();
  wireDelegatedClicks();
  wireSettings();
  $("#submitBtn").addEventListener("click", handleSubmit);
  bootstrap();
}

document.addEventListener("DOMContentLoaded", init);
