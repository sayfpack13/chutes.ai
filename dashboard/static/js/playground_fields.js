/* global window */
/**
 * Shared OpenAPI-driven field UI for playground forms (image + deployed chutes).
 */
(function (global) {
  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function renderModelSelect(f, modelPresets, idPrefix) {
    const pfx = idPrefix || "";
    const wrap = el("div", "pf-field pf-model-wrap");
    wrap.id = pfx + "pf-" + f.key;

    const sel = document.createElement("select");
    sel.className = "pf-control";
    sel.dataset.pfModelSelect = "1";
    const presets =
      modelPresets && modelPresets.length
        ? modelPresets
        : [f.default != null ? String(f.default) : "default"];
    const def = f.default != null ? String(f.default) : presets[0];
    presets.forEach(function (p) {
      const o = document.createElement("option");
      o.value = p;
      o.textContent = p;
      if (p === def) o.selected = true;
      sel.appendChild(o);
    });
    const oc = document.createElement("option");
    oc.value = "__custom__";
    oc.textContent = "Custom…";
    sel.appendChild(oc);

    const inp = document.createElement("input");
    inp.type = "text";
    inp.className = "pf-control pf-model-custom";
    inp.dataset.pfModelCustom = "1";
    inp.placeholder = "model id";
    inp.style.marginTop = "8px";
    inp.style.display = "none";

    sel.addEventListener("change", function () {
      inp.style.display = sel.value === "__custom__" ? "block" : "none";
    });

    wrap.appendChild(sel);
    wrap.appendChild(inp);
    return wrap;
  }

  function renderEnumSelect(f, idPrefix) {
    const pfx = idPrefix || "";
    const wrap = el("div", "pf-field");
    wrap.id = pfx + "pf-" + f.key;
    const sel = document.createElement("select");
    sel.className = "pf-control";
    (f.enum || []).forEach(function (v) {
      const o = document.createElement("option");
      o.value = String(v);
      o.textContent = String(v);
      if (f.default != null && String(f.default) === String(v)) o.selected = true;
      sel.appendChild(o);
    });
    wrap.appendChild(sel);
    return wrap;
  }

  function renderField(f, modelPresets, idPrefix) {
    const pfx = idPrefix || "";
    const row = el("div", "pf-row");
    const lab = el("label", "pf-label");
    lab.htmlFor = pfx + "pf-input-" + f.key;
    const title = f.title || f.key;
    lab.textContent = title + (f.required ? " *" : "");

    let control;
    if (f.widget === "model_select" || (f.key === "model" && !f.enum)) {
      control = renderModelSelect(f, modelPresets || [], idPrefix);
    } else if (f.enum && Array.isArray(f.enum) && f.enum.length) {
      control = renderEnumSelect(f, idPrefix);
    } else if (
      f.widget === "textarea" ||
      (f.type === "string" && /prompt|negative|caption|description|text|content|input/i.test(f.key))
    ) {
      const ta = document.createElement("textarea");
      ta.id = pfx + "pf-input-" + f.key;
      ta.className = "pf-control";
      ta.rows = /prompt/i.test(f.key) ? 4 : 3;
      if (f.default != null && f.default !== "") ta.value = String(f.default);
      control = el("div", "pf-field");
      control.appendChild(ta);
    } else if (f.type === "string") {
      const inp = document.createElement("input");
      inp.type = "text";
      inp.id = pfx + "pf-input-" + f.key;
      inp.className = "pf-control";
      if (f.default != null && f.default !== "") inp.value = String(f.default);
      control = el("div", "pf-field");
      control.appendChild(inp);
    } else if (f.type === "boolean") {
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.id = pfx + "pf-input-" + f.key;
      cb.className = "pf-control";
      cb.checked = Boolean(f.default);
      control = el("div", "pf-field pf-field--inline");
      control.appendChild(cb);
    } else if (f.widget === "json" || f.type === "object" || f.type === "array") {
      const ta = document.createElement("textarea");
      ta.id = pfx + "pf-input-" + f.key;
      ta.className = "pf-control mono";
      ta.rows = Math.min(14, 5 + (String(f.key).length % 4));
      ta.placeholder = "JSON";
      if (f.default != null) {
        try {
          ta.value =
            typeof f.default === "string" ? f.default : JSON.stringify(f.default, null, 2);
        } catch (_e) {
          ta.value = "";
        }
      }
      control = el("div", "pf-field");
      control.appendChild(ta);
    } else {
      const inp = document.createElement("input");
      inp.id = pfx + "pf-input-" + f.key;
      inp.className = "pf-control";
      inp.type = f.type === "integer" || f.type === "number" ? "number" : "text";
      if (f.minimum != null) inp.min = String(f.minimum);
      if (f.maximum != null) inp.max = String(f.maximum);
      if (f.step != null) inp.step = String(f.step);
      if (f.default != null && f.default !== "" && f.default !== null) inp.value = String(f.default);
      control = el("div", "pf-field");
      control.appendChild(inp);
    }

    if (f.description) {
      const hint = el("p", "muted small pf-hint", f.description);
      row.appendChild(lab);
      row.appendChild(control);
      row.appendChild(hint);
    } else {
      row.appendChild(lab);
      row.appendChild(control);
    }
    return row;
  }

  function renderFieldsRoot(root, fields, modelPresets, idPrefix) {
    if (!root) return;
    const pfx = idPrefix || "";
    root.innerHTML = "";
    (fields || []).forEach(function (f) {
      root.appendChild(renderField(f, modelPresets, pfx));
    });
  }

  function collectPayload(metaFields, idPrefix) {
    const pfx = idPrefix || "";
    const payload = {};
    for (let i = 0; i < metaFields.length; i++) {
      const f = metaFields[i];
      let v;
      const wrap = document.getElementById(pfx + "pf-" + f.key);
      const byId = document.getElementById(pfx + "pf-input-" + f.key);

      if (f.widget === "model_select" || (f.key === "model" && wrap && wrap.querySelector("[data-pf-model-select]"))) {
        const sel = wrap.querySelector("[data-pf-model-select]");
        const cust = wrap.querySelector("[data-pf-model-custom]");
        v = sel.value === "__custom__" ? (cust.value || "").trim() : sel.value;
      } else if (f.enum && wrap && wrap.querySelector("select")) {
        v = wrap.querySelector("select").value;
      } else if (byId) {
        if (byId.type === "checkbox") {
          payload[f.key] = byId.checked;
          continue;
        }
        if (f.widget === "json" || f.type === "object" || f.type === "array") {
          const raw = byId.value.trim();
          if (!raw) {
            v = undefined;
          } else {
            try {
              v = JSON.parse(raw);
            } catch (_e) {
              throw new Error("Invalid JSON for field: " + f.key);
            }
          }
        } else v = byId.value;
      } else continue;

      if (v === "" || v === undefined) {
        if (f.required) throw new Error("Required: " + (f.title || f.key));
        if (f.nullable && (v === "" || v === undefined)) continue;
        continue;
      }

      if (f.type === "integer") {
        const n = parseInt(String(v), 10);
        if (Number.isNaN(n)) throw new Error("Not an integer: " + f.key);
        payload[f.key] = n;
      } else if (f.type === "number") {
        const n = parseFloat(String(v));
        if (Number.isNaN(n)) throw new Error("Not a number: " + f.key);
        payload[f.key] = n;
      } else {
        payload[f.key] = v;
      }
    }
    return payload;
  }

  global.ChutesPlaygroundFields = {
    renderFieldsRoot: renderFieldsRoot,
    collectPayload: collectPayload,
  };
})(typeof window !== "undefined" ? window : globalThis);
