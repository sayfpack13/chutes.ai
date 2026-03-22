/* global document, window */

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function pickRows(data) {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  if (typeof data === "object") {
    if (Array.isArray(data.items)) return data.items;
    if (Array.isArray(data.results)) return data.results;
    if (Array.isArray(data.chutes)) return data.chutes;
    if (Array.isArray(data.data)) return data.data;
  }
  return [];
}

function renderWhatsLive(rows) {
  const box = document.getElementById("whats-live-body");
  if (!box) return;
  if (!rows.length) {
    box.innerHTML =
      "<p class='muted small'>No chutes returned for this page. If you haven’t published yet, use <strong>Deploy this chute</strong> above.</p>";
    return;
  }
  const keys = new Set();
  rows.slice(0, 30).forEach((r) => {
    if (r && typeof r === "object") Object.keys(r).forEach((k) => keys.add(k));
  });
  const want = ["name", "slug", "status", "chute_id", "id", "username", "updated_at", "created_at"];
  const cols = want.filter((k) => keys.has(k)).slice(0, 6);
  if (!cols.length) {
    cols.push(...[...keys].slice(0, 5));
  }
  let html = "<table class='table table--compact'><thead><tr>";
  cols.forEach((c) => {
    html += `<th>${escapeHtml(c)}</th>`;
  });
  html += "</tr></thead><tbody>";
  rows.slice(0, 40).forEach((r) => {
    html += "<tr>";
    cols.forEach((k) => {
      let v = r[k];
      if (v !== null && typeof v === "object") v = JSON.stringify(v).slice(0, 48) + "…";
      html += `<td class="mono">${escapeHtml(String(v ?? ""))}</td>`;
    });
    html += "</tr>";
  });
  html += "</tbody></table>";
  if (rows.length > 40) {
    html += `<p class="muted small">Showing 40 of ${rows.length}. Use <a href="/platform/advanced">advanced tools</a> to page or filter.</p>`;
  }
  box.innerHTML = html;
}

async function loadHealthSummary() {
  const el = document.getElementById("health-ping");
  const wrap = document.getElementById("health-ping-wrap");
  if (!el) return;
  try {
    const r = await fetch("/api/health-summary");
    const d = await r.json();
    if (d.ping_ok) {
      el.textContent = "Reachable";
      wrap?.classList.add("ok");
    } else {
      el.textContent = "Can’t reach API";
      wrap?.classList.add("warn");
    }
  } catch {
    el.textContent = "Check failed";
    wrap?.classList.add("warn");
  }
}

async function loadWhatsLive() {
  const loading = document.getElementById("whats-live-loading");
  const box = document.getElementById("whats-live-body");
  if (!box) return;

  if (loading) loading.hidden = true;

  const res = await fetch("/api/platform/chutes?limit=50&page=0");
  const data = await res.json().catch(() => ({}));
  if (!data.ok) {
    box.innerHTML = `<p class="err small">Couldn’t load live chutes. ${escapeHtml(String(data.error || "Check Account and Diagnostics."))}</p>`;
    return;
  }
  const rows = pickRows(data.data);
  renderWhatsLive(rows);
}

document.getElementById("btn-home-cli-logs")?.addEventListener("click", async () => {
  const chuteName = window.prompt("Platform chute name (usually your chute name):", "");
  if (chuteName === null || !String(chuteName).trim()) return;
  const tailStr = window.prompt("How many log lines?", "50");
  const tail = parseInt(String(tailStr || "50"), 10) || 50;
  const out = document.getElementById("home-troubleshoot-out");
  if (out) {
    out.hidden = false;
    out.textContent = "Loading…";
  }
  const params = new URLSearchParams({
    chute_name: String(chuteName).trim(),
    tail: String(Math.min(500, Math.max(1, tail))),
  });
  const res = await fetch(`/api/cli/logs?${params}`);
  const data = await res.json().catch(() => ({}));
  if (out) {
    out.textContent = JSON.stringify(data, null, 2) + (res.ok ? "" : "\n\nHTTP error");
  }
});

document.addEventListener("DOMContentLoaded", () => {
  loadHealthSummary();
  const hasKey = document.getElementById("home-app")?.dataset.hasApiKey === "true";
  const loading = document.getElementById("whats-live-loading");
  const box = document.getElementById("whats-live-body");
  if (hasKey) {
    if (loading) {
      loading.hidden = false;
      loading.textContent = "Loading…";
    }
    loadWhatsLive();
  } else if (loading) {
    loading.hidden = false;
    loading.innerHTML =
      'Save an API key under <a href="/settings/account">Account</a> to see your live chutes.';
  }
});
