# web/ — browser-side quota tools for the Stena portal

For platforms where the native apps in [`python/`](../python/) and
[`maui/`](../maui/) don't run (mainly iPhone/iPad), this folder ships three
tiny browser-side tools that talk to the same captive-portal API and show
your quota.

## The CORS constraint (why there's no hosted web app)

The portal returns:

```
Access-Control-Allow-Origin: https://internet.stenaline.com
```

That header is hard-coded to the portal's own origin, so a page hosted
anywhere else (GitHub Pages, a local dev server, `file://`, etc.) can send
the request but **cannot read the JSON response**. The three tools here
all work around that in different ways:

| Tool | Where it runs | How the CORS block is avoided |
| --- | --- | --- |
| [`bookmarklet/`](bookmarklet/) | Injected into the portal page itself | Same-origin execution |
| [`userscript/`](userscript/) | Injected into the portal page by a userscript manager extension | Same-origin execution |
| [`shortcut/`](shortcut/) | Apple Shortcuts app (native, not a browser) | No browser CORS layer |

There's also [`probe.html`](probe.html): a small diagnostic you can host
anywhere to confirm the CORS situation. Run it on ship Wi-Fi and if it ever
reports the portal newly accepts your origin, a "real" hosted web app
becomes viable.

Detailed install steps for each option live in the top-level
[`README.md`](../README.md#web--safari--ios-quota-overlay) of this repo.
