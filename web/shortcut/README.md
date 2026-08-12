# iOS Shortcut fallback (if CORS blocks the web app)

Use this when [`../probe.html`](../probe.html) shows a CORS failure on ship Wi-Fi.
Shortcuts talk to the portal from the iOS networking stack (no browser CORS).

## What it does

1. Asks for your Stena username (password is the same).
2. POSTs `action=init` then `action=authenticate` to `https://internet.stenaline.com/portal_api.php`.
3. Shows used / remaining quota and renewal time in an alert.

## Build it yourself in Shortcuts (recommended)

Apple’s `.shortcut` files are binary and version-sensitive, so the reliable path is to recreate the flow once:

### Actions

1. **Ask for Input** — Prompt: `Stena username` → store as `Username`
2. **URL** — `https://internet.stenaline.com/portal_api.php`
3. **Get Contents of URL**
   - Method: `POST`
   - Request Body: `Form`
   - Fields:
     - `action` = `init`
     - `free_urls` = *(empty)*
4. **URL** — same as step 2
5. **Get Contents of URL**
   - Method: `POST`
   - Request Body: `Form`
   - Fields (match the desktop / web client):
     - `action` = `authenticate`
     - `switch_package` = `true`
     - `login` = `Username` (variable)
     - `password` = `Username` (variable)
     - `policy_accept` = `true`
     - `private_policy_accept` = `false`
     - `from_ajax` = `true`
     - `wispr_mode` = `false`
6. **Get Dictionary from Input** (the response JSON)
7. **Get Dictionary Value** — `user` → then `consumedData`
8. Compute / display:
   - Download: `consumedData.download.value` (bytes → ÷ 1048576 for MB)
   - Upload: `consumedData.upload.value`
   - Walk `consumedData.extra.value` for the item where `isSumQuota` and `isDisconnectQuota` are true; use `total.upload` and `available.upload`
   - Renewal: `consumedData.renewTimestamp.value` (Unix seconds)
9. **Show Result** / **Show Notification** with used, remaining, and renewal.

### Optional: save username

Use **Get/Set Variable** or the **Data Jar** / **Toolbox Pro** apps if you want a saved profile without retyping.

## Status-only variant

If you only need “am I already connected?”:

1. POST `action=init&free_urls=`
2. Read `user.isConnected`, `user.login.value`, and `user.consumedData` the same way.

## Notes

- Must be on **Stena ship Wi-Fi**.
- If iOS warns about the TLS certificate for `internet.stenaline.com`, open that host once in Safari and continue (same as the official portal).
- This is unofficial and not affiliated with Stena Line.
