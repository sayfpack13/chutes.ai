/* global document */

/** Inspector panel element ids (single connected workflow UI) */
const WF = {
  summary: "workflow-summary",
  json: "workflow-json",
  badge: "workflow-badge",
  url: "workflow-url",
};

let selectedChuteId = "";
let selectedImageId = "";

function hasApiKey() {
  return document.getElementById("platform-app")?.dataset.hasApiKey === "true";
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function showJsonPre(obj) {
  const el = document.getElementById(WF.json);
  if (el) el.textContent = JSON.stringify(obj, null, 2);
}

function setBadge(text, variant) {
  const badge = document.getElementById(WF.badge);
  if (!badge) return;
  badge.textContent = text;
  badge.className = "badge";
  if (variant === "ok") badge.classList.add("badge--ok");
  else if (variant === "err") badge.classList.add("badge--err");
  else if (variant === "load") badge.classList.add("badge--load");
  else badge.classList.add("badge--muted");
}

function setResultUrl(text) {
  const el = document.getElementById(WF.url);
  if (!el) return;
  el.textContent = text || "";
}

function showResult(obj, meta) {
  const summaryEl = document.getElementById(WF.summary);
  showJsonPre(obj);

  if (obj && obj.loading) {
    setBadge("Loading…", "load");
    setResultUrl(typeof obj.loading === "string" ? obj.loading : "");
    if (summaryEl) {
      summaryEl.innerHTML = `<p class="muted">Requesting <code>${escapeHtml(String(obj.loading))}</code>…</p>`;
    }
    return;
  }

  const httpExtra = meta && meta.httpStatus != null ? meta.httpStatus : null;
  const isApiShape =
    obj &&
    typeof obj === "object" &&
    ("ok" in obj || "status" in obj) &&
    ("data" in obj || "error" in obj || obj.method);

  if (isApiShape) {
    const st = obj.status;
    const ok = Boolean(obj.ok);
    const label =
      httpExtra != null && httpExtra !== st
        ? `HTTP ${st} · response ${httpExtra}`
        : `HTTP ${st ?? "?"}`;
    setBadge(ok ? `Success · ${label}` : `Failed · ${label}`, ok ? "ok" : "err");
    setResultUrl(obj.url || "");
    if (summaryEl) summaryEl.innerHTML = renderApiEnvelope(obj);
    return;
  }

  const ok = httpExtra == null || (httpExtra >= 200 && httpExtra < 300);
  setBadge(httpExtra != null ? `HTTP ${httpExtra}` : "Response", ok ? "ok" : "err");
  setResultUrl("");
  if (summaryEl) summaryEl.innerHTML = renderGenericValue(obj);
}

function renderApiEnvelope(obj) {
  const parts = [];
  if (obj.method) {
    parts.push(`<p class="small muted"><strong>${escapeHtml(String(obj.method))}</strong></p>`);
  }
  if (obj.error) {
    parts.push(
      `<div class="callout callout--err"><strong>Error</strong><pre class="mono small">${escapeHtml(
        String(obj.error)
      )}</pre></div>`
    );
  }
  if (obj.ok && (obj.data === undefined || obj.data === null)) {
    parts.push(`<p class="success-msg">Request completed successfully (no JSON body).</p>`);
  } else if (obj.data !== undefined && obj.data !== null) {
    parts.push(renderDataForSummary(obj.data));
  } else if (!obj.error && !obj.ok) {
    parts.push(`<p class="muted small">No data or error field in response.</p>`);
  }
  return parts.join("") || `<p class="muted small">Empty response.</p>`;
}

function renderGenericValue(v) {
  if (v === null || v === undefined) return `<p class="muted">—</p>`;
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
    return `<p>${escapeHtml(String(v))}</p>`;
  }
  return renderDataForSummary(v);
}

function renderDataForSummary(data) {
  if (data === null || data === undefined) return `<p class="muted">No data</p>`;
  if (typeof data === "string") {
    return `<pre class="text-block">${escapeHtml(data)}</pre>`;
  }
  if (Array.isArray(data)) {
    if (data.length === 0) return `<p class="muted">Empty list</p>`;
    if (data.every((x) => x === null || ["string", "number", "boolean"].includes(typeof x))) {
      const items = data.slice(0, 50).map((x) => `<li>${escapeHtml(String(x))}</li>`).join("");
      const more = data.length > 50 ? `<p class="muted small">… and ${data.length - 50} more</p>` : "";
      return `<ul class="simple-list">${items}</ul>${more}`;
    }
    return `<p class="muted small">${data.length} items — see table above if this was a list call.</p>${renderObjectTablePreview(
      data
    )}`;
  }
  if (typeof data === "object") {
    if (typeof data.logs === "string" || typeof data.log === "string") {
      const logText = data.logs != null ? data.logs : data.log;
      const rest = { ...data };
      delete rest.logs;
      delete rest.log;
      const metaHtml = Object.keys(rest).length > 0 ? renderKvRowsWrap(rest, 0, 2) : "";
      return `${metaHtml}<h3 class="result-block-title">Log output</h3><pre class="text-block text-block--logs">${escapeHtml(
        logText
      )}</pre>`;
    }
    return renderKvRowsWrap(data, 0, 4);
  }
  return `<pre class="text-block">${escapeHtml(String(data))}</pre>`;
}

function renderObjectTablePreview(rows) {
  if (!rows.length) return "";
  const sample = rows.slice(0, 8);
  const keys = new Set();
  sample.forEach((r) => {
    if (r && typeof r === "object") Object.keys(r).forEach((k) => keys.add(k));
  });
  const cols = [...keys].slice(0, 6);
  if (!cols.length) return "";
  let html = "<table class='table table--compact'><thead><tr>";
  cols.forEach((k) => {
    html += `<th>${escapeHtml(k)}</th>`;
  });
  html += "</tr></thead><tbody>";
  sample.forEach((r) => {
    html += "<tr>";
    cols.forEach((k) => {
      let v = r[k];
      if (v !== null && typeof v === "object") v = JSON.stringify(v).slice(0, 60) + "…";
      html += `<td class="mono">${escapeHtml(String(v ?? ""))}</td>`;
    });
    html += "</tr>";
  });
  html += "</tbody></table>";
  if (rows.length > 8) html += `<p class="muted small">Preview of 8 / ${rows.length} rows.</p>`;
  return html;
}

function renderKvRowsInner(obj, depth, maxDepth) {
  if (!obj || typeof obj !== "object") return "";
  return Object.keys(obj)
    .map((key) => {
      const v = obj[key];
      return renderKvPair(key, v, depth, maxDepth);
    })
    .join("");
}

function renderKvRowsWrap(obj, depth, maxDepth, extraClass) {
  const inner = renderKvRowsInner(obj, depth, maxDepth);
  if (!inner) return "";
  const cls = `kv-grid${extraClass ? ` ${extraClass}` : ""}`;
  return `<dl class="${cls}">${inner}</dl>`;
}

function renderKvPair(key, v, depth, maxDepth) {
  const kHtml = escapeHtml(key);
  if (v === null || v === undefined) {
    return `<dt>${kHtml}</dt><dd class="muted">—</dd>`;
  }
  if (typeof v === "string" || typeof v === "number" || typeof v === "boolean") {
    const display = typeof v === "string" && v.length > 400 ? `${escapeHtml(v.slice(0, 400))}…` : escapeHtml(String(v));
    return `<dt>${kHtml}</dt><dd class="mono">${display}</dd>`;
  }
  if (Array.isArray(v)) {
    if (v.length === 0) {
      return `<dt>${kHtml}</dt><dd class="muted">[]</dd>`;
    }
    if (v.length <= 12 && v.every((x) => x === null || ["string", "number", "boolean"].includes(typeof x))) {
      const inner = v.map((x) => `<li>${escapeHtml(String(x))}</li>`).join("");
      return `<dt>${kHtml}</dt><dd><ul class="simple-list">${inner}</ul></dd>`;
    }
    if (depth >= maxDepth) {
      return `<dt>${kHtml}</dt><dd><pre class="text-block text-block--inline">${escapeHtml(
        JSON.stringify(v, null, 2).slice(0, 2500)
      )}${v.length > 10 ? "…" : ""}</pre></dd>`;
    }
    const tablePrev =
      v.length && typeof v[0] === "object"
        ? `<div class="nested-table">${renderObjectTablePreview(v)}</div>`
        : `<pre class="text-block text-block--inline">${escapeHtml(JSON.stringify(v, null, 2).slice(0, 1500))}…</pre>`;
    return `<dt>${kHtml}</dt><dd>${tablePrev}</dd>`;
  }
  if (typeof v === "object") {
    if (depth >= maxDepth) {
      return `<dt>${kHtml}</dt><dd><pre class="text-block text-block--inline">${escapeHtml(
        JSON.stringify(v, null, 2).slice(0, 2000)
      )}…</pre></dd>`;
    }
    return `<dt>${kHtml}</dt><dd>${renderKvRowsWrap(v, depth + 1, maxDepth, "kv-grid--nested")}</dd>`;
  }
  return `<dt>${kHtml}</dt><dd>${escapeHtml(String(v))}</dd>`;
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

function chuteRowId(row) {
  if (!row || typeof row !== "object") return "";
  return String(row.chute_id || row.id || row.slug || row.name || "").trim();
}

function imageRowId(row) {
  if (!row || typeof row !== "object") return "";
  return String(row.image_id || row.id || row.name || "").trim();
}

function setSelectedChute(id) {
  selectedChuteId = String(id || "").trim();
  const share = document.getElementById("share-chute");
  const del = document.getElementById("delete-chute-id");
  const lookup = document.getElementById("chute-lookup");
  if (share) share.value = selectedChuteId;
  if (del) del.value = selectedChuteId;
  if (lookup) lookup.value = selectedChuteId;
  const sel = document.getElementById("workflow-selection");
  if (sel) {
    sel.textContent = selectedChuteId
      ? `Selected chute: ${selectedChuteId} — share/delete fields updated.`
      : "No chute selected — click a chute row to select it for share/delete.";
  }
  document.querySelectorAll(".workflow-row-chute").forEach((tr) => {
    const enc = tr.getAttribute("data-chute-id") || "";
    const rid = enc ? decodeURIComponent(enc) : "";
    tr.classList.toggle("row-selected", Boolean(selectedChuteId) && rid === selectedChuteId);
  });
}

function setSelectedImage(id) {
  selectedImageId = String(id || "").trim();
  const logs = document.getElementById("image-logs-id");
  if (logs) logs.value = selectedImageId;
  document.querySelectorAll(".workflow-row-image").forEach((tr) => {
    const enc = tr.getAttribute("data-image-id") || "";
    const rid = enc ? decodeURIComponent(enc) : "";
    tr.classList.toggle("row-selected", Boolean(selectedImageId) && rid === selectedImageId);
  });
}

function renderTable(containerId, rows, tableKind) {
  const box = document.getElementById(containerId);
  if (!box) return;
  if (!rows.length) {
    box.innerHTML =
      "<p class='muted small empty-hint'>Nothing in this page of results. Try another page/filter or confirm the chute is deployed.</p>";
    return;
  }
  const keys = new Set();
  rows.slice(0, 50).forEach((r) => {
    if (r && typeof r === "object") Object.keys(r).forEach((k) => keys.add(k));
  });
  const preferred = ["name", "slug", "chute_id", "id", "image", "status", "tag", "username", "created_at", "updated_at"];
  const cols = preferred.filter((k) => keys.has(k));
  const rest = [...keys].filter((k) => !cols.includes(k)).slice(0, 8);
  const all = [...cols, ...rest];
  if (!all.length) {
    box.innerHTML = "<p class='muted small'>Objects have no keys to display.</p>";
    return;
  }
  const showChuteActions = tableKind === "chutes";
  const showImageActions = tableKind === "images";

  let html = "<table class='table'><thead><tr>";
  all.forEach((k) => {
    html += `<th>${escapeHtml(k)}</th>`;
  });
  if (showChuteActions || showImageActions) {
    html += "<th class='col-actions'>Actions</th>";
  }
  html += "</tr></thead><tbody>";
  rows.slice(0, 100).forEach((r) => {
    const cid = showChuteActions ? chuteRowId(r) : "";
    const iid = showImageActions ? imageRowId(r) : "";
    const chuteAttr = cid ? encodeURIComponent(cid) : "";
    const imageAttr = iid ? encodeURIComponent(iid) : "";
    const rowClass =
      showChuteActions
        ? `workflow-row-chute${cid && cid === selectedChuteId ? " row-selected" : ""}`
        : showImageActions
          ? `workflow-row-image${iid && iid === selectedImageId ? " row-selected" : ""}`
          : "";
    const extras = rowClass ? ` class="${rowClass}" tabindex="0"` : "";
    const dataChute = showChuteActions ? ` data-chute-id="${escapeHtml(chuteAttr)}"` : "";
    const dataImage = showImageActions ? ` data-image-id="${escapeHtml(imageAttr)}"` : "";
    html += `<tr${extras}${dataChute}${dataImage}>`;
    all.forEach((k) => {
      let v = r[k];
      if (v !== null && typeof v === "object") v = JSON.stringify(v).slice(0, 80);
      html += `<td class="mono">${escapeHtml(String(v ?? ""))}</td>`;
    });
    if (showChuteActions) {
      html += `<td class="actions-cell">`;
      if (cid) {
        const enc = encodeURIComponent(cid);
        html += `<button type="button" class="btn sm js-plat-detail" data-chute-id="${enc}">Detail</button>`;
        html += `<button type="button" class="btn sm secondary js-plat-warmup" data-chute-id="${enc}">Warmup</button>`;
      } else {
        html += "—";
      }
      html += `</td>`;
    } else if (showImageActions) {
      html += `<td class="actions-cell">`;
      if (iid) {
        const enc = encodeURIComponent(iid);
        html += `<button type="button" class="btn sm secondary js-plat-img-logs" data-image-id="${enc}">Logs</button>`;
      } else {
        html += "—";
      }
      html += `</td>`;
    }
    html += "</tr>";
  });
  html += "</tbody></table>";
  if (rows.length > 100) {
    html += `<p class="muted small">Showing first 100 of ${rows.length} rows.</p>`;
  }
  box.innerHTML = html;

  if (showChuteActions) {
    wireChuteTableActions(box);
    wireChuteRowClicks(box);
  }
  if (showImageActions) {
    wireImageTableActions(box);
    wireImageRowClicks(box);
  }
}

function wireChuteRowClicks(box) {
  box.querySelectorAll(".workflow-row-chute").forEach((tr) => {
    tr.addEventListener("click", (e) => {
      if (e.target.closest("button") || e.target.closest("a")) return;
      const enc = tr.getAttribute("data-chute-id");
      if (enc == null || enc === "") return;
      setSelectedChute(decodeURIComponent(enc));
    });
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        tr.click();
      }
    });
  });
}

function wireImageRowClicks(box) {
  box.querySelectorAll(".workflow-row-image").forEach((tr) => {
    tr.addEventListener("click", (e) => {
      if (e.target.closest("button") || e.target.closest("a")) return;
      const enc = tr.getAttribute("data-image-id");
      if (enc == null || enc === "") return;
      setSelectedImage(decodeURIComponent(enc));
    });
    tr.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        tr.click();
      }
    });
  });
}

function wireChuteTableActions(box) {
  box.querySelectorAll(".js-plat-detail").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const raw = btn.getAttribute("data-chute-id");
      if (!raw) return;
      const id = decodeURIComponent(raw);
      setSelectedChute(id);
      const path = "/api/platform/chutes/detail/" + encodeURIComponent(id);
      showResult({ loading: "Chute detail" }, {});
      const data = await fetchApi(path);
      showResult(data, {});
    });
  });
  box.querySelectorAll(".js-plat-warmup").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const raw = btn.getAttribute("data-chute-id");
      if (!raw) return;
      const id = decodeURIComponent(raw);
      setSelectedChute(id);
      const path = "/api/platform/chutes/warmup/" + encodeURIComponent(id);
      showResult({ loading: "Warmup" }, {});
      const data = await fetchApi(path);
      showResult(data, {});
    });
  });
}

function wireImageTableActions(box) {
  box.querySelectorAll(".js-plat-img-logs").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const raw = btn.getAttribute("data-image-id");
      if (!raw) return;
      const id = decodeURIComponent(raw);
      setSelectedImage(id);
      const path = `/api/platform/images/${encodeURIComponent(id)}/logs`;
      showResult({ loading: "Image logs" }, {});
      const data = await fetchApi(path);
      showResult(data, {});
    });
  });
}

async function fetchApi(url) {
  const res = await fetch(url);
  return res.json().catch(() => ({}));
}

function buildQuery(kind) {
  if (kind === "chutes") {
    const limit = document.getElementById("chutes-limit")?.value || "50";
    const page = document.getElementById("chutes-page")?.value || "0";
    const name = document.getElementById("chutes-name")?.value?.trim() || "";
    let q = `limit=${encodeURIComponent(limit)}&page=${encodeURIComponent(page)}`;
    if (name) q += `&name=${encodeURIComponent(name)}`;
    return q;
  }
  if (kind === "images") {
    const limit = document.getElementById("images-limit")?.value || "50";
    const page = document.getElementById("images-page")?.value || "0";
    const name = document.getElementById("images-name")?.value?.trim() || "";
    const tag = document.getElementById("images-tag")?.value?.trim() || "";
    let q = `limit=${encodeURIComponent(limit)}&page=${encodeURIComponent(page)}`;
    if (name) q += `&name=${encodeURIComponent(name)}`;
    if (tag) q += `&tag=${encodeURIComponent(tag)}`;
    return q;
  }
  return "";
}

function renderChutesError(boxId, res) {
  const box = document.getElementById(boxId);
  if (!box) return;
  const msg = res.error || "Request failed";
  box.innerHTML = `<div class="callout callout--err small"><strong>Could not load chutes</strong><pre class="mono small">${escapeHtml(
    String(msg)
  )}</pre><p class="small muted">HTTP ${escapeHtml(String(res.status ?? "?"))}</p></div>`;
}

function renderImagesError(boxId, res) {
  const box = document.getElementById(boxId);
  if (!box) return;
  const msg = res.error || "Request failed";
  box.innerHTML = `<div class="callout callout--err small"><strong>Could not load images</strong><pre class="mono small">${escapeHtml(
    String(msg)
  )}</pre><p class="small muted">HTTP ${escapeHtml(String(res.status ?? "?"))}</p></div>`;
}

async function refreshChutesTable() {
  const url = "/api/platform/chutes?" + buildQuery("chutes");
  const data = await fetchApi(url);
  if (!data.ok) {
    renderChutesError("chutes-table", data);
    return 0;
  }
  const rows = pickRows(data.data);
  renderTable("chutes-table", rows, "chutes");
  return rows.length;
}

async function refreshImagesTable() {
  const url = "/api/platform/images?" + buildQuery("images");
  const data = await fetchApi(url);
  if (!data.ok) {
    renderImagesError("images-table", data);
    return 0;
  }
  const rows = pickRows(data.data);
  renderTable("images-table", rows, "images");
  return rows.length;
}

async function refreshOverview() {
  const strip = document.getElementById("overview-strip");
  if (!hasApiKey()) {
    if (strip) strip.textContent = "Add an API key to load deployed chutes and images.";
    return;
  }
  if (strip) strip.textContent = "Refreshing chutes and images…";
  const [chRes, imRes] = await Promise.all([
    fetchApi("/api/platform/chutes?" + buildQuery("chutes")),
    fetchApi("/api/platform/images?" + buildQuery("images")),
  ]);
  let nChutes = 0;
  let nImages = 0;
  if (chRes.ok) {
    nChutes = pickRows(chRes.data).length;
    renderTable("chutes-table", pickRows(chRes.data), "chutes");
  } else {
    renderChutesError("chutes-table", chRes);
  }
  if (imRes.ok) {
    nImages = pickRows(imRes.data).length;
    renderTable("images-table", pickRows(imRes.data), "images");
  } else {
    renderImagesError("images-table", imRes);
  }
  const t = new Date().toLocaleTimeString();
  if (strip) {
    const problems = [];
    if (!chRes.ok) problems.push("chutes");
    if (!imRes.ok) problems.push("images");
    if (problems.length === 2) {
      strip.textContent = `Updated ${t} — could not load chutes or images. Check your API key (Account) and the Inspector below.`;
    } else if (problems.length === 1) {
      const okPart =
        problems[0] === "chutes"
          ? `${nImages} images loaded; chutes request failed.`
          : `${nChutes} chutes loaded; images request failed.`;
      strip.textContent = `Updated ${t} — partial load. ${okPart}`;
    } else {
      strip.textContent = `Last updated ${t} · ${nChutes} chutes · ${nImages} images on this page (filters + refresh to page through).`;
    }
  }
}

function wireAdvancedApiButtons() {
  document.querySelectorAll(".js-api").forEach((btn) => {
    btn.addEventListener("click", async () => {
      let url = btn.getAttribute("data-url");
      const label = btn.getAttribute("data-label") || url;
      showResult({ loading: label }, {});
      const data = await fetchApi(url);
      showResult(data, {});
    });
  });
}

document.getElementById("btn-refresh-overview")?.addEventListener("click", () => {
  refreshOverview();
});

document.getElementById("btn-refresh-chutes-only")?.addEventListener("click", async () => {
  const strip = document.getElementById("overview-strip");
  if (strip) strip.textContent = "Refreshing chutes…";
  const n = await refreshChutesTable();
  if (strip) strip.textContent = `Chutes refreshed · ${n} rows on this page.`;
});

document.getElementById("btn-refresh-images-only")?.addEventListener("click", async () => {
  const strip = document.getElementById("overview-strip");
  if (strip) strip.textContent = "Refreshing images…";
  const n = await refreshImagesTable();
  if (strip) strip.textContent = `Images refreshed · ${n} rows on this page.`;
});

document.getElementById("btn-overview-ping")?.addEventListener("click", async () => {
  showResult({ loading: "GET /ping" }, {});
  const data = await fetchApi("/api/platform/ping");
  showResult(data, {});
});

document.getElementById("btn-detail")?.addEventListener("click", async () => {
  const id = document.getElementById("chute-lookup")?.value?.trim();
  if (!id) {
    alert("Select a chute row or enter an id/name");
    return;
  }
  setSelectedChute(id);
  const path = "/api/platform/chutes/detail/" + encodeURIComponent(id);
  showResult({ loading: "GET /chutes/{id}" }, {});
  const data = await fetchApi(path);
  showResult(data, {});
});

document.getElementById("btn-warmup")?.addEventListener("click", async () => {
  const id = document.getElementById("chute-lookup")?.value?.trim();
  if (!id) {
    alert("Select a chute row or enter an id/name");
    return;
  }
  setSelectedChute(id);
  const path = "/api/platform/chutes/warmup/" + encodeURIComponent(id);
  showResult({ loading: "GET /chutes/warmup/{id}" }, {});
  const data = await fetchApi(path);
  showResult(data, {});
});

document.getElementById("btn-share")?.addEventListener("click", async () => {
  const chute = document.getElementById("share-chute")?.value?.trim();
  const user = document.getElementById("share-user")?.value?.trim();
  if (!chute || !user) {
    alert("Enter chute id/name and target user id/name");
    return;
  }
  const fd = new FormData();
  fd.append("chute_id_or_name", chute);
  fd.append("user_id_or_name", user);
  showResult({ loading: "POST /chutes/share" }, {});
  const res = await fetch("/api/platform/chutes/share", { method: "POST", body: fd });
  const data = await res.json().catch(() => ({}));
  showResult(data, { httpStatus: res.status });
});

document.getElementById("btn-delete-chute")?.addEventListener("click", async () => {
  const id = document.getElementById("delete-chute-id")?.value?.trim();
  if (!id) {
    alert("Enter chute id or name to delete");
    return;
  }
  const again = window.prompt(`Type exactly again to confirm DELETE:\n${id}`);
  if (again !== id) {
    alert("Confirmation did not match — cancelled.");
    return;
  }
  const url = `/api/platform/chutes/by-id/${encodeURIComponent(id)}?confirm=${encodeURIComponent(id)}`;
  showResult({ loading: "DELETE /chutes/{id}" }, {});
  const res = await fetch(url, { method: "DELETE" });
  const data = await res.json().catch(() => ({}));
  showResult(data, { httpStatus: res.status });
  if (data.ok) refreshOverview();
});

document.getElementById("btn-image-logs")?.addEventListener("click", async () => {
  const id = document.getElementById("image-logs-id")?.value?.trim();
  if (!id) {
    alert("Select an image row or enter image id");
    return;
  }
  const offset = document.getElementById("image-logs-offset")?.value?.trim() || "";
  let path = `/api/platform/images/${encodeURIComponent(id)}/logs`;
  if (offset) path += `?offset=${encodeURIComponent(offset)}`;
  showResult({ loading: "GET /images/{id}/logs" }, {});
  const data = await fetchApi(path);
  showResult(data, {});
});

document.addEventListener("DOMContentLoaded", () => {
  wireAdvancedApiButtons();
  if (hasApiKey()) {
    refreshOverview();
  }
});
