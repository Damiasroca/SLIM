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
| On ship Wi-Fi, connected | Floating quota card, top-right |
| Quota reached | Red "Quota reached" card with renewal countdown |
| On portal page but not logged in yet | Nothing (silent) |
| Off ship / no network | Nothing (silent, debug log only) |

Tap the `×` in the card corner to dismiss. Reload the page to re-check.

## Editing / updating

Change [`slim-quota.user.js`](slim-quota.user.js) and bump the `@version`
line. Userscript managers will auto-detect the newer version when the
file is fetched from a URL, or you can re-import it manually.
