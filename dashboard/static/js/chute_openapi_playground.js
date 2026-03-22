/* global document, window, fetch, ChutesPlaygroundFields */

(function () {
  const OPENAPI_URL = "/api/playground/chute/openapi";
  const FIELDS_URL = "/api/playground/chute/openapi-fields";
  const CALL_URL = "/api/playground/chute/call";

  let ccMetaFields = [];
  let ccModelPresets = [];

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showChuteOut(data) {
    const section = document.getElementById("cc-output");
    const pre = document.getElementById("cc-out-pre");
    const imgWrap = document.getElementById("cc-out-media-wrap");
    const audioWrap = document.getElementById("cc-out-audio-wrap");
    const img = document.getElementById("cc-out-img");
    const aud = document.getElementById("cc-out-audio");
    if (!section || !pre) return;
    section.hidden = false;
    pre.hidden = true;
    pre.textContent = "";
    if (imgWrap) imgWrap.hidden = true;
    if (audioWrap) audioWrap.hidden = true;
    if (img) img.removeAttribute("src");
    if (aud) {
      aud.removeAttribute("src");
      aud.pause();
    }

    if (data.data_base64 && data.content_type) {
      if (data.content_type.indexOf("image/") === 0 && img && imgWrap) {
        img.src = "data:" + data.content_type + ";base64," + data.data_base64;
        imgWrap.hidden = false;
        return;
      }
      if (data.content_type.indexOf("audio/") === 0 && aud && audioWrap) {
        aud.src = "data:" + data.content_type + ";base64," + data.data_base64;
        audioWrap.hidden = false;
        return;
      }
    }
    pre.hidden = false;
    if (data.json != null) {
      pre.textContent = JSON.stringify(data.json, null, 2);
    } else if (data.text != null) {
      pre.textContent = data.text;
    } else {
      pre.textContent = JSON.stringify(data, null, 2);
    }
  }

  function syncMethodUi() {
    const method = (document.getElementById("cc-method")?.value || "POST").toUpperCase();
    const ta = document.getElementById("cc-json");
    const lab = ta && ta.closest("label");
    const withBody = method === "POST" || method === "PUT";
    if (ta) ta.disabled = !withBody;
    if (lab) lab.style.opacity = withBody ? "1" : "0.5";
  }

  function setDynamicMode(on) {
    const dyn = document.getElementById("cc-dyn-wrap");
    const jwrap = document.getElementById("cc-json-wrap");
    if (dyn) dyn.hidden = !on;
    if (jwrap) jwrap.hidden = on;
  }

  document.getElementById("cc-method")?.addEventListener("change", syncMethodUi);
  document.addEventListener("DOMContentLoaded", syncMethodUi);

  document.getElementById("cc-fetch-openapi")?.addEventListener("click", async function () {
    const base = (document.getElementById("cc-base")?.value || "").trim();
    const st = document.getElementById("cc-openapi-status");
    const sel = document.getElementById("cc-op");
    if (!base) {
      if (st) st.textContent = "Enter base URL first.";
      return;
    }
    if (st) st.textContent = "Fetching OpenAPI…";
    if (sel) {
      sel.innerHTML = "<option value=\"\">— pick an operation —</option>";
      sel.hidden = true;
    }
    ccMetaFields = [];
    setDynamicMode(false);
    if (window.ChutesPlaygroundFields) {
      window.ChutesPlaygroundFields.renderFieldsRoot(document.getElementById("cc-dyn-fields"), [], [], "cc-");
    }
    try {
      const res = await fetch(OPENAPI_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base_url: base }),
      });
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok || !data.ok) {
        if (st) st.textContent = "OpenAPI: " + escapeHtml(String(data.error || res.status));
        return;
      }
      const ops = data.operations || [];
      const opLabel = document.getElementById("cc-op-label");
      if (opLabel) opLabel.hidden = ops.length === 0;
      if (st) {
        st.textContent =
          "Loaded " +
          ops.length +
          " JSON operations" +
          (data.title ? " — " + data.title : "") +
          ".";
      }
      if (sel && ops.length) {
        sel.hidden = false;
        ops.forEach(function (op) {
          const o = document.createElement("option");
          const v = JSON.stringify({ path: op.path, method: op.method });
          o.value = v;
          o.textContent = op.method + " " + op.path + " — " + (op.summary || "").slice(0, 80);
          sel.appendChild(o);
        });
      }
    } catch (e) {
      if (st) st.textContent = String(e && e.message ? e.message : e);
    }
  });

  document.getElementById("cc-op")?.addEventListener("change", async function () {
    const raw = (document.getElementById("cc-op")?.value || "").trim();
    const st = document.getElementById("cc-openapi-status");
    const base = (document.getElementById("cc-base")?.value || "").trim();
    if (!raw || !base) return;
    let op;
    try {
      op = JSON.parse(raw);
    } catch (_e) {
      return;
    }
    document.getElementById("cc-path").value = op.path || "/";
    document.getElementById("cc-method").value = (op.method || "POST").toUpperCase();
    syncMethodUi();
    if (st) st.textContent = "Loading request schema…";
    try {
      const res = await fetch(FIELDS_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: base,
          path: op.path,
          method: op.method,
        }),
      });
      const data = await res.json().catch(function () {
        return {};
      });
      if (!res.ok || !data.ok) {
        if (st) st.textContent = "Schema: " + String(data.error || res.status);
        setDynamicMode(false);
        return;
      }
      ccMetaFields = data.fields || [];
      ccModelPresets = data.model_presets || ["default"];
      window.ChutesPlaygroundFields.renderFieldsRoot(
        document.getElementById("cc-dyn-fields"),
        ccMetaFields,
        ccModelPresets,
        "cc-"
      );
      setDynamicMode(ccMetaFields.length > 0);
      if (st) st.textContent = "Dynamic form ready (" + ccMetaFields.length + " fields).";
    } catch (e) {
      if (st) st.textContent = String(e && e.message ? e.message : e);
    }
  });

  document.getElementById("cc-use-manual")?.addEventListener("click", function () {
    ccMetaFields = [];
    setDynamicMode(false);
    const opLabel = document.getElementById("cc-op-label");
    const sel = document.getElementById("cc-op");
    if (opLabel) opLabel.hidden = true;
    if (sel) {
      sel.hidden = true;
      sel.innerHTML = "<option value=\"\">— pick an operation —</option>";
    }
    if (window.ChutesPlaygroundFields) {
      window.ChutesPlaygroundFields.renderFieldsRoot(document.getElementById("cc-dyn-fields"), [], [], "cc-");
    }
    const st = document.getElementById("cc-openapi-status");
    if (st) st.textContent = "Manual JSON mode.";
  });

  document.getElementById("cc-form")?.addEventListener("submit", async function (ev) {
    ev.preventDefault();
    const st = document.getElementById("cc-status");
    const btn = document.getElementById("cc-submit");
    const base = (document.getElementById("cc-base")?.value || "").trim();
    const path = (document.getElementById("cc-path")?.value || "/").trim() || "/";
    const method = (document.getElementById("cc-method")?.value || "POST").toUpperCase();

    let jsonPayload = undefined;
    const dynWrap = document.getElementById("cc-dyn-wrap");
    const useDynamic = ccMetaFields.length > 0 && dynWrap && !dynWrap.hidden;
    if (useDynamic) {
      try {
        jsonPayload = window.ChutesPlaygroundFields.collectPayload(ccMetaFields, "cc-");
      } catch (e) {
        if (st) st.textContent = String(e && e.message ? e.message : e);
        return;
      }
    } else if (method === "POST" || method === "PUT") {
      const t = (document.getElementById("cc-json")?.value || "").trim();
      if (t) {
        try {
          jsonPayload = JSON.parse(t);
        } catch (e) {
          if (st) st.textContent = "Invalid JSON: " + (e && e.message ? e.message : e);
          return;
        }
      } else {
        jsonPayload = null;
      }
    }

    if (st) st.textContent = "Calling chute…";
    if (btn) btn.disabled = true;
    const out = document.getElementById("cc-output");
    if (out) out.hidden = true;

    try {
      const res = await fetch(CALL_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          base_url: base,
          path: path,
          method: method,
          json: jsonPayload,
        }),
      });
      const data = await res.json().catch(function () {
        return { error: "Invalid JSON response" };
      });
      if (!res.ok || !data.ok) {
        if (st) st.textContent = "Error: " + (data.error ? JSON.stringify(data.error) : res.status);
        showChuteOut({ json: data });
        return;
      }
      if (st) st.textContent = "Done (" + (data.status || res.status) + ").";
      showChuteOut(data);
    } catch (e) {
      if (st) st.textContent = String(e && e.message ? e.message : e);
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  window.ChutesDeployedPlayground = {
    prefillBaseUrl: function (url, opt) {
      opt = opt || {};
      const input = document.getElementById("cc-base");
      if (input) input.value = (url || "").trim();
      const title = document.getElementById("pg-chute-title");
      if (title) title.scrollIntoView({ behavior: "smooth", block: "start" });
      if (opt.autoFetch) {
        setTimeout(function () {
          document.getElementById("cc-fetch-openapi")?.click();
        }, 250);
      }
    },
  };
})();
