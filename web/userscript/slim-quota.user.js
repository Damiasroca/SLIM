// ==UserScript==
// @name         SLIM quota
// @namespace    https://github.com/Damiasroca/SLIM
// @version      1.1.0
// @description  Auto-show Stena Line captive-portal quota on the portal page, refreshing periodically.
// @author       Damiasroca
// @match        https://internet.stenaline.com/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  var API = "https://internet.stenaline.com/portal_api.php";
  var ID = "slim-quota-overlay";
  // How often to re-check quota. 60000 = every minute, 120000 = every two.
  // Each tick is one small POST to the portal; keep it modest to save quota.
  var REFRESH_MS = 120000;

  var stopped = false;
  var inFlight = false;
  var timer = null;

  function mb(b) {
    var n = Number(b);
    if (!isFinite(n)) return "?";
    return (n / 1048576).toFixed(1) + " MB";
  }

  function row(label, value, warn) {
    var color = warn ? "#fbbf24" : "#eaeaea";
    return (
      '<div style="display:flex;justify-content:space-between;gap:12px;padding:2px 0">' +
      '<span style="color:#a0a0a0">' + label + "</span>" +
      '<span style="font-weight:600;color:' + color + '">' + value + "</span>" +
      "</div>"
    );
  }

  function section(text) {
    return (
      '<div style="margin:10px 0 4px;font-size:11px;letter-spacing:.05em;text-transform:uppercase;font-weight:700;color:#4ade80">' +
      text +
      "</div>"
    );
  }

  function timeLeft(ts) {
    var s = Math.max(0, Number(ts) - Date.now() / 1000);
    var d = Math.floor(s / 86400);
    var h = Math.floor((s % 86400) / 3600);
    var m = Math.floor((s % 3600) / 60);
    return d + "d " + h + "h " + m + "m";
  }

  function pad2(n) { return n < 10 ? "0" + n : "" + n; }

  function updatedFooter() {
    var now = new Date();
    return (
      '<div style="margin-top:8px;font-size:11px;color:#a0a0a0;display:flex;justify-content:space-between">' +
      "<span>Updated " + pad2(now.getHours()) + ":" + pad2(now.getMinutes()) + ":" + pad2(now.getSeconds()) + "</span>" +
      "<span>Every " + (REFRESH_MS / 1000) + "s</span>" +
      "</div>"
    );
  }

  function removeCard() {
    var el = document.getElementById(ID);
    if (el) el.remove();
  }

  function ensureBox() {
    var el = document.getElementById(ID);
    if (el) return el;
    el = document.createElement("div");
    el.id = ID;
    el.style.cssText = [
      "position:fixed",
      "top:16px",
      "right:16px",
      "z-index:2147483647",
      "max-width:320px",
      "min-width:260px",
      "padding:14px 34px 14px 16px",
      "background:#16213e",
      "color:#eaeaea",
      'font:14px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
      "border:1px solid #2a2a4a",
      "border-radius:12px",
      "box-shadow:0 10px 30px rgba(0,0,0,0.4)"
    ].join(";");
    var content = document.createElement("div");
    content.setAttribute("data-slim-content", "");
    el.appendChild(content);
    var close = document.createElement("button");
    close.textContent = "\u00d7";
    close.style.cssText =
      "position:absolute;top:4px;right:8px;background:transparent;border:none;color:#a0a0a0;font-size:22px;line-height:1;cursor:pointer";
    close.onclick = function () {
      stopped = true;
      if (timer) { clearInterval(timer); timer = null; }
      el.remove();
    };
    el.appendChild(close);
    document.body.appendChild(el);
    return el;
  }

  function setContent(html) {
    var el = ensureBox();
    var slot = el.querySelector("[data-slim-content]");
    if (slot) slot.innerHTML = html;
  }

  function renderConnected(u) {
    var c = u.consumedData || {};
    var dl = Number((c.download && c.download.value) || 0);
    var up = Number((c.upload && c.upload.value) || 0);
    var quotaHtml = "";
    var extra = c.extra && c.extra.value;
    if (Array.isArray(extra)) {
      var q = null;
      for (var i = 0; i < extra.length; i++) {
        if (extra[i] && extra[i].isSumQuota && extra[i].isDisconnectQuota) { q = extra[i]; break; }
      }
      if (q) {
        var t = Number(q.total && q.total.upload);
        var a = Number(q.available && q.available.upload);
        if (isFinite(t) && isFinite(a)) {
          var used = t - a;
          var pct = t > 0 ? (used / t) * 100 : 0;
          quotaHtml =
            section("Quota") +
            row("Total", mb(t)) +
            row("Remaining", mb(a)) +
            row("Used", mb(used) + " (" + pct.toFixed(1) + "%)", pct > 80);
        }
      }
    }
    var renew = Number((c.renewTimestamp && c.renewTimestamp.value) || 0);
    var name = (u.login && u.login.value) || "Connected";
    setContent(
      '<div style="font-weight:700;color:#4361ee;margin-bottom:6px">' + name + "</div>" +
      section("Data usage") +
      row("Download", mb(dl)) +
      row("Upload", mb(up)) +
      row("Total", mb(dl + up)) +
      quotaHtml +
      (renew
        ? section("Renewal") +
          row("In", timeLeft(renew)) +
          row("Date", new Date(renew * 1000).toLocaleString())
        : "") +
      updatedFooter()
    );
  }

  function renderQuotaReached(ev) {
    var total = Number(ev.consumedUp || 0) + Number(ev.consumedDown || 0);
    setContent(
      '<div style="font-weight:700;color:#f87171;margin-bottom:6px">Quota reached</div>' +
      row("Download", mb(ev.consumedDown)) +
      row("Upload", mb(ev.consumedUp)) +
      row("Total", mb(total), true) +
      (ev.thresoldUp ? row("Limit", mb(ev.thresoldUp)) : "") +
      (ev.renewTimeStamp ? row("Renewal in", timeLeft(ev.renewTimeStamp)) : "") +
      updatedFooter()
    );
  }

  function tick() {
    if (stopped || inFlight) return;
    // Skip work when the tab is hidden; refresh will resume via
    // visibilitychange below when the user comes back.
    if (document.visibilityState === "hidden") return;
    inFlight = true;
    fetch(API, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "action=init&free_urls=",
      credentials: "include"
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.error && data.error.code === "error_logon_volume-quota-reached-detail") {
          renderQuotaReached(data.error.value || {});
          return;
        }
        var u = (data && data.user) || {};
        if (u.isConnected) {
          renderConnected(u);
        } else {
          // Logged out (either manually via portal or session expired).
          // Hide the card but keep polling so we re-appear on re-login.
          removeCard();
        }
      })
      .catch(function (e) {
        // Silent on network hiccups so the overlay is not spammed with
        // errors during roaming / captive-portal weirdness.
        if (window.console && console.debug) console.debug("[SLIM] refresh failed:", e);
      })
      .finally(function () {
        inFlight = false;
      });
  }

  tick();
  timer = setInterval(tick, REFRESH_MS);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") tick();
  });
})();
