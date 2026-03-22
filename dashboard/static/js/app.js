function showOut(text) {
  const el = document.getElementById("out");
  if (!el) return;
  el.hidden = false;
  el.textContent = text;
}

async function postJson(url) {
  const res = await fetch(url, { method: "POST" });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, data };
}

async function loadHealthSummary() {
  const el = document.getElementById("health-ping");
  if (!el) return;
  try {
    const r = await fetch("/api/health-summary");
    const d = await r.json();
    if (d.ping_ok) {
      el.textContent = `API ping: OK (HTTP ${d.ping_status})`;
      el.classList.add("ok");
    } else {
      el.textContent = `API ping: failed (HTTP ${d.ping_status ?? "?"})`;
      el.classList.add("warn");
    }
  } catch {
    el.textContent = "API ping: error";
    el.classList.add("warn");
  }
}

function wireButtons() {
  document.querySelectorAll(".js-generate").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const name = btn.getAttribute("data-name");
      showOut("Generating…");
      const { ok, data } = await postJson(`/api/generate/${encodeURIComponent(name)}`);
      showOut(JSON.stringify(data, null, 2) + (ok ? "" : "\n\nHTTP error"));
    });
  });
  document.querySelectorAll(".js-build").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const name = btn.getAttribute("data-name");
      const el = document.getElementById("out");
      if (el) {
        el.hidden = false;
        el.textContent = "";
      }
      let buf = "";
      const { ok, data } = await window.consumeChutesNdjsonStream(
        `/api/build/${encodeURIComponent(name)}/stream`,
        {
          onLog(msg) {
            buf += (buf ? "\n" : "") + msg;
            if (el) {
              el.textContent = buf;
              el.scrollTop = el.scrollHeight;
            }
          },
          onResult(ev) {
            if (el) el.textContent = buf + (buf ? "\n\n" : "") + JSON.stringify(ev, null, 2);
          },
          onHttpError(status, text) {
            if (el) el.textContent = `HTTP ${status}\n${text}`;
          },
        }
      );
      if (el && !ok) showOut((el.textContent || "") + "\n\n" + JSON.stringify(data, null, 2));
    });
  });
  document.querySelectorAll(".js-deploy").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const name = btn.getAttribute("data-name");
      if (!confirm("Deploy this chute? This may incur fees (--accept-fee).")) return;
      const el = document.getElementById("out");
      if (el) {
        el.hidden = false;
        el.textContent = "";
      }
      let buf = "";
      const { ok, data } = await window.consumeChutesNdjsonStream(
        `/api/deploy/${encodeURIComponent(name)}/stream`,
        {
          onLog(msg) {
            buf += (buf ? "\n" : "") + msg;
            if (el) {
              el.textContent = buf;
              el.scrollTop = el.scrollHeight;
            }
          },
          onResult(ev) {
            if (el) el.textContent = buf + (buf ? "\n\n" : "") + JSON.stringify(ev, null, 2);
          },
          onHttpError(status, text) {
            if (el) el.textContent = `HTTP ${status}\n${text}`;
          },
        }
      );
      if (el && !ok) showOut((el.textContent || "") + "\n\n" + JSON.stringify(data, null, 2));
    });
  });
  document.querySelectorAll(".js-cli-logs").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const def = btn.getAttribute("data-config-name") || "";
      const chuteName = window.prompt("Platform chute name (for `chutes chutes logs`):", def);
      if (chuteName === null || !String(chuteName).trim()) return;
      const tailStr = window.prompt("Tail how many lines?", "50");
      const tail = parseInt(String(tailStr || "50"), 10) || 50;
      showOut("Fetching CLI logs…");
      const params = new URLSearchParams({
        chute_name: String(chuteName).trim(),
        tail: String(Math.min(500, Math.max(1, tail))),
      });
      const res = await fetch(`/api/cli/logs?${params}`);
      const data = await res.json().catch(() => ({}));
      showOut(JSON.stringify(data, null, 2) + (res.ok ? "" : "\n\nHTTP error"));
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  loadHealthSummary();
  wireButtons();
});
