# KERRY the FERRY — Internet Monitor

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
