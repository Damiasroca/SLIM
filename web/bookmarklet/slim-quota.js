/*
 * SLIM quota bookmarklet
 *
 * Run this from a Safari bookmark WHILE ON the Stena Line captive portal
 * page (https://internet.stenaline.com). Because it executes at that
 * origin, CORS does not apply and we can read portal_api.php responses.
 *
 * Renders a small floating card with usage / quota / renewal. To rebuild
 * the pastable javascript:... URL after editing this file, see README.md
 * in the same folder.
 */
(function () {
  var API = "https://internet.stenaline.com/portal_api.php";
  var ID = "slim-quota-overlay";
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
  box.innerHTML = "<div>SLIM \u00b7 loading\u2026</div>";
  document.body.appendChild(box);

  var close = document.createElement("button");
  close.textContent = "\u00d7";
  close.style.cssText =
    "position:absolute;top:4px;right:8px;background:transparent;border:none;color:#a0a0a0;font-size:22px;line-height:1;cursor:pointer";
  close.onclick = function () { box.remove(); };
  box.appendChild(close);

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

  function render(html) {
    box.innerHTML = html;
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
        var ev = data.error.value || {};
        var total = Number(ev.consumedUp || 0) + Number(ev.consumedDown || 0);
        render(
          '<div style="font-weight:700;color:#f87171;margin-bottom:6px">Quota reached</div>' +
          row("Download", mb(ev.consumedDown)) +
          row("Upload", mb(ev.consumedUp)) +
          row("Total", mb(total), true) +
          (ev.thresoldUp ? row("Limit", mb(ev.thresoldUp)) : "") +
          (ev.renewTimeStamp ? row("Renewal in", timeLeft(ev.renewTimeStamp)) : "")
        );
        return;
      }
      var u = (data && data.user) || {};
      if (!u.isConnected) {
        render(
          '<div style="font-weight:700">Not connected</div>' +
          '<div style="color:#a0a0a0;margin-top:4px">Log in via the portal, then tap the bookmark again.</div>'
        );
        return;
      }
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
      render(
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
          : "")
      );
    })
    .catch(function (e) {
      render(
        '<div style="color:#f87171;font-weight:700">Request failed</div>' +
        '<div style="color:#a0a0a0;margin-top:4px">' +
        String(e) +
        "</div>"
      );
    });
})();
