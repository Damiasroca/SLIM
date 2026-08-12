# SLIM quota userscript

Auto-shows the quota overlay every time you load
`https://internet.stenaline.com/*`. Silent when you're not logged in
(so the portal's own login UI is undisturbed) and silent on network
errors (so it doesn't complain when you happen to visit the URL off
the ship).

## File

- [`slim-quota.user.js`](slim-quota.user.js) — the userscript.

## Install

You need a userscript manager. One-time setup per browser.

### Desktop Chrome / Edge / Brave / Arc

1. Install **Tampermonkey** (free) or **Violentmonkey** (free, open source) from the browser's extension store.
2. Open `slim-quota.user.js` in a new tab (raw view if hosted on GitHub).
3. The manager will offer to install it. Confirm.

### Desktop Firefox

1. Install **Violentmonkey**, **Greasemonkey**, or **Tampermonkey**.
2. Open `slim-quota.user.js` raw. Confirm install.

### Desktop Safari (macOS)

1. Install **Userscripts** from the Mac App Store (free).
2. Enable it in Safari → Settings → Extensions.
3. Open `slim-quota.user.js` raw. Userscripts will offer to save it.

### iOS Safari

1. Install **Userscripts** from the App Store (free).
2. Open **Settings → Safari → Extensions**, enable **Userscripts**,
   grant it "Allow" for `internet.stenaline.com` (or All Websites).
3. Open `slim-quota.user.js` raw in Safari.
4. Tap the **Userscripts** icon in the Safari toolbar → "Save".
5. Done. Every visit to `internet.stenaline.com` will auto-render the
   quota card once you're connected.

### iOS with Orion browser (alternative)

Orion supports Tampermonkey. Install Tampermonkey inside Orion, then
install the script the same way as desktop Chrome.

### Android Firefox

1. Install **Tampermonkey** or **Violentmonkey** add-on.
2. Open `slim-quota.user.js` raw. Confirm install.

### Android Chrome

Chrome for Android does **not** support extensions. Use Firefox for
Android, Kiwi Browser (Chromium with extension support), or Samsung
Internet with the Tampermonkey extension.

## Behaviour

| State | What you see |
| --- | --- |
| On ship Wi-Fi, connected | Floating quota card, top-right, auto-refreshing |
| Quota reached | Red "Quota reached" card with renewal countdown |
| On portal page but not logged in yet | Nothing (silent) |
| Log out via the portal while the card is up | Card disappears; polling continues so it re-appears on re-login |
| Off ship / no network | Nothing (silent, `console.debug` line) |

The card includes an "Updated HH:MM:SS" timestamp in its footer so you
can see it's alive.

Tap the `×` in the corner to dismiss the card **and stop polling** for
the rest of the page's life. Reload the page to restart.

## Refresh interval

Auto-refresh defaults to **every 2 minutes**. Each tick is one small
POST to the portal; keep it modest so you don't burn quota on the
overlay itself.

To change it, edit this line near the top of
[`slim-quota.user.js`](slim-quota.user.js):

```js
var REFRESH_MS = 120000;
```

- `60000`  — every minute
- `120000` — every two minutes (default)
- `300000` — every five minutes

Save, bump `@version` if you want your manager to prompt for an update,
and reload the portal page. When the tab is hidden the tick is skipped;
when you come back to the tab it fetches immediately (`visibilitychange`
handler).

## Editing / updating

Change [`slim-quota.user.js`](slim-quota.user.js) and bump the `@version`
line. Userscript managers will auto-detect the newer version when the
file is fetched from a URL, or you can re-import it manually.
