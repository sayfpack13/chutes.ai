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

function chuteNameFromRow(row) {
  if (!row || typeof row !== "object") return "";
  return String(row.name || row.slug || row.chute_id || row.id || "").trim();
}

async function postJson(url) {
  const res = await fetch(url, { method: "POST" });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, data };
}

function setStepState(step, kind, message) {
  const st = document.getElementById(`step-${step}-status`);
  if (!st) return;
  st.className = "deploy-step__status deploy-step__status--" + kind;
  st.textContent = message;
}

function setStepOut(step, text) {
  const el = document.getElementById(`step-${step}-out`);
  if (el) el.textContent = text;
}

function summarizeApiData(data) {
  if (!data) return "";
  if (data.path) return `Saved: ${data.path}`;
  if (data.ref) return `Module: ${data.ref}`;
  if (data.stdout && String(data.stdout).trim()) return String(data.stdout).trim().split("\n").slice(-3).join("\n");
  if (data.stderr && String(data.stderr).trim()) return String(data.stderr).trim().split("\n").slice(0, 2).join("\n");
  return data.ok ? "Done." : "Something went wrong.";
}

function getChuteName() {
  return document.getElementById("deploy-steps")?.getAttribute("data-chute-name") || "";
}

/** Turn common CLI stderr into a short, actionable line (full text stays in Show details). */
function friendlyCliError(stderr) {
  const s = String(stderr || "");
  if (!s.trim()) return null;
  if (/No module named ['"]pwd['"]/i.test(s) || /ModuleNotFoundError[^\n]*\bpwd\b/i.test(s)) {
    return (
      "The Chutes CLI uses Unix-only Python modules (here: 'pwd'). It usually won't run on Windows itself. " +
      "Use WSL2/Linux/macOS for Build and Publish, or run chutes from a supported environment."
    );
  }
  if (/No module named /i.test(s) && /ModuleNotFoundError/i.test(s)) {
    return "The Chutes command failed to start (missing Python module). See Show details for the traceback.";
  }
  return null;
}

document.querySelectorAll(".js-step-run").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const step = btn.getAttribute("data-step");
    const name = getChuteName();
    if (!name || !step) return;

    if (step === "publish") {
      if (!window.confirm("Publish to Chutes? This may charge your account.")) return;
    }

    setStepState(
      step,
      "running",
      step === "build"
        ? "Starting build — streaming output (first lines can take a while)…"
        : step === "publish"
          ? "Starting publish…"
          : "Working…"
    );
    setStepOut(step, "");
    btn.disabled = true;

    try {
      if (step === "prepare") {
        const { ok, data } = await postJson(`/api/generate/${encodeURIComponent(name)}`);
        setStepOut(step, JSON.stringify(data, null, 2) + (ok ? "" : "\n\nHTTP error"));
        if (ok && data && data.ok) {
          setStepState(step, "ok", summarizeApiData(data));
        } else {
          setStepState(step, "err", !ok ? "Request failed" : summarizeApiData(data) || "Failed");
        }
      } else if (step === "build") {
        const outEl = document.getElementById("step-build-out");
        outEl?.closest("details")?.setAttribute("open", "");
        let logBuf = "";
        const url = `/api/build/${encodeURIComponent(name)}/stream`;
        if (typeof window.consumeChutesNdjsonStream !== "function") {
          setStepState(step, "err", "Reload the page — chutes_stream.js failed to load.");
          return;
        }
        const { ok, data } = await window.consumeChutesNdjsonStream(url, {
          onLog(msg) {
            logBuf += msg;
            if (outEl) {
              outEl.textContent = logBuf;
              outEl.scrollTop = outEl.scrollHeight;
            }
            const oneLine = String(msg).replace(/\s+/g, " ").trim();
            const tail = oneLine.length > 90 ? "…" + oneLine.slice(-90) : oneLine;
            setStepState(step, "running", tail || "Running…");
          },
          onResult(ev) {
            setStepOut(step, JSON.stringify(ev, null, 2));
          },
          onHttpError(status, text) {
            setStepOut(step, `HTTP ${status}\n${text}`);
            setStepState(step, "err", `HTTP ${status}`);
          },
        });
        const hint = friendlyCliError((data && data.stderr) || (data && data.stdout));
        if (ok && data && data.ok) {
          setStepState(
            step,
            "ok",
            data.skipped ? "Skipped — Chutes standard image (no build needed)." : "Build finished."
          );
        } else {
          setStepState(
            step,
            "err",
            (data && data.hint) || hint || (data && data.stderr) || "Build failed — open Show details"
          );
        }
      } else if (step === "publish") {
        const outEl = document.getElementById("step-publish-out");
        outEl?.closest("details")?.setAttribute("open", "");
        let logBuf = "";
        const url = `/api/deploy/${encodeURIComponent(name)}/stream`;
        if (typeof window.consumeChutesNdjsonStream !== "function") {
          setStepState(step, "err", "Reload the page — chutes_stream.js failed to load.");
          return;
        }
        const { ok, data } = await window.consumeChutesNdjsonStream(url, {
          onLog(msg) {
            logBuf += msg;
            if (outEl) {
              outEl.textContent = logBuf;
              outEl.scrollTop = outEl.scrollHeight;
            }
            const oneLine = String(msg).replace(/\s+/g, " ").trim();
            const tail = oneLine.length > 90 ? "…" + oneLine.slice(-90) : oneLine;
            setStepState(step, "running", tail || "Publishing…");
          },
          onResult(ev) {
            setStepOut(step, JSON.stringify(ev, null, 2));
          },
          onHttpError(status, text) {
            setStepOut(step, `HTTP ${status}\n${text}`);
            setStepState(step, "err", `HTTP ${status}`);
          },
        });
        const hint = friendlyCliError((data && data.stderr) || (data && data.stdout));
        if (ok && data && data.ok) {
          setStepState(step, "ok", "Published. Check status below.");
        } else {
          setStepState(
            step,
            "err",
            (data && data.hint) || hint || (data && data.stderr) || "Publish failed — open Show details"
          );
        }
      } else if (step === "status") {
        const res = await fetch(`/api/platform/chutes?limit=100&page=0&name=${encodeURIComponent(name)}`);
        const data = await res.json().catch(() => ({}));
        setStepOut(step, JSON.stringify(data, null, 2));
        const live = document.getElementById("step-status-live");
        if (!data.ok) {
          setStepState(step, "err", data.error || "Could not load platform list");
          if (live) live.innerHTML = "";
        } else {
          const rows = pickRows(data.data);
          const matches = rows.filter((r) => {
            const n = chuteNameFromRow(r);
            return n === name || n.includes(name) || name.includes(n);
          });
          if (matches.length) {
            setStepState(step, "ok", `Found ${matches.length} matching row(s) on Chutes.`);
            if (live) {
              let html = "<table class='table table--compact'><thead><tr>";
              const keys = Object.keys(matches[0]).slice(0, 6);
              keys.forEach((k) => {
                html += `<th>${escapeHtml(k)}</th>`;
              });
              html += "</tr></thead><tbody>";
              matches.forEach((r) => {
                html += "<tr>";
                keys.forEach((k) => {
                  let v = r[k];
                  if (v !== null && typeof v === "object") v = JSON.stringify(v).slice(0, 40);
                  html += `<td class="mono">${escapeHtml(String(v ?? ""))}</td>`;
                });
                html += "</tr>";
              });
              html += "</tbody></table>";
              live.innerHTML = html;
            }
          } else if (rows.length && !matches.length) {
            setStepState(step, "ok", "Loaded your chutes, but none matched this name exactly. Try Chutes website or advanced tools.");
            if (live) live.innerHTML = "<p class='muted small'>No close match — name on platform may differ.</p>";
          } else {
            setStepState(step, "ok", "No chutes in this list yet, or filter returned empty.");
            if (live) live.innerHTML = "";
          }
        }
      }
    } catch (e) {
      setStepState(step, "err", String(e && e.message ? e.message : e));
      setStepOut(step, String(e));
    } finally {
      btn.disabled = false;
    }
  });
});
