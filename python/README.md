# SLIM — Stena Line Internet Monitor

A small desktop GUI (Tkinter) for connecting to the **Stena Line** onboard
captive-portal internet and monitoring connection quality. It handles portal
authentication, lets you save reusable login profiles, logs network latency
over time, and can flush the system DNS cache to help recover flaky
connections.

> On the Stena Line captive portal the **username and password are the same**.

## Features

- One-click authenticate / disconnect against the captive portal
- Saved login profiles (stored locally in `profiles.json`)
- Network quality logging (TCP latency) to `network_quality.csv`
- Latency-by-hour heatmap and history chart
- Light / dark theme (remembered in `config.json`)
- DNS cache flush helper (Windows / macOS)

## Requirements

- Python 3.10+ (`tkinter` ships with the standard CPython installer)
- See [`requirements.txt`](requirements.txt) for third-party packages

## Setup

```bash
# Create and activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
python stena_internet_gui.py
```

## Configuration & data files

These files are created at runtime and are **git-ignored** (they may contain
your credentials):

| File | Purpose |
| --- | --- |
| `profiles.json` | Saved login profiles. Copy `profiles.example.json` to get the format. |
| `config.json` | UI preferences (e.g. theme). |
| `network_quality.csv` | Logged latency samples. |

## Building a standalone executable

The project ships a PyInstaller spec file that bundles SSL certificates:

```bash
pyinstaller StenaInternetMonitor.spec
```

The executable (`SLIM.exe`) is written to `dist/`.

## Project layout

```
stena_internet_gui.py          # Main application
StenaInternetMonitor.spec      # PyInstaller build spec
icon.ico                       # Application icon
profiles.example.json          # Example profile format
requirements.txt
```

## Disclaimer

This is an unofficial tool and is not affiliated with Stena Line. Use it in
accordance with the network's terms of service.
