# SLIM Safari bookmarklet (recommended iOS path)

The hosted web app can't work: the portal's `Access-Control-Allow-Origin`
header is hard-coded to `https://internet.stenaline.com`, so any other
origin is blocked from reading its JSON.

**Workaround**: run the code from a Safari bookmark **while viewing the
portal page**. The script then executes at `internet.stenaline.com`
origin, has full CORS access, and paints a small quota overlay on top.

## Files

| File | Purpose |
| --- | --- |
| `slim-quota.js` | Readable source of the bookmarklet |
| `bookmarklet.txt` | Generated pastable `javascript:...` URL |
| `build.py` | Regenerates `bookmarklet.txt` from the source |

## Install on iPhone (Safari)

Safari doesn't let you type a `javascript:` URL directly into a new
bookmark, so you have to create a bookmark then edit its URL.

1. Open any page in Safari and tap Share → **Add Bookmark**. Name it
   `SLIM quota`, save it.
2. Open **Bookmarks** → find `SLIM quota` → **Edit** → tap the URL field.
3. Delete the URL. Paste the contents of [`bookmarklet.txt`](bookmarklet.txt)
   (the whole `javascript:...` string, ~7 KB).
4. Tap **Done**.

## Use it

1. Join the ship's Wi-Fi.
2. Open `https://internet.stenaline.com` in Safari (or wait for the
   captive-portal page to appear).
3. Log in with the portal's own UI if you're not connected yet.
4. Tap the **SLIM quota** bookmark from the address bar or Bookmarks.
5. A floating card appears with usage, quota, and renewal countdown.
   Tap the `×` to dismiss.

## Install on desktop (for testing)

Drag any link to the bookmarks bar, right-click → **Edit**, paste the
`javascript:` URL as the address. Then open `https://internet.stenaline.com`
and click the bookmark.

## Rebuilding after edits

```bash
python web/bookmarklet/build.py
```

That regenerates `bookmarklet.txt` from `slim-quota.js`. No dependencies
beyond Python 3.

## Why not just ship a hosted app?

See [`../probe.html`](../probe.html) — running it on ship Wi-Fi produced:

```
Access to fetch at 'https://internet.stenaline.com/portal_api.php'
from origin 'http://127.0.0.1:5500' has been blocked by CORS policy:
The 'Access-Control-Allow-Origin' header has a value
'https://internet.stenaline.com' that is not equal to the supplied origin.
```

That header is set by the portal and we can't change it. Same-origin
execution (bookmarklet) or a native app / Shortcut are the only paths.
