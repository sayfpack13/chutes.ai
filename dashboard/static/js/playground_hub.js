/* global document, window, fetch */

(function () {
  var CATALOG_URL = "/api/playground/catalog";

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function encodeQueryValue(s) {
    return encodeURIComponent(String(s || ""));
  }

  function render(groups) {
    var root = document.getElementById("pg-hub-root");
    if (!root) return;
    if (!groups || !groups.length) {
      root.innerHTML =
        "<p class='muted small'>No chutes with a guessable base URL on this page. Try <a href='/platform/advanced'>advanced tools</a> to page or filter.</p>";
      return;
    }
    var html = "";
    groups.forEach(function (g) {
      var chutes = g.chutes || [];
      if (!chutes.length) return;
      html += "<details class='playground-catalog__group' open>";
      html +=
        "<summary class='playground-catalog__summary'><strong>" +
        escapeHtml(g.label || g.id) +
        "</strong> <span class='muted small'>(" +
        chutes.length +
        ")</span></summary>";
      html += "<ul class='playground-catalog__list'>";
      chutes.forEach(function (c) {
        var name = escapeHtml(String(c.name || ""));
        var url = String(c.base_url || "");
        var tag = c.tagline ? escapeHtml(String(c.tagline).slice(0, 120)) : "";
        var price = c.price_per_hour != null ? "$" + Number(c.price_per_hour).toFixed(2) + "/hr" : "";
        var hot = c.hot ? "<span class='badge badge--hot'>Hot</span>" : "";
        var chuteUrl = "/playground/chute?url=" + encodeQueryValue(url);
        html += "<li class='playground-catalog__item'>";
        html += "<div class='playground-catalog__item-head'>";
        html +=
          "<a class='playground-catalog__name' href=\"" +
          escapeHtml(chuteUrl) +
          "\">" +
          name +
          "</a> ";
        if (hot) html += hot;
        if (price) html += "<span class='muted small'>" + escapeHtml(price) + "</span>";
        html += "</div>";
        if (tag) html += "<p class='muted small playground-catalog__tag'>" + tag + "</p>";
        html += "<div class='playground-catalog__actions'>";
        html +=
          "<a class='btn secondary sm' href=\"" +
          escapeHtml(chuteUrl) +
          "\">Open</a>";
        html += "</div></li>";
      });
      html += "</ul></details>";
    });
    root.innerHTML = html;
  }

  function load() {
    var st = document.getElementById("pg-hub-status");
    var root = document.getElementById("pg-hub-root");
    var typeFilter = document.getElementById("pg-type-filter");
    if (!root) return;
    var typeVal = typeFilter ? typeFilter.value : "";
    var url = CATALOG_URL + "?limit=100&page=0";
    if (typeVal) {
      url += "&chute_type=" + encodeQueryValue(typeVal);
    }
    if (st) {
      st.textContent = typeVal ? "Loading " + typeVal + " chutes…" : "Loading catalog…";
    }
    fetch(url)
      .then(function (res) {
        return res.json().catch(function () {
          return {};
        });
      })
      .then(function (data) {
        if (!data.ok) {
          if (st)
            st.textContent = data.error ? String(data.error) : "Catalog request failed.";
          root.innerHTML = "";
          return;
        }
        if (st) {
          st.innerHTML =
            "Showing " +
            escapeHtml(String(data.total || 0)) +
            " chute(s). Use <a href=\"/platform/advanced\">advanced tools</a> to page or filter.";
        }
        render(data.groups || []);
      })
      .catch(function (e) {
        if (st) st.textContent = String((e && e.message) || e);
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    load();
    var filter = document.getElementById("pg-type-filter");
    if (filter) {
      filter.addEventListener("change", load);
    }
    var btn = document.getElementById("pg-refresh-btn");
    if (btn) {
      btn.addEventListener("click", load);
    }
  });
})();
