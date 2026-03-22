/* global document, window, fetch, ChutesPlaygroundFields */

(function () {
  const META_URL = "/api/playground/image/meta";
  const RUN_URL = "/api/playground/image/run";

  let metaFields = [];
  let modelPresets = [];

  function formatRunError(data) {
    const e = data && data.error;
    if (e == null || e === "") return data && data.message ? String(data.message) : "Request failed";
    if (typeof e === "string") return e;
    if (typeof e === "object") {
      if (e.detail != null) {
        if (typeof e.detail === "string") return e.detail;
        if (Array.isArray(e.detail)) {
          return e.detail
            .map(function (d) {
              return typeof d === "object" && d.msg != null ? String(d.msg) : JSON.stringify(d);
            })
            .join("; ");
        }
      }
      try {
        return JSON.stringify(e);
      } catch (_x) {
        return String(e);
      }
    }
    return String(e);
  }

  function showResult(data) {
    const section = document.getElementById("pg-output");
    const imgWrap = document.getElementById("pg-out-image-wrap");
    const img = document.getElementById("pg-out-img");
    const pre = document.getElementById("pg-out-json");
    section.hidden = false;
    imgWrap.hidden = true;
    pre.hidden = true;
    pre.textContent = "";

    if (data.data_base64 && data.content_type) {
      img.src = "data:" + data.content_type + ";base64," + data.data_base64;
      imgWrap.hidden = false;
    } else if (data.json != null) {
      pre.textContent = JSON.stringify(data.json, null, 2);
      pre.hidden = false;
    } else {
      pre.textContent = JSON.stringify(data, null, 2);
      pre.hidden = false;
    }
  }

  function applyModelFromQuery() {
    const params = new URLSearchParams(window.location.search);
    const m = (params.get("model") || "").trim();
    if (!m) return;
    const sel = document.querySelector("#pg-fields [data-pf-model-select]");
    if (!sel) return;
    const wrap = sel.closest(".pf-model-wrap");
    const cust = wrap && wrap.querySelector("[data-pf-model-custom]");
    if (!cust) return;
    let found = false;
    for (let i = 0; i < sel.options.length; i++) {
      const o = sel.options[i];
      if (o.value === m && o.value !== "__custom__") {
        sel.selectedIndex = i;
        found = true;
        break;
      }
    }
    if (!found) {
      sel.value = "__custom__";
      cust.value = m;
      cust.style.display = "block";
    } else {
      cust.style.display = "none";
    }
  }

  async function loadMeta() {
    const box = document.getElementById("pg-meta");
    const fieldsRoot = document.getElementById("pg-fields");
    if (!box || !fieldsRoot || !window.ChutesPlaygroundFields) return;

    box.textContent = "Loading field definitions…";
    try {
      const res = await fetch(META_URL);
      const data = await res.json().catch(function () {
        return {};
      });
      metaFields = data.fields || [];
      modelPresets = data.model_presets || [];

      let msg =
        data.openapi_ok === true
          ? "Form fields follow the live OpenAPI from image.chutes.ai (cached a few minutes)."
          : "Using built-in field list (OpenAPI not loaded" +
            (data.openapi_error ? ": " + data.openapi_error : "") +
            ").";
      msg += " Endpoint: " + (data.image_api_base || "") + "/generate";
      if (data.model_presets_note) {
        msg += "\n\n" + data.model_presets_note;
      }
      box.textContent = msg;

      window.ChutesPlaygroundFields.renderFieldsRoot(fieldsRoot, metaFields, modelPresets, "");
      applyModelFromQuery();
    } catch (e) {
      box.textContent = "Could not load meta: " + (e && e.message ? e.message : e);
    }
  }

  document.getElementById("pg-form")?.addEventListener("submit", async function (ev) {
    ev.preventDefault();
    const st = document.getElementById("pg-status");
    const btn = document.getElementById("pg-submit");
    let payload;
    try {
      payload = window.ChutesPlaygroundFields.collectPayload(metaFields, "");
    } catch (err) {
      if (st) st.textContent = String(err.message || err);
      return;
    }
    if (st) st.textContent = "Calling Chutes…";
    if (btn) btn.disabled = true;
    try {
      const res = await fetch(RUN_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(function () {
        return { error: "Invalid JSON response" };
      });
      if (!res.ok || !data.ok) {
        let line = formatRunError(data);
        if (res.status === 404 && /model not found/i.test(line)) {
          line +=
            " — Use a preset from this form or a model id the hosted image service actually runs.";
        }
        if (st) st.textContent = "Error: " + line;
        showResult({ json: data });
        return;
      }
      if (st) st.textContent = "Done.";
      showResult(data);
    } catch (e) {
      if (st) st.textContent = String(e && e.message ? e.message : e);
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  loadMeta();
})();
