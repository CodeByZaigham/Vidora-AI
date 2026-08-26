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

