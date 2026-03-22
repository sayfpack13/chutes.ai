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
      showOut("Build running (this can take a long time)…");
      const { ok, data } = await postJson(`/api/build/${encodeURIComponent(name)}`);
      showOut(JSON.stringify(data, null, 2) + (ok ? "" : "\n\nHTTP error"));
    });
  });
  document.querySelectorAll(".js-deploy").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const name = btn.getAttribute("data-name");
      if (!confirm("Deploy this chute? This may incur fees (--accept-fee).")) return;
      showOut("Deploying…");
      const { ok, data } = await postJson(`/api/deploy/${encodeURIComponent(name)}`);
      showOut(JSON.stringify(data, null, 2) + (ok ? "" : "\n\nHTTP error"));
    });
  });
}

document.addEventListener("DOMContentLoaded", wireButtons);
