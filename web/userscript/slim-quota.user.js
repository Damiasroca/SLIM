// ==UserScript==
// @name         SLIM quota
// @namespace    https://github.com/Damiasroca/SLIM
// @version      1.0.0
// @description  Auto-show Stena Line captive-portal quota on the portal page.
// @author       Damiasroca
// @match        https://internet.stenaline.com/*
// @run-at       document-idle
// @grant        none
// ==/UserScript==

(function () {
  "use strict";

  var API = "https://internet.stenaline.com/portal_api.php";
  var ID = "slim-quota-overlay";

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

  function mountBox() {
    var prev = document.getElementById(ID);
    if (prev) prev.remove();
    var box = document.createElement("div");
    box.id = ID;
    box.style.cssText = [
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
    var close = document.createElement("button");
    close.textContent = "\u00d7";
    close.style.cssText =
      "position:absolute;top:4px;right:8px;background:transparent;border:none;color:#a0a0a0;font-size:22px;line-height:1;cursor:pointer";
    close.onclick = function () { box.remove(); };
    document.body.appendChild(box);
    return { box: box, close: close };
  }

  function renderConnected(u) {
    var mounted = mountBox();
    var box = mounted.box, close = mounted.close;
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
    box.innerHTML =
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
        : "");
    box.appendChild(close);
  }

  function renderQuotaReached(ev) {
    var mounted = mountBox();
    var box = mounted.box, close = mounted.close;
    var total = Number(ev.consumedUp || 0) + Number(ev.consumedDown || 0);
    box.innerHTML =
      '<div style="font-weight:700;color:#f87171;margin-bottom:6px">Quota reached</div>' +
      row("Download", mb(ev.consumedDown)) +
      row("Upload", mb(ev.consumedUp)) +
      row("Total", mb(total), true) +
      (ev.thresoldUp ? row("Limit", mb(ev.thresoldUp)) : "") +
      (ev.renewTimeStamp ? row("Renewal in", timeLeft(ev.renewTimeStamp)) : "");
    box.appendChild(close);
  }

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
      }
      // Silent when not connected: user is on the login screen, leave the portal UI alone.
    })
    .catch(function (e) {
      // Silent on network errors so the userscript is invisible when off the ship.
      if (window.console && console.debug) console.debug("[SLIM] init failed:", e);
    });
})();
