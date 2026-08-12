# Stena Line — Internet Monitor

Companion tools for the **Stena Line** onboard captive-portal Wi-Fi: monitor
your data quota, save login profiles, log connection quality, and connect/
disconnect without juggling the portal web UI.

> On the Stena captive portal the **username and password are the same**.

## Downloads

Pre-built binaries are available on the [Releases](../../releases) page:

| Platform | File |
|----------|------|
| Windows  | `SLIM-vX.Y.Z-windows.exe` |
| Android  | `SLIM-vX.Y.Z-android.apk` |

## Repository layout

```
SLIM/
├── python/    Desktop tkinter app (Windows-first, packaged via PyInstaller)
├── maui/      .NET MAUI cross-platform app (Android + Windows)
├── web/       Bookmarklet + userscript + iOS Shortcut for iPhone / iPad
├── scripts/   Build and release automation
├── LICENSE
└── README.md  (this file)
```

The two app codebases are **independent implementations** that share design
intent and the same captive-portal API. Pick whichever one matches your target
platform; changes in one do not automatically propagate to the other.

## python/ — desktop Tkinter app

- Run from source: `python stena_internet_gui.py`
- Build a standalone Windows `.exe`: `pyinstaller StenaInternetMonitor.spec`
  (output lands in `python/dist/SLIM.exe`)
- Full setup / features / runtime files described in
  [`python/README.md`](python/README.md).

## maui/ — .NET MAUI cross-platform app

- Open `maui/KerryInternetMonitor.sln` in Visual Studio 2022 with the
  **.NET Multi-platform App UI development** workload installed.
- Build targets: Android (APK) and Windows (MSIX / WinUI).

### Android signing

The Android keystore (`kerry_sign.keystore`) is not included in the repo for
security reasons. To build a signed APK:

1. Generate your own keystore or obtain the original
2. Place it at `maui/kerry_sign.keystore`
3. Set environment variables before building:
   ```bash
   export ANDROID_SIGNING_STORE_PASS=your-keystore-password
   export ANDROID_SIGNING_KEY_PASS=your-key-password
   ```
   Or pass them on the command line:
   ```bash
   dotnet build -p:AndroidSigningStorePass=... -p:AndroidSigningKeyPass=...
   ```

## web/ — Safari / iOS quota overlay

The Python and MAUI apps don't run on iPhone/iPad. For those (and for any
browser you don't want to install a native app on), [`web/`](web/) ships
three tiny helpers that call the same captive-portal API and paint a small
quota card. All three are ~200 lines of JavaScript; no backend, no build
step, no framework.

Before anything: **the Stena portal enforces same-origin CORS**, so a
"real" hosted web app cannot read its JSON. The three options below all
work around that in different ways. If you want to verify the block
yourself, host [`web/probe.html`](web/probe.html) on any static server
(e.g. `python -m http.server`), open it on ship Wi-Fi, tap **POST init**,
and look for the CORS error in the response pane.

### Which option should I pick?

| You are on… | Recommended option |
| --- | --- |
| iPhone / iPad, Safari | Bookmarklet (easiest) or Userscripts app (auto-runs) |
| iPhone / iPad, no browser preference | iOS Shortcut |
| Android with Firefox | Userscript via Tampermonkey / Violentmonkey (auto-runs) |
| Android with Chrome / Brave / Edge / Samsung | Bookmarklet with address-bar workaround |
| Desktop Chrome / Edge / Brave / Firefox / Safari | Userscript via Tampermonkey / Violentmonkey (auto-runs) |

You only need one of them working — but they can coexist.

---

### Option 1 — Safari bookmarklet (lowest-friction on iPhone)

A `javascript:` bookmark you tap while viewing the portal page. Because it
runs at `internet.stenaline.com` origin, CORS is not an issue. Renders a
floating card with usage / quota / renewal, then goes away when you tap
the `×`.

**Install on iPhone (Safari):**

1. Open any website in Safari. Tap **Share** → **Add Bookmark**. Name it
   `SLIM quota`. Save.
2. Tap the Bookmarks icon (open book) → find `SLIM quota` → **Edit**.
3. Tap the URL field, delete its contents, and paste the entire content of
   [`web/bookmarklet/bookmarklet.txt`](web/bookmarklet/bookmarklet.txt).
   It's a single line starting with `javascript:…`, ~7 KB long.
4. Tap **Done**.

**Use it:**

1. Join ship Wi-Fi.
2. Open `https://internet.stenaline.com` in Safari and log in via the
   portal if you're not already.
3. Open Bookmarks → tap **SLIM quota**.
4. A floating card appears in the top-right with download, upload,
   used / remaining quota, and a renewal countdown. Tap `×` to dismiss.

**Install on desktop (Chrome / Edge / Brave / Firefox / Safari):**

1. Drag any link onto the bookmarks bar to create a bookmark.
2. Right-click it → **Edit** (or "Edit URL").
3. Paste the whole `javascript:…` string from
   [`web/bookmarklet/bookmarklet.txt`](web/bookmarklet/bookmarklet.txt) as
   the URL. Save.
4. On ship Wi-Fi, open the portal page and click the bookmark.

**Install on Android:**

- **Firefox / Samsung Internet** — save as bookmark, tap it, works.
- **Chrome / Brave / Edge** — save the bookmark, then to run it, type its
  name (e.g. `SLIM`) in the address bar and tap the suggestion. Tapping
  bookmarks directly does not execute `javascript:` URLs in Chromium on
  Android.

**Rebuilding after edits:**

The readable source is [`web/bookmarklet/slim-quota.js`](web/bookmarklet/slim-quota.js).
After editing it, regenerate the pastable URL:

```bash
python web/bookmarklet/build.py
```

That writes a fresh `bookmarklet.txt` next to it. Pure stdlib, no
dependencies.

---

### Option 2 — Userscript (best UX, auto-runs on portal page)

Same code as the bookmarklet, but registered as a userscript so it fires
automatically every time you load `internet.stenaline.com`. It stays
silent when you're not logged in — the portal's own UI is undisturbed —
and paints the quota card the moment you're connected.

You need a **userscript manager** first. One-time setup per browser:

**iPhone / iPad (Safari):**

1. Install [Userscripts](https://apps.apple.com/app/userscripts/id1463298887)
   (free) from the App Store.
2. Open **Settings → Safari → Extensions**, enable **Userscripts**, and
   grant it **Allow** for `internet.stenaline.com` (or all websites).
3. Open [`web/userscript/slim-quota.user.js`](web/userscript/slim-quota.user.js)
   raw in Safari (e.g. via GitHub's *Raw* button).
4. Tap the Userscripts icon in Safari's toolbar → **Save**.

**Android (Firefox):**

1. Install Firefox for Android.
2. Add the **Tampermonkey** add-on from
   [addons.mozilla.org](https://addons.mozilla.org/en-US/android/addon/tampermonkey/)
   (or Violentmonkey — either works).
3. Open [`web/userscript/slim-quota.user.js`](web/userscript/slim-quota.user.js)
   raw in Firefox. Tampermonkey will offer to install; confirm.

**Desktop Chrome / Edge / Brave / Firefox / Safari:**

1. Install **Tampermonkey** (free) or **Violentmonkey** (free, OSS) from
   the browser's extension store. On desktop Safari, use the free
   [Userscripts app](https://apps.apple.com/us/app/userscripts/id1463298887)
   from the Mac App Store instead.
2. Open the raw `.user.js` file. The manager offers to install it.
3. Bump `@version` in the file's header when you want managers to prompt
   for an update.

**Behaviour:**

| State | What you see |
| --- | --- |
| On ship Wi-Fi, logged in | Floating quota card, top-right, auto-refreshing every 2 min |
| Quota reached | Red "Quota reached" card with renewal countdown |
| Portal page but not logged in yet | Nothing (silent) |
| Log out via the portal while the card is up | Card disappears; polling continues so it re-appears on re-login |
| Off ship / no network | Nothing (silent; only a `console.debug` line) |

The refresh interval is set at the top of `slim-quota.user.js`
(`var REFRESH_MS = 120000;`). Change it to `60000` for every minute or
`300000` for every five minutes. Ticks are skipped while the tab is
hidden and re-run when it becomes visible again, so the overlay doesn't
burn quota in the background.

Tap `×` to dismiss the card and stop polling. Reload the page to
restart.

---

### Option 3 — iOS Shortcut (no browser needed)

Runs natively via the Apple Shortcuts app, so CORS doesn't apply at all.
This is the most robust fallback if the browser options ever break.

Apple's `.shortcut` binary format is version-sensitive, so instead of
shipping a fragile export we ship precise build steps in
[`web/shortcut/README.md`](web/shortcut/README.md). It walks you through
the ~9 actions needed:

1. Ask for your Stena username.
2. POST `action=init` to the portal.
3. POST `action=authenticate` with the credentials.
4. Parse the returned JSON.
5. Compute used / remaining bytes and renewal time.
6. Show them in a notification.

Once built, it lives on your Home Screen as a normal Shortcut and takes
one tap.

---

### File map

```
web/
├── README.md                     Overview of the trio
├── probe.html                    CORS diagnostic (host it yourself)
├── bookmarklet/
│   ├── README.md                 Detailed install instructions
│   ├── slim-quota.js             Readable source
│   ├── bookmarklet.txt           Generated javascript:… URL to paste
│   └── build.py                  Regenerates bookmarklet.txt from source
├── userscript/
│   ├── README.md                 Per-platform manager install
│   └── slim-quota.user.js        Userscript source
└── shortcut/
    └── README.md                 Steps to build the iOS Shortcut
```

---

## Building releases

A PowerShell script automates building both platforms:

```powershell
# Build both platforms (reads version from source)
.\scripts\build-release.ps1

# Build specific version
.\scripts\build-release.ps1 -Version "1.1.0"

# Build only Python
.\scripts\build-release.ps1 -SkipMaui
```

Output files land in `releases/` with names like:
- `SLIM-v1.0.9-windows.exe`
- `SLIM-v1.0.9-android.apk`

### Creating a GitHub release

```bash
# Tag the version
git tag v1.0.9
git push origin v1.0.9

# Create release with binaries
gh release create v1.0.9 releases/* \
  --title "SLIM v1.0.9" \
  --notes "Release notes here"
```

## Refreshing your MAC address (both apps)

When the ship's portal keeps associating your device with an exhausted
session, randomize your MAC so the portal sees you as new. Both apps surface
a one-tap shortcut to the OS settings page where this lives:

- **Windows**: Settings → Network & Internet → Wi-Fi → your network →
  "Random hardware addresses" (set to *Daily*).
- **Android**: Settings → Wi-Fi → tap your network → Privacy →
  "Use randomized MAC" (set to *Daily* on supported OEMs).

## Disclaimer

Unofficial tool; not affiliated with Stena Line. Use in accordance with the
network's terms of service.
