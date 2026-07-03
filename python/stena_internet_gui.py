import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import json
import requests
import urllib3
from datetime import datetime, timedelta
import threading
import sys
import os
import platform
import traceback  # Added for better error handling
import re
import socket
import statistics
import csv
import time
import math
from urllib.parse import urlparse
if platform.system() == 'Windows':
    from subprocess import CREATE_NO_WINDOW

# Primary UI font family (loaded at runtime from bundled TTFs)
UI_FONT = "Stena Sans"

# Modern Theme System
THEMES = {
    "dark": {
        "bg": "#1a1a2e",              # Deep blue-black background
        "bg_secondary": "#16213e",    # Card/panel backgrounds
        "bg_tertiary": "#0f3460",     # Input fields, elevated elements
        "text": "#eaeaea",            # Primary text
        "text_secondary": "#a0a0a0",  # Muted/secondary text
        "accent": "#4361ee",          # Primary accent (blue)
        "success": "#4ade80",         # Green for success
        "warning": "#fbbf24",         # Amber for warnings
        "error": "#f87171",           # Red for errors
        "border": "#2a2a4a",          # Subtle borders
        "button_text": "#ffffff",     # Button text color
    },
    "light": {
        "bg": "#f8fafc",              # Off-white background
        "bg_secondary": "#ffffff",    # Card/panel backgrounds
        "bg_tertiary": "#f1f5f9",     # Input fields, elevated elements
        "text": "#1e293b",            # Primary text
        "text_secondary": "#64748b",  # Muted/secondary text
        "accent": "#3b82f6",          # Primary accent (blue)
        "success": "#22c55e",         # Green for success
        "warning": "#f59e0b",         # Amber for warnings
        "error": "#ef4444",           # Red for errors
        "border": "#e2e8f0",          # Subtle borders
        "button_text": "#ffffff",     # Button text color
    }
}

# Current theme state (will be loaded from config)
current_theme = "dark"

def get_theme():
    """Get the current theme colors"""
    return THEMES[current_theme]

def load_config():
    """Load configuration including theme preference"""
    global current_theme
    try:
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                current_theme = config.get('theme', 'dark')
                if current_theme not in THEMES:
                    current_theme = 'dark'
    except Exception:
        current_theme = 'dark'
    return current_theme

def save_config():
    """Save configuration including theme preference"""
    try:
        config = {'theme': current_theme}
        with open('config.json', 'w') as f:
            json.dump(config, f)
    except Exception as e:
        print(f"[DEBUG] Error saving config: {e}")

# Load config on startup
load_config()

# Legacy COLORS reference for backward compatibility during transition
COLORS = THEMES[current_theme]

# Application version (shown in window title and footer)
APP_VERSION = "1.1.1"

# API Configuration
API_URL = "https://internet.stenaline.com/portal_api.php"
API_ACTIONS = {
    "authenticate": "authenticate",
    "disconnect": "disconnect",
    "init": "init"
}
API_HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01"
}

# Landing page used to replicate the browser captive-portal handshake. Hitting
# this lets the gateway set PHPSESSID and bind the session to this device's
# IP/MAC (the `/NNN/portal/` redirect) before we call `authenticate`.
PORTAL_LANDING_URL = f"{urlparse(API_URL).scheme}://{urlparse(API_URL).hostname}/"

# Retry tuning for the slow authenticate/disconnect round-trip to the ship
# gateway (high-latency satellite link). The connect timeout is generous
# because the first SYN over satellite is frequently dropped.
PORTAL_POST_ATTEMPTS = 4
PORTAL_CONNECT_TIMEOUT = 10
PORTAL_READ_TIMEOUT = 30
# Cold start needs at least two GETs (degraded sets the cookie, then the zoned
# /<zone>/portal/ loads); extra margin covers a dropped SYN in between.
PORTAL_HANDSHAKE_ATTEMPTS = 3

# Network quality monitoring configuration
QUALITY_HOST = urlparse(API_URL).hostname or "internet.stenaline.com"
QUALITY_PORT = 443
QUALITY_CSV = "network_quality.csv"

class ModernTooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)
    
    def show_tooltip(self, event=None):
        # Get widget position
        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        # Create a toplevel window
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        theme = get_theme()
        label = tk.Label(self.tooltip, text=self.text, background=theme["bg_secondary"],
                         foreground=theme["text"], relief="flat", borderwidth=0,
                         font=(UI_FONT, 9, "normal"), padx=8, pady=4,
                         highlightbackground=theme["border"], highlightthickness=1)
        label.pack()
    
    def hide_tooltip(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

class CustomButton(tk.Canvas):
    def __init__(self, parent, text, command, width=120, height=40, bg_color=None, color_key="accent", hover_color=None, radius=8, **kwargs):
        # Store the color key for theme updates
        self.color_key = color_key
        self.command = command
        self.text = text
        self._enabled = True
        self._width = width
        self._height = height
        self._radius = radius
        
        # Get initial color from theme or use provided bg_color
        if bg_color is not None:
            self.bg_color = bg_color
        else:
            self.bg_color = get_theme().get(color_key, get_theme()["accent"])
        
        self.hover_color = hover_color if hover_color else self._lighten_color(self.bg_color, 0.15)
        self.disabled_color = self._lighten_color(self.bg_color, 0.4)
        
        tk.Canvas.__init__(self, parent, width=width, height=height, 
                          bg=get_theme()["bg"], highlightthickness=0, **kwargs)
        
        # Track the minimum width so geometry managers (and the relayout code)
        # can keep the label fully visible.
        self.min_width = width
        
        # Create rounded rectangle button
        self.rect_id = self._create_rounded_rect(0, 0, width, height, radius, fill=self.bg_color, outline="")
        self.text_id = self.create_text(width//2, height//2, text=text, fill=get_theme()["button_text"], font=(UI_FONT, 10, "bold"))
        
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_configure)
    
    def _on_configure(self, event):
        """Redraw the rounded rect + center the label when the canvas resizes."""
        if event.width <= 1 or event.height <= 1:
            return
        self._width = event.width
        self._height = event.height
        # Clamp radius so the rect stays sane at small sizes.
        radius = min(self._radius, event.width // 2, event.height // 2)
        current_fill = self.bg_color if self._enabled else self.disabled_color
        self.delete(self.rect_id)
        self.rect_id = self._create_rounded_rect(
            0, 0, event.width, event.height, radius,
            fill=current_fill, outline=""
        )
        self.coords(self.text_id, event.width // 2, event.height // 2)
        self.tag_raise(self.text_id)

    def _create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Create a rounded rectangle on the canvas"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
            x1 + radius, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
    
    def _lighten_color(self, color, factor=0.2):
        # Convert hex to RGB
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
        
        # Lighten (positive factor) or darken (negative factor)
        if factor > 0:
            r = min(255, int(r + (255 - r) * factor))
            g = min(255, int(g + (255 - g) * factor))
            b = min(255, int(b + (255 - b) * factor))
        else:
            factor = abs(factor)
            r = max(0, int(r * (1 - factor)))
            g = max(0, int(g * (1 - factor)))
            b = max(0, int(b * (1 - factor)))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def update_theme(self):
        """Update button colors based on current theme"""
        theme = get_theme()
        self.bg_color = theme.get(self.color_key, theme["accent"])
        self.hover_color = self._lighten_color(self.bg_color, 0.15)
        self.disabled_color = self._lighten_color(self.bg_color, 0.4)
        
        # Update canvas background
        self.configure(bg=theme["bg"])
        
        if self._enabled:
            self.itemconfig(self.rect_id, fill=self.bg_color)
            self.itemconfig(self.text_id, fill=theme["button_text"])
        else:
            self.itemconfig(self.rect_id, fill=self.disabled_color)
            self.itemconfig(self.text_id, fill=theme["text_secondary"])
    
    def set_enabled(self, enabled):
        """Enable or disable the button with visual feedback"""
        self._enabled = enabled
        theme = get_theme()
        if enabled:
            self.itemconfig(self.rect_id, fill=self.bg_color)
            self.itemconfig(self.text_id, fill=theme["button_text"])
        else:
            self.itemconfig(self.rect_id, fill=self.disabled_color)
            self.itemconfig(self.text_id, fill=theme["text_secondary"])
    
    def is_enabled(self):
        """Check if button is enabled"""
        return self._enabled
    
    def _on_enter(self, event):
        if self._enabled:
            self.itemconfig(self.rect_id, fill=self.hover_color)
    
    def _on_leave(self, event):
        if self._enabled:
            self.itemconfig(self.rect_id, fill=self.bg_color)
        else:
            self.itemconfig(self.rect_id, fill=self.disabled_color)
    
    def _on_click(self, event):
        if self._enabled:
            self.itemconfig(self.rect_id, fill=self._lighten_color(self.bg_color, -0.15))
    
    def _on_release(self, event):
        if self._enabled:
            self.itemconfig(self.rect_id, fill=self.hover_color)
            if self.command:
                self.command()

class CardFrame(tk.Frame):
    """A modern card-style container with subtle border and background"""
    def __init__(self, parent, title=None, **kwargs):
        theme = get_theme()
        super().__init__(parent, bg=theme["bg_secondary"], **kwargs)
        
        self.title = title
        self.title_label = None
        
        # Create inner padding frame
        self.inner = tk.Frame(self, bg=theme["bg_secondary"])
        self.inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
        
        if title:
            self.title_label = tk.Label(
                self.inner, 
                text=title, 
                font=(UI_FONT, 11, "bold"),
                fg=theme["text"],
                bg=theme["bg_secondary"]
            )
            self.title_label.pack(anchor=tk.W, pady=(0, 8))
        
        # Content frame for actual widgets
        self.content = tk.Frame(self.inner, bg=theme["bg_secondary"])
        self.content.pack(fill=tk.BOTH, expand=True)
        
        # Draw border
        self.configure(highlightbackground=theme["border"], highlightthickness=1)
    
    def update_theme(self):
        """Update card colors based on current theme"""
        theme = get_theme()
        self.configure(bg=theme["bg_secondary"], highlightbackground=theme["border"])
        self.inner.configure(bg=theme["bg_secondary"])
        self.content.configure(bg=theme["bg_secondary"])
        if self.title_label:
            self.title_label.configure(fg=theme["text"], bg=theme["bg_secondary"])

class RoundedEntry(tk.Canvas):
    """A modern rounded entry field"""
    def __init__(self, parent, textvariable=None, width=150, height=32, radius=6, show=None, **kwargs):
        theme = get_theme()
        self._width = width
        self._height = height
        self._radius = radius
        self._show = show
        self._textvariable = textvariable if textvariable else tk.StringVar()
        
        tk.Canvas.__init__(self, parent, width=width, height=height, 
                          bg=theme["bg_secondary"], highlightthickness=0, **kwargs)
        
        # Draw rounded background
        self.bg_id = self._create_rounded_rect(0, 0, width, height, radius, 
                                                fill=theme["bg_tertiary"], outline=theme["border"])
        
        # Create the actual entry widget
        entry_width = int((width - 16) / 8)  # Approximate character width
        self.entry = tk.Entry(self, textvariable=self._textvariable, 
                              font=(UI_FONT, 10),
                              bg=theme["bg_tertiary"], fg=theme["text"],
                              insertbackground=theme["text"],
                              relief=tk.FLAT, bd=0,
                              highlightthickness=0,
                              width=entry_width)
        if show:
            self.entry.configure(show=show)
        
        # Place entry inside the canvas
        self.entry_window = self.create_window(8, height//2, window=self.entry, anchor=tk.W)
        
        # Bind focus events for highlight effect
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
    
    def _create_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs):
        """Create a rounded rectangle"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
            x1 + radius, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
    
    def _on_focus_in(self, event=None):
        theme = get_theme()
        self.itemconfig(self.bg_id, outline=theme["accent"])
    
    def _on_focus_out(self, event=None):
        theme = get_theme()
        self.itemconfig(self.bg_id, outline=theme["border"])
    
    def get(self):
        return self._textvariable.get()
    
    def set(self, value):
        self._textvariable.set(value)
    
    def update_theme(self):
        """Update entry colors based on current theme"""
        theme = get_theme()
        self.configure(bg=theme["bg_secondary"])
        self.itemconfig(self.bg_id, fill=theme["bg_tertiary"], outline=theme["border"])
        self.entry.configure(bg=theme["bg_tertiary"], fg=theme["text"], insertbackground=theme["text"])


class QuotaGauge(tk.Canvas):
    """Semicircle (fuel-gauge style) widget showing data usage versus a fixed
    1 GB reference scale.

    Drawn flat with Canvas primitives so it inherits the app's dark/light
    theme. If usage exceeds the scale, the dial turns red and the secondary
    label shows the overflow amount (e.g. "+128 MB over").
    """

    GAUGE_MAX_BYTES = 1024 * 1024 * 1024  # 1 GB reference scale

    def __init__(self, parent, used_bytes=0, max_bytes=None, width=240, height=200):
        theme = get_theme()
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=theme["bg_secondary"],
            highlightthickness=0,
            bd=0,
        )
        self._used = max(0, used_bytes)
        self._max = max_bytes if max_bytes else self.GAUGE_MAX_BYTES
        # NOTE: do NOT use self._w / self._h — `_w` is reserved by Tk for the
        # widget's command path; overwriting it breaks every later Tk call.
        self._canvas_w = width
        self._canvas_h = height
        self._draw()

    def set_value(self, used_bytes, max_bytes=None):
        self._used = max(0, used_bytes)
        if max_bytes:
            self._max = max_bytes
        self._draw()

    def update_theme(self):
        theme = get_theme()
        self.configure(bg=theme["bg_secondary"])
        self._draw()

    def _draw(self):
        self.delete("all")
        theme = get_theme()

        cx = self._canvas_w // 2
        cy = self._canvas_h - 50  # baseline of the dial, leaving room for text
        outer_r = min(cx - 20, self._canvas_h - 80)
        inner_r = outer_r - 24

        fraction = self._used / self._max if self._max else 0
        clamped = min(fraction, 1.0)
        over_limit = fraction > 1.0

        # Traffic-light color: green / yellow / red.
        if over_limit or clamped >= 0.85:
            fill_color = theme["error"]
        elif clamped >= 0.6:
            fill_color = theme["warning"]
        else:
            fill_color = theme["success"]

        # Title at the top so the gauge is clearly labeled
        self.create_text(
            cx, 14, text="QUOTA",
            font=(UI_FONT, 10, "bold"),
            fill=theme["success"],
        )

        # Empty arc track — uses bg_tertiary so it stays clearly visible against
        # the canvas (bg_secondary). This was the "invisible" bug previously.
        self.create_arc(
            cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r,
            start=0, extent=180,
            outline="", fill=theme["bg_tertiary"], style="pieslice",
        )

        # Filled portion of the dial
        if clamped > 0:
            filled_extent = 180 * clamped
            self.create_arc(
                cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r,
                start=180 - filled_extent, extent=filled_extent,
                outline="", fill=fill_color, style="pieslice",
            )

        # Inner cutout (same color as the canvas bg) turns the pieslices into a ring.
        self.create_arc(
            cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r,
            start=0, extent=180,
            outline="", fill=theme["bg_secondary"], style="pieslice",
        )

        # Tick marks at 0 / 25 / 50 / 75 / 100 %
        for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
            angle = math.radians(180 - 180 * tick)
            x1 = cx + math.cos(angle) * (outer_r + 1)
            y1 = cy - math.sin(angle) * (outer_r + 1)
            x2 = cx + math.cos(angle) * (outer_r + 7)
            y2 = cy - math.sin(angle) * (outer_r + 7)
            self.create_line(x1, y1, x2, y2, fill=theme["text_secondary"], width=1)

        # Center hub
        self.create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                         fill=theme["text_secondary"], outline="")

        used_mb = self._used / (1024 * 1024)
        max_mb = self._max / (1024 * 1024)
        pct = clamped * 100

        # Primary label (used / max in MB)
        self.create_text(
            cx, cy - outer_r // 2,
            text=f"{used_mb:.0f} MB / {max_mb:.0f} MB",
            font=(UI_FONT, 11, "bold"),
            fill=theme["text"],
        )

        # Secondary label: percent, or overflow if past 1 GB
        if over_limit:
            sub_text = f"+{used_mb - max_mb:.0f} MB over"
            sub_color = theme["error"]
        else:
            sub_text = f"{pct:.0f}%"
            sub_color = theme["text_secondary"]
        self.create_text(
            cx, cy + 16,
            text=sub_text,
            font=(UI_FONT, 10, "bold"),
            fill=sub_color,
        )

        # End-of-scale labels
        self.create_text(
            cx - outer_r, cy + 8, text="0",
            font=(UI_FONT, 8), fill=theme["text_secondary"], anchor="n",
        )
        self.create_text(
            cx + outer_r, cy + 8, text=f"{max_mb:.0f} MB",
            font=(UI_FONT, 8), fill=theme["text_secondary"], anchor="n",
        )


class VPNDetector:
    """Windows-only heuristic VPN detection (pure stdlib).

    Single signal: an adapter that currently has a Default Gateway has a
    VPN-ish name or description. The earlier portal-IP sanity check was
    dropped because it false-positives whenever the host isn't on the
    captive-portal subnet (e.g. off-ferry testing).
    """

    _KEYWORDS = (
        "tap-", "tap windows", "tap adapter", "tun ", "tun adapter",
        "tunnel adapter", "wireguard", "openvpn", "nordlynx", "nordvpn",
        "protonvpn", "proton vpn", "expressvpn", "mullvad", "cisco anyconnect",
        "anyconnect", "pulse secure", "forticlient", "fortinet ssl",
        "checkpoint", "sonicwall", "globalprotect", "zerotier", "tailscale",
        "wan miniport (ikev2)", "wan miniport (sstp)", "wan miniport (l2tp)",
        "wan miniport (pptp)", "ppp adapter",
    )

    @classmethod
    def check(cls):
        """Return (is_vpn_active: bool, reason: str | None)."""
        if platform.system() != "Windows":
            return (False, None)

        for ad in cls._ipconfig_adapters():
            if not ad["gateway"]:
                continue
            haystack = f"{ad['name']} {ad['description']}".lower()
            for kw in cls._KEYWORDS:
                if kw in haystack:
                    return (True, f"VPN adapter owns the default route: {ad['name']}")

        return (False, None)

    @staticmethod
    def _ipconfig_adapters():
        try:
            flags = CREATE_NO_WINDOW if platform.system() == "Windows" else 0
            out = subprocess.check_output(
                ["ipconfig", "/all"], stderr=subprocess.STDOUT,
                timeout=5, creationflags=flags,
            ).decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[DEBUG] VPN detect: ipconfig failed: {e}")
            return []

        adapters = []
        current = None
        for raw in out.splitlines():
            line = raw.rstrip()
            if line and not line[0].isspace() and " adapter " in line.lower() and line.endswith(":"):
                if current:
                    adapters.append(current)
                current = {"name": line[:-1].strip(), "description": "", "gateway": ""}
                continue
            if current is None:
                continue
            stripped = line.strip()
            if ":" not in stripped:
                continue
            key, _, value = stripped.partition(":")
            key = key.strip().rstrip(".").strip()
            value = value.strip()
            if key.lower().startswith("description"):
                current["description"] = value
            elif key.lower().startswith("default gateway") and value:
                current["gateway"] = value
        if current:
            adapters.append(current)
        return adapters


class NetworkQualityLogger:
    """Background sampler that measures TCP-connect latency, jitter and loss.

    Uses raw TCP connects (no payload) so it reflects how slow it is to even
    reach the portal/gateway without consuming meaningful quota. Pure stdlib,
    so it bundles cleanly with PyInstaller.
    """
    def __init__(self, host, port, csv_path, interval=120, samples=4, timeout=8.0):
        self.host = host
        self.port = port
        self.csv_path = csv_path
        self.interval = interval
        self.samples = samples
        self.timeout = timeout
        self._thread = None
        self._stop = threading.Event()
        self.on_update = None  # callback(record), invoked from the worker thread
        self.last_record = None
        self.vpn_reason = None  # set by _run when a VPN is detected; clears otherwise

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        if self.is_running():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            vpn_active, vpn_reason = VPNDetector.check()
            self.vpn_reason = vpn_reason if vpn_active else None
            if vpn_active:
                # Pause sampling: a VPN distorts both DNS and routing, so the
                # numbers would be lies. Don't write to CSV either.
                cb = self.on_update
                if cb:
                    try:
                        cb(None)
                    except Exception as e:
                        print(f"[DEBUG] NQ callback error: {e}")
                self._stop.wait(self.interval)
                continue

            record = self._measure()
            self.last_record = record
            try:
                self._append_csv(record)
            except Exception as e:
                print(f"[DEBUG] NQ csv append error: {e}")
            cb = self.on_update
            if cb:
                try:
                    cb(record)
                except Exception as e:
                    print(f"[DEBUG] NQ callback error: {e}")
            self._stop.wait(self.interval)

    def _tcp_latency(self):
        """Return the TCP connect time in ms, or None on failure/timeout."""
        start = time.perf_counter()
        try:
            sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            sock.close()
            return (time.perf_counter() - start) * 1000.0
        except Exception:
            return None

    def _measure(self):
        latencies = []
        failures = 0
        for i in range(self.samples):
            if self._stop.is_set():
                break
            ms = self._tcp_latency()
            if ms is None:
                failures += 1
            else:
                latencies.append(ms)
            if i < self.samples - 1:
                self._stop.wait(0.5)  # small gap between samples
        total = failures + len(latencies)
        loss = (failures / total * 100.0) if total else 100.0
        if latencies:
            avg = sum(latencies) / len(latencies)
            lmin = min(latencies)
            lmax = max(latencies)
            jitter = statistics.pstdev(latencies) if len(latencies) > 1 else 0.0
        else:
            avg = lmin = lmax = jitter = None
        return {
            "timestamp": datetime.now(),
            "host": self.host,
            "avg": avg,
            "min": lmin,
            "max": lmax,
            "jitter": jitter,
            "loss": loss,
        }

    def _append_csv(self, r):
        exists = os.path.isfile(self.csv_path)
        with open(self.csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow([
                    "Timestamp", "Host", "LatencyAvg(ms)", "LatencyMin(ms)",
                    "LatencyMax(ms)", "Jitter(ms)", "Loss(%)"
                ])
            def fmt(x):
                return "" if x is None else f"{x:.1f}"
            writer.writerow([
                r["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                r["host"], fmt(r["avg"]), fmt(r["min"]), fmt(r["max"]),
                fmt(r["jitter"]), f"{r['loss']:.0f}",
            ])


class NetworkQualityPanel(tk.Frame):
    """Embedded panel that controls the logger and visualises quality by hour."""
    CELL_W = 26
    CELL_H = 40
    GAP = 2
    PAD_X = 16
    PAD_TOP = 8

    def __init__(self, parent, app):
        self.app = app
        self.logger = app.quality_logger
        theme = get_theme()
        super().__init__(parent, bg=theme["bg"])
        self._hourly = {}
        self._points = []

        self._build_ui()
        self.logger.on_update = self._on_logger_update
        self._refresh_controls()
        self.update_heatmap()
        self._reload_points()
        self.update_chart()

    def rebuild(self):
        """Tear down and rebuild the panel (used on theme change)."""
        for widget in self.winfo_children():
            widget.destroy()
        self.configure(bg=get_theme()["bg"])
        self._build_ui()
        self._refresh_controls()
        self.update_heatmap()
        self._reload_points()
        self.update_chart()

    def _build_ui(self):
        theme = get_theme()
        container = tk.Frame(self, bg=theme["bg"])
        container.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        desc = tk.Label(
            container,
            text=f"Samples TCP connect time & packet loss to {self.logger.host}. "
                 "Leave it running to learn which hours are quiet.",
            fg=theme["text_secondary"], bg=theme["bg"], font=(UI_FONT, 9),
            justify=tk.LEFT, wraplength=700)
        desc.pack(anchor=tk.W, pady=(0, 8))

        # VPN warning banner (hidden unless a VPN is detected). Frame with
        # wrapped text + close button; _apply_vpn_banner toggles visibility.
        self.vpn_banner = tk.Frame(container, bg=theme["warning"])
        self.vpn_banner_text = tk.Label(
            self.vpn_banner, text="", fg=theme["bg"], bg=theme["warning"],
            font=(UI_FONT, 9, "bold"), justify=tk.LEFT, wraplength=700,
            anchor=tk.W, padx=10, pady=6)
        self.vpn_banner_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.vpn_banner_close = tk.Label(
            self.vpn_banner, text="\u00d7", fg=theme["bg"], bg=theme["warning"],
            font=(UI_FONT, 14, "bold"), cursor="hand2", padx=12)
        self.vpn_banner_close.pack(side=tk.RIGHT)
        self.vpn_banner_close.bind("<Button-1>", lambda e: self.app._dismiss_vpn_banner())

        # Status row
        controls = tk.Frame(container, bg=theme["bg"])
        controls.pack(fill=tk.X, pady=(0, 8))

        self.current_label = tk.Label(controls, text="", fg=theme["text"],
                                      bg=theme["bg"], font=(UI_FONT, 10, "bold"))
        self.current_label.pack(side=tk.LEFT)

        # Heatmap
        hm_title = tk.Label(container, text="Latency by hour of day (local time)",
                            fg=theme["success"], bg=theme["bg"], font=(UI_FONT, 10, "bold"))
        hm_title.pack(anchor=tk.W)

        canvas_w = self.PAD_X * 2 + 24 * (self.CELL_W + self.GAP)
        canvas_h = self.PAD_TOP + self.CELL_H + 22
        self.canvas = tk.Canvas(container, width=canvas_w, height=canvas_h,
                                bg=theme["bg"], highlightthickness=0)
        self.canvas.pack(anchor=tk.W, pady=(4, 2))
        self.canvas.bind("<Motion>", self._on_hover)

        self.detail_label = tk.Label(container, text="Hover a cell for details.",
                                     fg=theme["text_secondary"], bg=theme["bg"],
                                     font=(UI_FONT, 9))
        self.detail_label.pack(anchor=tk.W)

        legend = tk.Label(container,
                          text="green = fast   yellow = sluggish   red = slow / packet loss   dark = unreachable",
                          fg=theme["text_secondary"], bg=theme["bg"], font=(UI_FONT, 8))
        legend.pack(anchor=tk.W, pady=(2, 10))

        self.summary_label = tk.Label(container, text="", fg=theme["text"],
                                      bg=theme["bg"], font=(UI_FONT, 10), justify=tk.LEFT)
        self.summary_label.pack(anchor=tk.W)

        # Scatter chart of every probe point
        chart_title = tk.Label(container,
                               text="All probes \u2014 latency (ms) by time of day  \u2022  bars = jitter",
                               fg=theme["success"], bg=theme["bg"], font=(UI_FONT, 10, "bold"))
        chart_title.pack(anchor=tk.W, pady=(10, 2))

        self.chart_canvas = tk.Canvas(container, height=170, bg=theme["bg"],
                                      highlightthickness=0)
        self.chart_canvas.pack(fill=tk.BOTH, expand=True)
        self.chart_canvas.bind("<Configure>", lambda e: self.update_chart())

    def _refresh_controls(self):
        self._update_current_label()

    def _apply_vpn_banner(self, reason):
        """Show/hide the in-panel banner. Called by the app's _refresh_vpn_state
        with the *effective* reason (after dismissal logic)."""
        if reason:
            self.vpn_banner_text.config(
                text=f"VPN/tunnel detected \u2014 sampling paused. {reason}. "
                     "Disable the VPN to resume probing the Stena portal."
            )
            if not self.vpn_banner.winfo_ismapped():
                self.vpn_banner.pack(fill=tk.X, pady=(0, 8), before=self.current_label.master)
        elif self.vpn_banner.winfo_ismapped():
            self.vpn_banner.pack_forget()

    def _update_current_label(self):
        vpn_reason = getattr(self.logger, "vpn_reason", None)
        # Delegate banner show/hide (with dismissal logic) to the app, then
        # keep the small status line honest about the real detection state.
        self.app._refresh_vpn_state()
        if vpn_reason:
            self.current_label.config(text="Paused (VPN detected).")
            return

        rec = self.logger.last_record
        if rec is None:
            txt = "Sampling..."
        elif rec["avg"] is None:
            txt = f"Last: unreachable ({rec['loss']:.0f}% loss) at {rec['timestamp'].strftime('%H:%M:%S')}"
        else:
            txt = (f"Last: {rec['avg']:.0f} ms  |  jitter {rec['jitter']:.0f} ms  |  "
                   f"{rec['loss']:.0f}% loss  at {rec['timestamp'].strftime('%H:%M:%S')}")
        self.current_label.config(text=txt)

    def _on_logger_update(self, record):
        # Called from worker thread -> marshal onto the Tk main thread.
        try:
            self.app.root.after(0, self._apply_update)
        except Exception:
            pass

    def _apply_update(self):
        if not self.winfo_exists():
            return
        self._refresh_controls()
        self.update_heatmap()
        self._reload_points()
        self.update_chart()

    def _load_hourly(self):
        hours = {h: {"lat": [], "loss": []} for h in range(24)}
        if not os.path.isfile(self.logger.csv_path):
            return hours
        try:
            with open(self.logger.csv_path, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        h = datetime.strptime(row.get("Timestamp", ""), "%Y-%m-%d %H:%M:%S").hour
                    except (ValueError, TypeError):
                        continue
                    loss_s = row.get("Loss(%)", "")
                    try:
                        loss = float(loss_s) if loss_s != "" else 100.0
                    except ValueError:
                        loss = 100.0
                    hours[h]["loss"].append(loss)
                    lat_s = row.get("LatencyAvg(ms)", "")
                    if lat_s:
                        try:
                            hours[h]["lat"].append(float(lat_s))
                        except ValueError:
                            pass
        except Exception as e:
            print(f"[DEBUG] NQ load error: {e}")
        return hours

    @staticmethod
    def _lerp(a, b, f):
        return tuple(int(a[i] + (b[i] - a[i]) * f) for i in range(3))

    def _quality_color(self, lat, loss):
        if lat is None:
            return "#7f1d1d"  # unreachable
        good, bad = 60.0, 1500.0
        t = max(0.0, min(1.0, (lat - good) / (bad - good)))
        t = max(t, min(1.0, loss / 100.0))  # fold loss into the score
        green, yellow, red = (74, 222, 128), (251, 191, 36), (248, 113, 113)
        if t <= 0.5:
            c = self._lerp(green, yellow, t / 0.5)
        else:
            c = self._lerp(yellow, red, (t - 0.5) / 0.5)
        return "#%02x%02x%02x" % c

    def update_heatmap(self):
        self._hourly = self._load_hourly()
        theme = get_theme()
        c = self.canvas
        c.delete("all")
        for h in range(24):
            x0 = self.PAD_X + h * (self.CELL_W + self.GAP)
            y0 = self.PAD_TOP
            x1 = x0 + self.CELL_W
            y1 = y0 + self.CELL_H
            d = self._hourly.get(h, {"lat": [], "loss": []})
            if d["loss"]:
                avg_lat = (sum(d["lat"]) / len(d["lat"])) if d["lat"] else None
                avg_loss = sum(d["loss"]) / len(d["loss"])
                color = self._quality_color(avg_lat, avg_loss)
            else:
                color = theme["bg_tertiary"]
            c.create_rectangle(x0, y0, x1, y1, fill=color, outline=theme["border"])
            c.create_text((x0 + x1) // 2, y1 + 11, text=f"{h:02d}",
                          fill=theme["text_secondary"], font=(UI_FONT, 7))
        self._update_summary()

    def _update_summary(self):
        ranked = []
        for h, d in self._hourly.items():
            if d["lat"]:
                ranked.append((sum(d["lat"]) / len(d["lat"]), h, len(d["loss"])))
        if not ranked:
            self.summary_label.config(text="Quietest hours: no data yet.")
            return
        ranked.sort()
        best = ", ".join(f"{h:02d}:00 ({lat:.0f} ms)" for lat, h, _ in ranked[:3])
        self.summary_label.config(text=f"Quietest hours so far: {best}")

    def _on_hover(self, event):
        h = round((event.x - self.PAD_X) / (self.CELL_W + self.GAP))
        if h < 0 or h > 23:
            self.detail_label.config(text="Hover a cell for details.")
            return
        d = self._hourly.get(h, {"lat": [], "loss": []})
        if not d["loss"]:
            self.detail_label.config(text=f"{h:02d}:00 \u2014 no samples yet")
            return
        avg_loss = sum(d["loss"]) / len(d["loss"])
        if d["lat"]:
            avg_lat = sum(d["lat"]) / len(d["lat"])
            self.detail_label.config(
                text=f"{h:02d}:00 \u2014 {avg_lat:.0f} ms avg, {avg_loss:.0f}% loss, n={len(d['loss'])}")
        else:
            self.detail_label.config(
                text=f"{h:02d}:00 \u2014 unreachable, {avg_loss:.0f}% loss, n={len(d['loss'])}")

    def _reload_points(self):
        """Read every probe row from the CSV into (frac_hour, avg, jitter, loss)."""
        points = []
        if not os.path.isfile(self.logger.csv_path):
            self._points = points
            return
        try:
            with open(self.logger.csv_path, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        dt = datetime.strptime(row.get("Timestamp", ""), "%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        continue
                    frac = dt.hour + dt.minute / 60.0 + dt.second / 3600.0

                    def num(key):
                        v = row.get(key, "")
                        try:
                            return float(v) if v != "" else None
                        except ValueError:
                            return None

                    avg = num("LatencyAvg(ms)")
                    jitter = num("Jitter(ms)") or 0.0
                    loss = num("Loss(%)")
                    if loss is None:
                        loss = 0.0 if avg is not None else 100.0
                    points.append((frac, avg, jitter, loss))
        except Exception as e:
            print(f"[DEBUG] NQ points load error: {e}")
        self._points = points

    def update_chart(self):
        c = self.chart_canvas
        if not c.winfo_exists():
            return
        w, h = c.winfo_width(), c.winfo_height()
        if w < 40 or h < 40:
            return
        theme = get_theme()
        c.delete("all")
        left, right, top, bottom = 46, 12, 10, 22
        plot_w, plot_h = w - left - right, h - top - bottom
        if plot_w < 10 or plot_h < 10:
            return

        avgs = [p[1] for p in self._points if p[1] is not None]
        ymax = max(max(avgs) * 1.1, 100.0) if avgs else 500.0

        def yp(val):
            return top + plot_h - (min(val, ymax) / ymax) * plot_h

        # Plot border
        c.create_rectangle(left, top, left + plot_w, top + plot_h, outline=theme["border"])
        # Y gridlines + labels
        for i in range(5):
            val = ymax * i / 4
            y = yp(val)
            c.create_line(left, y, left + plot_w, y, fill=theme["border"])
            c.create_text(left - 6, y, text=f"{val:.0f}", anchor=tk.E,
                          fill=theme["text_secondary"], font=(UI_FONT, 7))
        # X gridlines + hour labels
        for hh in range(0, 25, 3):
            x = left + (hh / 24.0) * plot_w
            c.create_line(x, top, x, top + plot_h, fill=theme["border"])
            c.create_text(x, top + plot_h + 10, text=f"{hh:02d}",
                          fill=theme["text_secondary"], font=(UI_FONT, 7))

        # Probe points (with jitter error bars); unreachable shown as dashed line
        for frac, avg, jitter, loss in self._points:
            x = left + (frac / 24.0) * plot_w
            if avg is None:
                c.create_line(x, top, x, top + plot_h, fill=theme["error"], dash=(1, 3))
                continue
            if jitter > 0:
                c.create_line(x, yp(max(0.0, avg - jitter)), x, yp(avg + jitter),
                              fill=theme["text_secondary"])
            color = self._quality_color(avg, loss)
            y = yp(avg)
            c.create_oval(x - 2, y - 2, x + 2, y + 2, fill=color, outline="")

        if not self._points:
            c.create_text(left + plot_w // 2, top + plot_h // 2,
                          text="No probe data yet.",
                          fill=theme["text_secondary"], font=(UI_FONT, 9))


class IPInfoPanel(tk.Frame):
    """Tab panel that looks up the user's external IP and renders ISP /
    geolocation details. Fetches happen in a worker thread and are merged
    back onto the Tk main thread via root.after."""

    PRIMARY_URL = "https://ipapi.co/json/"
    FALLBACK_URL = "https://ipwho.is/"

    def __init__(self, parent, app):
        self.app = app
        theme = get_theme()
        super().__init__(parent, bg=theme["bg_secondary"])
        self._data = None
        self._loading = False
        self._build_ui()
        # Auto-fetch once on startup so the tab isn't empty when opened.
        self.after(800, self.refresh)

    def rebuild(self):
        """Tear down + rebuild on theme change. Re-renders cached data."""
        for widget in self.winfo_children():
            widget.destroy()
        self.configure(bg=get_theme()["bg_secondary"])
        self._build_ui()
        if self._data:
            self._render(self._data)

    def _build_ui(self):
        theme = get_theme()

        header = tk.Frame(self, bg=theme["bg_secondary"])
        header.pack(fill=tk.X, padx=12, pady=(12, 8))

        title = tk.Label(
            header, text="External IP Information",
            fg=theme["accent"], bg=theme["bg_secondary"],
            font=(UI_FONT, 12, "bold"))
        title.pack(side=tk.LEFT)

        self.refresh_btn = CustomButton(
            header, "Refresh", self.refresh,
            width=100, height=32, color_key="accent")
        self.refresh_btn.pack(side=tk.RIGHT)

        self.output = scrolledtext.ScrolledText(
            self, wrap=tk.WORD, font=("Consolas", 10),
            background=theme["bg_tertiary"], foreground=theme["text"],
            insertbackground=theme["text"], relief=tk.FLAT,
            highlightthickness=1, highlightbackground=theme["border"],
            highlightcolor=theme["accent"])
        self.output.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        self._configure_tags()

        self.output.insert(
            tk.END,
            "Click 'Refresh' to look up your public IP information.\n",
            "normal")

    def _configure_tags(self):
        theme = get_theme()
        self.output.tag_configure("title", foreground=theme["accent"],
                                  font=(UI_FONT, 12, "bold"))
        self.output.tag_configure("section", foreground=theme["success"],
                                  font=(UI_FONT, 10, "bold"))
        self.output.tag_configure("label", foreground=theme["text_secondary"],
                                  font=("Consolas", 10))
        self.output.tag_configure("value", foreground=theme["text"],
                                  font=("Consolas", 10, "bold"))
        self.output.tag_configure("normal", foreground=theme["text"],
                                  font=(UI_FONT, 10))
        self.output.tag_configure("error", foreground=theme["error"],
                                  font=(UI_FONT, 10, "bold"))
        self.output.tag_configure("fetching", foreground=theme["accent"],
                                  font=(UI_FONT, 10, "italic"))
        self.output.tag_configure("footer", foreground=theme["text_secondary"],
                                  font=(UI_FONT, 8, "italic"))

    def refresh(self):
        if self._loading:
            return
        self._loading = True
        try:
            self.refresh_btn.set_enabled(False)
        except Exception:
            pass
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, "Fetching IP information...\n", "fetching")
        threading.Thread(target=self._fetch_thread, daemon=True).start()

    def _fetch_thread(self):
        result = {}
        try:
            result = self._fetch_ip_data()
        except Exception as e:
            result = {"_error": str(e)}
        try:
            self.app.root.after(0, lambda r=result: self._on_fetch_done(r))
        except Exception:
            pass

    def _fetch_ip_data(self):
        last_err = None
        try:
            r = requests.get(self.PRIMARY_URL, timeout=10,
                             headers={"User-Agent": "SLIM/IPInfo"})
            if r.status_code == 200:
                data = r.json()
                if not data.get("error"):
                    return self._normalize_ipapi(data)
                last_err = data.get("reason") or data.get("error")
        except Exception as e:
            last_err = str(e)

        try:
            r = requests.get(self.FALLBACK_URL, timeout=10,
                             headers={"User-Agent": "SLIM/IPInfo"})
            r.raise_for_status()
            data = r.json()
            if data.get("success") is False:
                raise RuntimeError(data.get("message", "Lookup failed"))
            return self._normalize_ipwhois(data)
        except Exception as e:
            raise RuntimeError(last_err or str(e))

    @staticmethod
    def _normalize_ipapi(d):
        return {
            "source": "ipapi.co",
            "ip": d.get("ip"),
            "version": d.get("version"),
            "hostname": d.get("hostname"),
            "city": d.get("city"),
            "region": d.get("region"),
            "country": d.get("country_name"),
            "country_code": d.get("country_code"),
            "postal": d.get("postal"),
            "latitude": d.get("latitude"),
            "longitude": d.get("longitude"),
            "timezone": d.get("timezone"),
            "utc_offset": d.get("utc_offset"),
            "calling_code": d.get("country_calling_code"),
            "currency": d.get("currency"),
            "currency_name": d.get("currency_name"),
            "languages": d.get("languages"),
            "asn": d.get("asn"),
            "org": d.get("org"),
        }

    @staticmethod
    def _normalize_ipwhois(d):
        conn = d.get("connection") or {}
        tz = d.get("timezone") or {}
        cur = d.get("currency") or {}
        return {
            "source": "ipwho.is",
            "ip": d.get("ip"),
            "version": d.get("type"),
            "hostname": None,
            "city": d.get("city"),
            "region": d.get("region"),
            "country": d.get("country"),
            "country_code": d.get("country_code"),
            "postal": d.get("postal"),
            "latitude": d.get("latitude"),
            "longitude": d.get("longitude"),
            "timezone": tz.get("id"),
            "utc_offset": tz.get("utc"),
            "calling_code": d.get("calling_code"),
            "currency": cur.get("code"),
            "currency_name": cur.get("name"),
            "languages": None,
            "asn": f"AS{conn.get('asn')}" if conn.get("asn") else None,
            "org": conn.get("isp") or conn.get("org"),
        }

    def _on_fetch_done(self, data):
        self._loading = False
        try:
            self.refresh_btn.set_enabled(True)
        except Exception:
            pass

        if "_error" in data:
            self.output.delete("1.0", tk.END)
            self.output.insert(tk.END, "Failed to fetch IP information.\n", "error")
            self.output.insert(tk.END, f"{data['_error']}\n", "normal")
            return

        self._data = data
        self._render(data)

        # Reverse DNS lookup runs in its own thread so a slow PTR query
        # doesn't delay the visible render.
        ip = data.get("ip")
        if ip and not data.get("hostname"):
            threading.Thread(
                target=self._reverse_dns_thread, args=(ip,), daemon=True
            ).start()

    def _reverse_dns_thread(self, ip):
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except Exception:
            hostname = None
        if not hostname or not self._data:
            return
        self._data["hostname"] = hostname
        try:
            self.app.root.after(0, lambda: self._render(self._data))
        except Exception:
            pass

    def _render(self, data):
        self.output.delete("1.0", tk.END)

        self.output.insert(tk.END, "Public IP Address\n", "title")
        self._row("IP Address", data.get("ip"))
        self._row("Version", data.get("version"))
        self._row("Reverse DNS", data.get("hostname") or "—")
        self.output.insert(tk.END, "\n")

        self.output.insert(tk.END, "Network / ISP\n", "section")
        self._row("Organization", data.get("org"))
        self._row("ASN", data.get("asn"))
        self.output.insert(tk.END, "\n")

        self.output.insert(tk.END, "Location\n", "section")
        loc_parts = [data.get("city"), data.get("region"), data.get("country")]
        loc = ", ".join(p for p in loc_parts if p)
        self._row("Location", loc or None)
        self._row("Country code", data.get("country_code"))
        self._row("Postal code", data.get("postal"))
        lat, lon = data.get("latitude"), data.get("longitude")
        if lat is not None and lon is not None:
            self._row("Coordinates", f"{lat}, {lon}")
        self._row("Timezone", data.get("timezone"))
        self._row("UTC offset", data.get("utc_offset"))
        self.output.insert(tk.END, "\n")

        self.output.insert(tk.END, "Region info\n", "section")
        self._row("Calling code", data.get("calling_code"))
        cur_name = data.get("currency_name")
        cur_code = data.get("currency")
        if cur_name and cur_code:
            currency = f"{cur_name} ({cur_code})"
        else:
            currency = cur_name or cur_code
        self._row("Currency", currency)
        self._row("Languages", data.get("languages"))
        self.output.insert(tk.END, "\n")

        self.output.insert(
            tk.END,
            f"Source: {data.get('source', 'unknown')}\n",
            "footer")

    def _row(self, label, value):
        if value in (None, ""):
            return
        self.output.insert(tk.END, f"{label:>14} : ", "label")
        self.output.insert(tk.END, f"{value}\n", "value")


class StenaInternetMonitor:
    def __init__(self, root):
        print("[DEBUG] Initializing StenaInternetMonitor...")
        self.root = root
        self.root.title(f"Stena Line Internet Monitor v{APP_VERSION}")
        self.root.geometry("760x860")
        self.root.resizable(True, True)
        self.root.configure(bg=get_theme()["bg"])
        print("[DEBUG] Basic window configuration complete")

        # Shared HTTP session so cookies set by `init` are carried into
        # subsequent `authenticate` / `disconnect` calls (matches what a phone
        # webview does on the captive portal).
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session = requests.Session()
        self.session.headers.update(API_HEADERS)
        self.session.verify = False
        # Portal handshake state (see _ensure_portal_session)
        self._portal_session_ready = False
        self.portal_url = None
        self.portal_site_id = None
        
        # Configure ttk styles for modern look
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._configure_styles()
        
        # Create main frame with padding
        self.main_frame = tk.Frame(root, bg=get_theme()["bg"])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)
        
        # Create a container for all content including footer
        self.content_frame = tk.Frame(self.main_frame, bg=get_theme()["bg"])
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create footer frame
        self.footer_frame = tk.Frame(self.main_frame, bg=get_theme()["bg"])
        self.footer_frame.pack(fill=tk.X, side=tk.BOTTOM, before=self.content_frame, pady=(8, 0))
        
        # Add GitHub link to footer
        self.github_link = tk.Label(
            self.footer_frame,
            text="© Damiasroca",
            fg=get_theme()["accent"],
            bg=get_theme()["bg"],
            cursor="hand2",
            font=(UI_FONT, 8, "underline")
        )
        self.github_link.pack(side=tk.RIGHT, padx=10, pady=2)
        self.github_link.bind("<Button-1>", self.open_github)

        # Add version label to footer (left side)
        self.version_label = tk.Label(
            self.footer_frame,
            text=f"v{APP_VERSION}",
            fg=get_theme()["text_secondary"],
            bg=get_theme()["bg"],
            font=(UI_FONT, 8)
        )
        self.version_label.pack(side=tk.LEFT, padx=10, pady=2)
        
        # Add theme toggle button
        self.theme_btn = tk.Label(
            self.footer_frame,
            text="🌙 Dark" if current_theme == "dark" else "☀️ Light",
            fg=get_theme()["text_secondary"],
            bg=get_theme()["bg"],
            cursor="hand2",
            font=(UI_FONT, 9)
        )
        self.theme_btn.pack(side=tk.LEFT, padx=10, pady=2)
        self.theme_btn.bind("<Button-1>", self.toggle_theme)
        
        # Info banner about username/password
        self.info_frame = tk.Frame(self.content_frame, bg=get_theme()["bg"])
        self.info_frame.pack(fill=tk.X, pady=(0, 12))
        
        self.info_label = tk.Label(
            self.info_frame, 
            text="💡 For Stena Line captive portal, the username and password are the same.",
            fg=get_theme()["text_secondary"],
            bg=get_theme()["bg"],
            font=(UI_FONT, 10)
        )
        self.info_label.pack(pady=4)

        # Create credentials card
        self.creds_frame = CardFrame(self.content_frame, title="Login Credentials")
        self.creds_frame.pack(fill=tk.X, pady=(0, 12))
        
        # Create credentials inner frame for grid layout
        creds_inner = tk.Frame(self.creds_frame.content, bg=get_theme()["bg_secondary"])
        creds_inner.pack(fill=tk.X)
        
        # Create username and password fields with rounded entries
        self.username_label = tk.Label(creds_inner, text="Username:", fg=get_theme()["text"], bg=get_theme()["bg_secondary"], font=(UI_FONT, 10))
        self.username_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=6)
        self.username_var = tk.StringVar(value="")
        self.username_entry = RoundedEntry(creds_inner, textvariable=self.username_var, width=160, height=32)
        self.username_entry.grid(row=0, column=1, sticky=tk.W, padx=(0, 20), pady=6)
        
        self.password_label = tk.Label(creds_inner, text="Password:", fg=get_theme()["text"], bg=get_theme()["bg_secondary"], font=(UI_FONT, 10))
        self.password_label.grid(row=0, column=2, sticky=tk.W, padx=(0, 8), pady=6)
        self.password_var = tk.StringVar(value="")
        self.password_entry = RoundedEntry(creds_inner, textvariable=self.password_var, width=160, height=32, show="•")
        self.password_entry.grid(row=0, column=3, sticky=tk.W, pady=6)
        
        # Create profile management card
        self.profile_frame = CardFrame(self.content_frame, title="Profile Management")
        self.profile_frame.pack(fill=tk.X, pady=(0, 12))
        
        # Profile selection
        self.profiles_frame = tk.Frame(self.profile_frame.content, bg=get_theme()["bg_secondary"])
        self.profiles_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.select_profile_label = tk.Label(self.profiles_frame, text="Select Profile:", fg=get_theme()["text"], bg=get_theme()["bg_secondary"], font=(UI_FONT, 10))
        self.select_profile_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        self.profiles = self.load_profiles()
        self.profile_var = tk.StringVar()
        self.profile_combo = ttk.Combobox(self.profiles_frame, textvariable=self.profile_var, width=20, font=(UI_FONT, 10))
        self.profile_combo.grid(row=0, column=1, padx=(0, 8), pady=4)
        self.update_profile_list()
        
        self.profile_combo.bind("<<ComboboxSelected>>", self.load_selected_profile)
        
        # New profile creation
        self.new_profile_frame = tk.Frame(self.profile_frame.content, bg=get_theme()["bg_secondary"])
        self.new_profile_frame.pack(fill=tk.X)
        
        self.new_profile_label = tk.Label(self.new_profile_frame, text="New Profile:", fg=get_theme()["text"], bg=get_theme()["bg_secondary"], font=(UI_FONT, 10))
        self.new_profile_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        self.profile_name_var = tk.StringVar()
        self.profile_name_entry = RoundedEntry(self.new_profile_frame, textvariable=self.profile_name_var, width=160, height=32)
        self.profile_name_entry.grid(row=0, column=1, padx=(0, 16), pady=4)
        
        # Buttons for profile management. The frame stretches to fill the
        # remaining width of `new_profile_frame` (col 2 gets weight) so the
        # responsive layout has room to spread the buttons on wide windows
        # and to wrap them on narrow ones.
        self.new_profile_frame.grid_columnconfigure(2, weight=1)
        self.profile_buttons_frame = tk.Frame(self.new_profile_frame, bg=get_theme()["bg_secondary"])
        self.profile_buttons_frame.grid(row=0, column=2, columnspan=2, padx=0, pady=4, sticky="ew")

        self.save_profile_btn = CustomButton(
            self.profile_buttons_frame, "Save Profile", self.save_profile,
            width=100, height=28, color_key="success"
        )
        self.delete_profile_btn = CustomButton(
            self.profile_buttons_frame, "Delete Profile", self.delete_profile,
            width=100, height=28, color_key="warning"
        )
        self._profile_buttons = [self.save_profile_btn, self.delete_profile_btn]
        
        # Create action buttons frame
        self.buttons_frame = tk.Frame(self.content_frame, bg=get_theme()["bg"])
        self.buttons_frame.pack(fill=tk.X, pady=(0, 12))
        
        # Create buttons with custom styling. Their `width` doubles as the
        # minimum cell width used by the responsive layout below, so that the
        # label is always fully visible no matter how narrow the window gets.
        self.fetch_btn = CustomButton(
            self.buttons_frame, "Fetch Data/Connect", self.fetch_data, 
            width=140, height=36, color_key="accent"
        )
        self.clear_btn = CustomButton(
            self.buttons_frame, "Clear Display", self.clear_output, 
            width=110, height=36, color_key="text_secondary"
        )
        self.flush_dns_btn = CustomButton(
            self.buttons_frame, "Flush DNS", self.flush_dns, 
            width=100, height=36, color_key="warning"
        )
        self.disconnect_btn = CustomButton(
            self.buttons_frame, "Disconnect", self.disconnect_profile,
            width=100, height=36, color_key="error"
        )
        self._action_buttons = [
            self.fetch_btn, self.clear_btn, self.flush_dns_btn, self.disconnect_btn
        ]
        # Cache of column-count per responsive row, keyed by row name, used
        # to skip no-op relayouts during drag-resize.
        self._button_row_cols = {}
        self.buttons_frame.bind(
            "<Configure>",
            lambda e: self._layout_button_row(self._action_buttons, self.buttons_frame, "action", e),
        )
        self.profile_buttons_frame.bind(
            "<Configure>",
            lambda e: self._layout_button_row(self._profile_buttons, self.profile_buttons_frame, "profile", e),
        )
        # Flip the profile buttons frame between inline (next to the entry) and
        # wrapped (its own row below the entry) based on available width.
        self.new_profile_frame.bind("<Configure>", self._layout_profile_row)
        # Initial placement once each frame has been realized.
        self.buttons_frame.after_idle(
            lambda: self._layout_button_row(self._action_buttons, self.buttons_frame, "action")
        )
        self.profile_buttons_frame.after_idle(
            lambda: self._layout_button_row(self._profile_buttons, self.profile_buttons_frame, "profile")
        )
        self.new_profile_frame.after_idle(self._layout_profile_row)
        
        # Add tooltips to buttons
        ModernTooltip(self.fetch_btn, "Fetch your current internet usage data")
        ModernTooltip(self.clear_btn, "Clear the display area")
        ModernTooltip(self.flush_dns_btn, "Flush DNS cache to resolve connection issues")
        ModernTooltip(self.disconnect_btn, "Disconnect the selected profile from the network")
        
        # Network quality logger (shared by the embedded panel below).
        # Always runs in the background; samples every 120s.
        # _vpn_dismissed_reason remembers a VPN reason the user closed via the
        # banner's X so it doesn't pop back next cycle while the VPN is still on.
        self._vpn_dismissed_reason = None
        self.quality_logger = NetworkQualityLogger(QUALITY_HOST, QUALITY_PORT, QUALITY_CSV)
        self.quality_logger.start()
        
        # Tabbed area: usage output + network quality, all in one window (no popup)
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        
        self.usage_tab = tk.Frame(self.notebook, bg=get_theme()["bg_secondary"])
        self.quality_tab = tk.Frame(self.notebook, bg=get_theme()["bg"])
        self.ip_info_tab = tk.Frame(self.notebook, bg=get_theme()["bg_secondary"])
        self.notebook.add(self.usage_tab, text="Internet Usage")
        self.notebook.add(self.quality_tab, text="Network Quality")
        self.notebook.add(self.ip_info_tab, text="IP Info")
        
        # Right-side panel that hosts the quota gauge. Stays hidden until
        # there's quota data to show (see _show_quota_gauge / _hide_quota_gauge).
        self.gauge_panel = tk.Frame(
            self.usage_tab, bg=get_theme()["bg_secondary"], width=260
        )
        self.gauge_panel.pack_propagate(False)
        self.quota_gauge = QuotaGauge(self.gauge_panel)
        self.quota_gauge.pack(pady=12, padx=8)

        # VPN warning banner for the usage tab. Frame with a wrapped text
        # label + a close (x) button; hidden unless the quality logger
        # detects a tunnel (see _update_usage_vpn_banner).
        self.usage_vpn_banner = tk.Frame(self.usage_tab, bg=get_theme()["warning"])
        self.usage_vpn_banner_text = tk.Label(
            self.usage_vpn_banner, text="",
            fg=get_theme()["bg"], bg=get_theme()["warning"],
            font=(UI_FONT, 9, "bold"), justify=tk.LEFT, wraplength=900,
            anchor=tk.W, padx=10, pady=6)
        self.usage_vpn_banner_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.usage_vpn_banner_close = tk.Label(
            self.usage_vpn_banner, text="\u00d7",
            fg=get_theme()["bg"], bg=get_theme()["warning"],
            font=(UI_FONT, 14, "bold"), cursor="hand2", padx=12)
        self.usage_vpn_banner_close.pack(side=tk.RIGHT)
        self.usage_vpn_banner_close.bind("<Button-1>", lambda e: self._dismiss_vpn_banner())

        self.output_text = scrolledtext.ScrolledText(
            self.usage_tab, wrap=tk.WORD, 
            font=("Consolas", 10), 
            background=get_theme()["bg_tertiary"], 
            foreground=get_theme()["text"],
            insertbackground=get_theme()["text"],
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=get_theme()["border"],
            highlightcolor=get_theme()["accent"]
        )
        self.output_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # Embedded network quality panel (heatmap + probe chart) in its own tab
        self.quality_panel = NetworkQualityPanel(self.quality_tab, self)
        self.quality_panel.pack(fill=tk.BOTH, expand=True)

        # External IP info panel (public IP, ISP, geolocation) in its own tab
        self.ip_info_panel = IPInfoPanel(self.ip_info_tab, self)
        self.ip_info_panel.pack(fill=tk.BOTH, expand=True)
        
        # Configure all text tags for formatting (consolidated in one place)
        self._configure_text_tags()
        
        # Create status bar
        self.status_frame = tk.Frame(self.content_frame, bg=get_theme()["bg"])
        self.status_frame.pack(fill=tk.X)
        
        self.status_indicator = tk.Canvas(self.status_frame, width=12, height=12, background=get_theme()["bg"], highlightthickness=0)
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 6))
        self.status_light = self.status_indicator.create_oval(2, 2, 10, 10, fill=get_theme()["success"], outline="")
        
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = tk.Label(self.status_frame, textvariable=self.status_var, anchor=tk.W,
                                      fg=get_theme()["text_secondary"], bg=get_theme()["bg"], font=(UI_FONT, 9))
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Storage for fetched data
        self.current_data = None
        
        # Stop the background logger cleanly on exit
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Welcome message with colors
        self.display_welcome_message()
        print("[DEBUG] StenaInternetMonitor initialization complete")
        
        # Check connection status on startup
        self.root.after(500, self.check_connection_status)
    
    def _configure_styles(self):
        """Configure ttk styles for modern look"""
        theme = get_theme()
        self.style.configure("TFrame", background=theme["bg"])
        self.style.configure("TLabel", background=theme["bg"], foreground=theme["text"])
        self.style.configure("TLabelframe", background=theme["bg"], foreground=theme["accent"])
        self.style.configure("TLabelframe.Label", background=theme["bg"], foreground=theme["accent"], font=(UI_FONT, 10, "bold"))
        self.style.configure("TEntry", fieldbackground=theme["bg_tertiary"], foreground=theme["text"])
        self.style.configure("TCombobox", fieldbackground=theme["bg_tertiary"], foreground=theme["text"], arrowcolor=theme["text"])
        self.style.map("TCombobox", fieldbackground=[("readonly", theme["bg_tertiary"])], selectbackground=[("readonly", theme["accent"])])
        self.style.map("TButton", background=[("active", theme["accent"])], foreground=[("active", "white")])
        # Notebook (tabbed usage / network quality area)
        self.style.configure("TNotebook", background=theme["bg"], borderwidth=0)
        self.style.configure("TNotebook.Tab", background=theme["bg_secondary"],
                             foreground=theme["text_secondary"], padding=(14, 6),
                             font=(UI_FONT, 10, "bold"))
        self.style.map("TNotebook.Tab",
                       background=[("selected", theme["bg_tertiary"])],
                       foreground=[("selected", theme["accent"])])
    
    def _configure_text_tags(self):
        """Configure all text tags for the output text widget (consolidated in one place)"""
        theme = get_theme()
        
        # Title and headers
        self.output_text.tag_configure("title", foreground=theme["accent"], font=(UI_FONT, 12, "bold"))
        self.output_text.tag_configure("header", foreground=theme["accent"], font=(UI_FONT, 12, "bold"))
        
        # Section headers
        self.output_text.tag_configure("subtitle", foreground=theme["success"], font=(UI_FONT, 10, "bold"))
        self.output_text.tag_configure("section", foreground=theme["success"], font=(UI_FONT, 10, "bold"))
        
        # Content tags
        self.output_text.tag_configure("normal", foreground=theme["text"], font=(UI_FONT, 10))
        self.output_text.tag_configure("label", foreground=theme["text_secondary"], font=(UI_FONT, 9))
        self.output_text.tag_configure("value", foreground=theme["text"], font=(UI_FONT, 10, "bold"))
        
        # Status tags
        self.output_text.tag_configure("warning", foreground=theme["warning"], font=(UI_FONT, 10, "bold"))
        self.output_text.tag_configure("alert", foreground=theme["error"], font=(UI_FONT, 11, "bold"))
        self.output_text.tag_configure("error", foreground=theme["error"], font=(UI_FONT, 10, "bold"))
        self.output_text.tag_configure("error_details", foreground=theme["error"], font=("Consolas", 9))
        
        # Other tags
        self.output_text.tag_configure("fetching", foreground=theme["accent"], font=(UI_FONT, 10, "italic"))
        self.output_text.tag_configure("footer", foreground=theme["text_secondary"], font=(UI_FONT, 8, "italic"))
        self.output_text.tag_configure("debug", foreground=theme["text_secondary"], font=("Consolas", 9))

        # Clickable Wi-Fi settings link, shown inside the output box only on connection errors
        self.output_text.tag_configure("wifi_link", foreground=theme["accent"], font=(UI_FONT, 9, "underline"))
        self.output_text.tag_bind("wifi_link", "<Button-1>", lambda e: self.open_wifi_settings())
        self.output_text.tag_bind("wifi_link", "<Enter>", lambda e: self.output_text.configure(cursor="hand2"))
        self.output_text.tag_bind("wifi_link", "<Leave>", lambda e: self.output_text.configure(cursor=""))
    
    def open_github(self, event=None):
        """Open the GitHub profile in the default web browser"""
        try:
            import webbrowser
            webbrowser.open("https://github.com/Damiasroca/SLIM")
        except Exception as e:
            self.display_error(f"Failed to open GitHub link: {e}", traceback.format_exc())
    
    def toggle_theme(self, event=None):
        """Toggle between dark and light themes"""
        global current_theme, COLORS
        current_theme = "light" if current_theme == "dark" else "dark"
        COLORS = THEMES[current_theme]
        save_config()
        
        # Update theme button text
        self.theme_btn.config(text="🌙 Dark" if current_theme == "dark" else "☀️ Light")
        
        # Apply theme to all widgets
        self.apply_theme()
    
    def apply_theme(self):
        """Apply current theme to all widgets"""
        theme = get_theme()
        
        # Update root and main frames
        self.root.configure(bg=theme["bg"])
        self.main_frame.configure(bg=theme["bg"])
        self.content_frame.configure(bg=theme["bg"])
        self.footer_frame.configure(bg=theme["bg"])
        
        # Update ttk styles
        self._configure_styles()
        
        # Update footer widgets
        self.github_link.configure(fg=theme["accent"], bg=theme["bg"])
        self.theme_btn.configure(fg=theme["text_secondary"], bg=theme["bg"])
        self.version_label.configure(fg=theme["text_secondary"], bg=theme["bg"])
        
        # Update info banner
        self.info_frame.configure(bg=theme["bg"])
        self.info_label.configure(fg=theme["text_secondary"], bg=theme["bg"])
        
        # Update credentials card
        self.creds_frame.update_theme()
        # Update credentials inner widgets - find them through creds_frame.content
        for widget in self.creds_frame.content.winfo_children():
            if isinstance(widget, tk.Frame):
                widget.configure(bg=theme["bg_secondary"])
                for child in widget.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(fg=theme["text"], bg=theme["bg_secondary"])
                    elif isinstance(child, RoundedEntry):
                        child.update_theme()
        
        # Also update the direct entry references
        self.username_label.configure(fg=theme["text"], bg=theme["bg_secondary"])
        self.password_label.configure(fg=theme["text"], bg=theme["bg_secondary"])
        self.username_entry.update_theme()
        self.password_entry.update_theme()
        
        # Update profile card
        self.profile_frame.update_theme()
        self.profiles_frame.configure(bg=theme["bg_secondary"])
        self.select_profile_label.configure(fg=theme["text"], bg=theme["bg_secondary"])
        self.new_profile_frame.configure(bg=theme["bg_secondary"])
        self.new_profile_label.configure(fg=theme["text"], bg=theme["bg_secondary"])
        self.profile_name_entry.update_theme()
        self.profile_buttons_frame.configure(bg=theme["bg_secondary"])
        
        # Update profile buttons
        self.save_profile_btn.update_theme()
        self.delete_profile_btn.update_theme()
        
        # Update action buttons frame and buttons
        self.buttons_frame.configure(bg=theme["bg"])
        self.fetch_btn.update_theme()
        self.clear_btn.update_theme()
        self.flush_dns_btn.update_theme()
        self.disconnect_btn.update_theme()
        
        # Update tabbed area (usage text + network quality panel + IP info)
        self.usage_tab.configure(bg=theme["bg_secondary"])
        self.quality_tab.configure(bg=theme["bg"])
        self.ip_info_tab.configure(bg=theme["bg_secondary"])
        self.output_text.configure(bg=theme["bg_tertiary"], fg=theme["text"],
                                   insertbackground=theme["text"],
                                   highlightbackground=theme["border"],
                                   highlightcolor=theme["accent"])
        self.usage_vpn_banner.configure(bg=theme["warning"])
        self.usage_vpn_banner_text.configure(fg=theme["bg"], bg=theme["warning"])
        self.usage_vpn_banner_close.configure(fg=theme["bg"], bg=theme["warning"])
        self.quality_panel.rebuild()
        self.ip_info_panel.rebuild()
        
        # Re-configure text tags with new theme colors
        self._configure_text_tags()

        # Repaint the quota gauge panel and its canvas with the new theme.
        self.gauge_panel.configure(bg=theme["bg_secondary"])
        self.quota_gauge.update_theme()
        
        # Update status bar
        self.status_frame.configure(bg=theme["bg"])
        self.status_indicator.configure(bg=theme["bg"])
        self.status_label.configure(fg=theme["text_secondary"], bg=theme["bg"])

    def _update_usage_vpn_banner(self, reason):
        """Show/hide the VPN warning at the top of the Internet Usage tab.

        Called by _refresh_vpn_state, which already applies dismissal logic;
        `reason` here is the *effective* reason, so we just render it.
        """
        if reason:
            self.usage_vpn_banner_text.config(
                text=f"VPN/tunnel detected \u2014 the Stena portal won't be reachable. "
                     f"{reason}. Disable the VPN to fetch usage data."
            )
            if not self.usage_vpn_banner.winfo_ismapped():
                self.usage_vpn_banner.pack(side=tk.TOP, fill=tk.X,
                                           before=self.output_text,
                                           padx=8, pady=(8, 0))
        elif self.usage_vpn_banner.winfo_ismapped():
            self.usage_vpn_banner.pack_forget()

    def _dismiss_vpn_banner(self):
        """Close the VPN banner(s) for the current detection reason.

        The banners stay hidden until the detection state changes (VPN gone or
        a different reason fires), so closing once doesn't silence future,
        unrelated VPN events.
        """
        self._vpn_dismissed_reason = self.quality_logger.vpn_reason
        self._refresh_vpn_state()

    def _refresh_vpn_state(self):
        """Single source of truth for VPN banner visibility across both tabs."""
        raw = self.quality_logger.vpn_reason
        if raw != self._vpn_dismissed_reason:
            # Detection state changed — clear any prior dismissal so a new VPN
            # scenario is shown (or a cleared VPN simply hides everything).
            self._vpn_dismissed_reason = None
        effective = None if (raw is None or self._vpn_dismissed_reason is not None) else raw
        self._update_usage_vpn_banner(effective)
        if hasattr(self, "quality_panel"):
            self.quality_panel._apply_vpn_banner(effective)

    def display_welcome_message(self):
        self.output_text.insert(tk.END, "Welcome to Stena Line Internet Monitor!\n", "title")
        self.output_text.insert(tk.END, "\nThis tool helps you monitor your internet usage on the Stena Line network.\n\n", "normal")
        self.output_text.insert(tk.END, "Getting Started:\n", "subtitle")
        self.output_text.insert(tk.END, "1. Enter your password\n", "normal")
        self.output_text.insert(tk.END, "2. Click 'Fetch Data/Connect' to check your usage\n", "normal")
        self.output_text.insert(tk.END, "3. In case of getting 'cURL Error 6', click the 'Flush DNS' button.\n", "normal")
        self.output_text.insert(tk.END, "4. Save profiles for easier access next time\n\n", "normal")
        self.output_text.insert(tk.END, "Ready to check your internet usage status!\n", "normal")
    
    def display_error(self, error_message, error_details=None):
        """Display an error message in the output text area with formatting"""
        self.output_text.insert(tk.END, f"ERROR: {error_message}\n", "error")
        
        if error_details:
            self.output_text.insert(tk.END, "\nError Details:\n", "subtitle")
            self.output_text.insert(tk.END, f"{error_details}\n", "error_details")
        
        self.output_text.see(tk.END)  # Scroll to see the error

    def display_bad_credentials(self, username=None):
        """Show a friendly 'wrong credentials' message in the output box.

        Triggered when the portal returns
        error.code == 'error_logon_bad-login-or-password'.
        """
        self.output_text.insert(tk.END, "🔒 INVALID CREDENTIALS\n\n", "alert")
        self.output_text.insert(
            tk.END,
            "The username or password you entered is incorrect.\n"
            "Please double-check your credentials and try again.\n",
            "warning",
        )
        if username:
            self.output_text.insert(tk.END, "\nUsername tried: ", "label")
            self.output_text.insert(tk.END, f"{username}\n", "value")
        self.output_text.see(1.0)

    def display_mac_refresh_tip(self):
        """Show the MAC refresh / Wi-Fi tip in the output box.

        Only intended for connection failures (e.g. DNS NameResolutionError when
        the portal host can't be resolved), where refreshing the MAC address
        often gets the device a new captive-portal session.
        """
        self.output_text.insert(
            tk.END,
            "\n🔐 Trouble connecting or quota exhausted? Refresh your MAC "
            "address so the network sees you as a new device:\n"
            "Settings → Network & Internet → Wi-Fi → click your network → "
            "set 'Random hardware addresses' to Daily.\n",
            "warning",
        )
        self.output_text.insert(tk.END, "Open Wi-Fi settings →\n", "wifi_link")
        self.output_text.see(tk.END)
    
    def _ensure_portal_session(self, force=False):
        """Replicate the UCOPIA captive-portal handshake before authenticating.

        Cold start is a two-step on UCOPIA:
          1. First hit (no cookie) is intercepted and lands on
             `portal_degraded.php`, whose only useful effect is setting PHPSESSID.
          2. The next hit, now carrying that cookie, resolves to
             `https://internet.stenaline.com/<zone>/portal/` -- the zoned session
             that `authenticate` can actually attach to.
        A fresh device that POSTs `authenticate` while still in the degraded /
        unzoned state gets the portal HTML back ("not connected"). So we loop the
        GET until it reaches `/<zone>/portal/`, reusing the freshly-set cookie.
        The connect timeout is generous because the first SYN over satellite is
        frequently dropped. Safe to call repeatedly.

        Returns True if we reached `/<zone>/portal/`.
        """
        if self._portal_session_ready and not force:
            return True
        self._portal_session_ready = False
        last_err = None
        for i in range(PORTAL_HANDSHAKE_ATTEMPTS):
            try:
                resp = self.session.get(
                    PORTAL_LANDING_URL,
                    timeout=(PORTAL_CONNECT_TIMEOUT, 15),
                    allow_redirects=True,
                )
                self.portal_url = resp.url
                match = re.search(r"/(\d+)/portal/", resp.url or "")
                if match:
                    self.portal_site_id = match.group(1)
                has_cookie = "PHPSESSID" in self.session.cookies.get_dict()
                degraded = "portal_degraded" in (resp.url or "")
                print(f"[DEBUG] Portal handshake attempt {i + 1}/"
                      f"{PORTAL_HANDSHAKE_ATTEMPTS}: final_url={resp.url} "
                      f"site_id={self.portal_site_id} phpsessid={has_cookie} "
                      f"degraded={degraded}")
                if match:
                    # Reached the zoned portal -> session is ready.
                    self._portal_session_ready = True
                    return True
                # Landed on degraded (or an unzoned page). The cookie is now set,
                # so loop again to let the second GET reach /<zone>/portal/.
            except requests.exceptions.RequestException as e:
                last_err = e
                print(f"[DEBUG] Portal handshake attempt {i + 1}/"
                      f"{PORTAL_HANDSHAKE_ATTEMPTS} failed: {e}")
        # Didn't reach /<zone>/portal/. A PHPSESSID may still be set, leaving the
        # caller's HTML/redirect guards to take over.
        if last_err:
            print(f"[DEBUG] Portal handshake gave up: {last_err}")
        else:
            print("[DEBUG] Portal handshake stayed in degraded/unzoned state")
        return False

    def _portal_post(self, data, attempts=PORTAL_POST_ATTEMPTS):
        """POST to portal_api.php with timeouts, retry and backoff.

        The authenticate/disconnect actions trigger a slow backend round-trip to
        the ship gateway over a high-latency link, so a single attempt often
        times out even when the change took effect. Redirects are NOT followed so
        the caller can detect an unbound session (302 -> portal page).

        Returns (response, error). On total failure response is None.
        """
        last_err = None
        for i in range(attempts):
            try:
                resp = self.session.post(
                    API_URL,
                    data=data,
                    timeout=(PORTAL_CONNECT_TIMEOUT, PORTAL_READ_TIMEOUT),
                    allow_redirects=False,
                )
                return resp, None
            except (requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError) as e:
                last_err = e
                backoff = min(2 ** i, 8)
                print(f"[DEBUG] portal POST attempt {i + 1}/{attempts} failed: {e} "
                      f"(retrying in {backoff}s)")
                time.sleep(backoff)
        return None, last_err

    def _query_connection_state(self):
        """Lightweight `init` call used to verify state after a timeout.

        Returns (is_connected, data). is_connected is None if the check itself
        failed (so the caller can distinguish "not connected" from "unknown").
        """
        try:
            resp = self.session.post(
                API_URL,
                data={"action": API_ACTIONS["init"], "free_urls": ""},
                timeout=(PORTAL_CONNECT_TIMEOUT, 15),
                allow_redirects=False,
            )
            if resp.status_code == 200:
                d = resp.json()
                connected = bool(d.get("user", {}).get("isConnected", False)
                                 and d.get("step") == "FEEDBACK")
                return connected, d
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            print(f"[DEBUG] connection state query failed: {e}")
        return None, None

    def check_connection_status(self):
        """Check if already connected to the network on startup"""
        print("[DEBUG] check_connection_status() called")
        self.set_status("Checking connection status...", "info")
        
        # Start a new thread to check connection
        threading.Thread(target=self._check_connection_thread, daemon=True).start()
    
    def _check_connection_thread(self):
        """Thread to check connection status via API"""
        print("[DEBUG] _check_connection_thread() started")
        try:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Establish the captive-portal session first so `init` is bound to
            # this device (matches the browser flow).
            self._ensure_portal_session()
            
            data = {
                "action": API_ACTIONS["init"],
                "free_urls": ""
            }
            
            print(f"[DEBUG] Init request URL: {API_URL}")
            print(f"[DEBUG] Init request data: {data}")
            
            response = self.session.post(API_URL, data=data, timeout=10)
            print(f"[DEBUG] Init response status code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    print(f"[DEBUG] Init response keys: {list(response_data.keys())}")
                    
                    # Check if user is connected
                    step = response_data.get("step", "")
                    user_data = response_data.get("user", {})
                    is_connected = user_data.get("isConnected", False)
                    
                    if step == "FEEDBACK" and is_connected:
                        # User is already connected
                        username = user_data.get("login", {}).get("value", "Unknown")
                        profile = user_data.get("profile", {}).get("value", "Unknown")
                        
                        print(f"[DEBUG] User is connected: {username} ({profile})")
                        
                        # Update UI on main thread
                        self.root.after(0, lambda: self._display_connection_status(response_data))
                    else:
                        # Not connected
                        print("[DEBUG] User is not connected")
                        self.root.after(0, lambda: self.set_status("Not connected to network", "warning"))
                        self.root.after(0, lambda: self.output_text.insert(tk.END, "\n⚠️ Not currently connected to the network.\n", "warning"))
                        
                except json.JSONDecodeError as je:
                    print(f"[DEBUG] JSON decode error: {je}")
                    self.root.after(0, lambda: self.set_status("Ready", "info"))
            else:
                print(f"[DEBUG] Init request failed: {response.status_code}")
                self.root.after(0, lambda: self.set_status("Could not check connection", "warning"))
                
        except requests.exceptions.ConnectionError:
            print("[DEBUG] Connection error - likely not on Stena network")
            self.root.after(0, lambda: self.set_status("Not on Stena network", "warning"))
            self.root.after(0, lambda: self.output_text.insert(tk.END, "\n⚠️ Could not connect to Stena network. Make sure you're connected to the ship's WiFi.\n", "warning"))
        except requests.exceptions.Timeout:
            print("[DEBUG] Connection timeout")
            self.root.after(0, lambda: self.set_status("Connection timeout", "warning"))
        except Exception as e:
            print(f"[DEBUG] Error checking connection: {e}")
            self.root.after(0, lambda: self.set_status("Ready", "info"))
    
    def _display_connection_status(self, data):
        """Display the current connection status in the output area"""
        user_data = data.get("user", {})
        username = user_data.get("login", {}).get("value", "Unknown")
        profile = user_data.get("profile", {}).get("value", "Unknown")
        
        # Store current data for potential save
        self.current_data = data
        
        # Auto-fill username if empty
        if not self.username_var.get():
            self.username_var.set(username)
            self.password_var.set(username)  # Password is same as username
        
        # Clear and display connection info
        self.clear_output()
        
        self.output_text.insert(tk.END, "✓ ALREADY CONNECTED\n\n", "title")
        
        self.output_text.insert(tk.END, "Connected as: ", "label")
        self.output_text.insert(tk.END, f"{username}\n", "value")
        
        self.output_text.insert(tk.END, "Profile: ", "label")
        self.output_text.insert(tk.END, f"{profile}\n\n", "value")
        
        # Show usage data if available
        consumed = user_data.get("consumedData", {})
        if consumed:
            try:
                download_bytes = int(consumed.get("download", {}).get("value", 0))
                upload_bytes = int(consumed.get("upload", {}).get("value", 0))
                
                self.output_text.insert(tk.END, "DATA USAGE\n", "section")
                self.output_text.insert(tk.END, "Download: ", "label")
                self.output_text.insert(tk.END, f"{self.format_bytes(download_bytes)}\n", "value")
                self.output_text.insert(tk.END, "Upload: ", "label")
                self.output_text.insert(tk.END, f"{self.format_bytes(upload_bytes)}\n", "value")
                self.output_text.insert(tk.END, "Total: ", "label")
                self.output_text.insert(tk.END, f"{self.format_bytes(download_bytes + upload_bytes)}\n\n", "value")
                
                # Quota info
                extra_data = consumed.get("extra", {}).get("value", [])
                for item in extra_data:
                    if item.get("isSumQuota") and item.get("isDisconnectQuota"):
                        total_quota = item.get("total", {}).get("upload")
                        available = item.get("available", {}).get("upload")
                        if total_quota and available:
                            used = total_quota - available
                            usage_pct = (used / total_quota) * 100
                            self.output_text.insert(tk.END, "QUOTA\n", "section")
                            self.output_text.insert(tk.END, "Total Quota: ", "label")
                            self.output_text.insert(tk.END, f"{self.format_bytes(total_quota)}\n", "value")
                            self.output_text.insert(tk.END, "Used: ", "label")
                            if usage_pct > 80:
                                self.output_text.insert(tk.END, f"{self.format_bytes(used)} ({usage_pct:.1f}%)\n", "warning")
                            else:
                                self.output_text.insert(tk.END, f"{self.format_bytes(used)} ({usage_pct:.1f}%)\n", "value")
                            self.output_text.insert(tk.END, "Remaining: ", "label")
                            self.output_text.insert(tk.END, f"{self.format_bytes(available)}\n\n", "value")

                            self._show_quota_gauge(used)
                        break
                
                # Time info
                renew_timestamp = int(consumed.get("renewTimestamp", {}).get("value", 0))
                if renew_timestamp:
                    from datetime import datetime, timedelta
                    current_time = datetime.now().timestamp()
                    time_remaining_seconds = renew_timestamp - current_time
                    time_remaining = timedelta(seconds=max(0, time_remaining_seconds))
                    
                    self.output_text.insert(tk.END, "TIME INFO\n", "section")
                    self.output_text.insert(tk.END, "Renewal in: ", "label")
                    self.output_text.insert(tk.END, f"{time_remaining.days}d {time_remaining.seconds // 3600}h {(time_remaining.seconds % 3600) // 60}m\n", "value")
                    
            except (ValueError, TypeError) as e:
                print(f"[DEBUG] Error parsing usage data: {e}")
        
        self.output_text.insert(tk.END, f"\nLast checked: {datetime.now().strftime('%H:%M:%S')}\n", "footer")
        self.output_text.see(1.0)
        
        self.set_status(f"Connected as {username}", "success")
    
    def load_profiles(self):
        print("[DEBUG] Loading profiles from profiles.json...")
        try:
            if os.path.exists('profiles.json'):
                print("[DEBUG] profiles.json exists, reading file...")
                with open('profiles.json', 'r') as f:
                    profiles = json.load(f)
                print(f"[DEBUG] Loaded {len(profiles)} profiles: {list(profiles.keys())}")
                return profiles
            print("[DEBUG] profiles.json does not exist, returning empty dict")
            return {}
        except Exception as e:
            print(f"[DEBUG] Error loading profiles: {e}")
            error_details = traceback.format_exc()
            self.root.after(0, lambda: self.display_error(f"Failed to load profiles: {e}", error_details))
            return {}
    
    def save_profiles(self):
        print(f"[DEBUG] Saving {len(self.profiles)} profiles to profiles.json...")
        try:
            with open('profiles.json', 'w') as f:
                json.dump(self.profiles, f)
            print("[DEBUG] Profiles saved successfully")
        except Exception as e:
            print(f"[DEBUG] Error saving profiles: {e}")
            error_details = traceback.format_exc()
            self.display_error(f"Failed to save profiles: {e}", error_details)
    
    def update_profile_list(self):
        try:
            self.profile_combo['values'] = list(self.profiles.keys())
        except Exception as e:
            error_details = traceback.format_exc()
            self.display_error(f"Failed to update profile list: {e}", error_details)
    
    def load_selected_profile(self, event=None):
        print("[DEBUG] Loading selected profile...")
        try:
            profile_name = self.profile_var.get()
            print(f"[DEBUG] Selected profile: '{profile_name}'")
            if profile_name in self.profiles:
                profile = self.profiles[profile_name]
                username = profile.get('username', '')
                password = profile.get('password', '')
                print(f"[DEBUG] Profile data - Username: '{username}', Password: {'*' * len(password)}")
                self.username_var.set(username)
                self.password_var.set(password)
                self.set_status(f"Loaded profile: {profile_name}", "success")
                print(f"[DEBUG] Profile '{profile_name}' loaded successfully")
            else:
                print(f"[DEBUG] Profile '{profile_name}' not found in profiles")
        except Exception as e:
            print(f"[DEBUG] Error loading selected profile: {e}")
            error_details = traceback.format_exc()
            self.display_error(f"Failed to load profile: {e}", error_details)
    
    def save_profile(self):
        print("[DEBUG] Saving new profile...")
        try:
            profile_name = self.profile_name_var.get().strip()
            username = self.username_var.get()
            password = self.password_var.get()
            print(f"[DEBUG] Profile name: '{profile_name}', Username: '{username}', Password: {'*' * len(password)}")
            
            if not profile_name:
                print("[DEBUG] Profile name is empty")
                messagebox.showerror("Error", "Profile name cannot be empty")
                return
            
            self.profiles[profile_name] = {
                'username': username,
                'password': password
            }
            print(f"[DEBUG] Profile '{profile_name}' added to profiles dictionary")
            self.save_profiles()
            self.update_profile_list()
            self.profile_var.set(profile_name)
            self.profile_name_var.set('')
            self.set_status(f"Profile '{profile_name}' saved", "success")
            print(f"[DEBUG] Profile '{profile_name}' saved successfully")
        except Exception as e:
            print(f"[DEBUG] Error saving profile: {e}")
            error_details = traceback.format_exc()
            self.display_error(f"Failed to save profile: {e}", error_details)
    
    def delete_profile(self):
        print("[DEBUG] Deleting profile...")
        try:
            profile_name = self.profile_var.get()
            print(f"[DEBUG] Profile to delete: '{profile_name}'")
            if profile_name in self.profiles:
                del self.profiles[profile_name]
                print(f"[DEBUG] Profile '{profile_name}' removed from profiles dictionary")
                self.save_profiles()
                self.update_profile_list()
                self.profile_var.set('')
                self.set_status(f"Profile '{profile_name}' deleted", "warning")
                print(f"[DEBUG] Profile '{profile_name}' deleted successfully")
            else:
                print(f"[DEBUG] No profile selected or profile '{profile_name}' not found")
                messagebox.showerror("Error", "No profile selected")
        except Exception as e:
            print(f"[DEBUG] Error deleting profile: {e}")
            error_details = traceback.format_exc()
            self.display_error(f"Failed to delete profile: {e}", error_details)
    
    def set_status(self, message, status_type="info"):
        self.status_var.set(message)
        theme = get_theme()
        
        if status_type == "success":
            self.status_indicator.itemconfig(self.status_light, fill=theme["success"])
        elif status_type == "warning":
            self.status_indicator.itemconfig(self.status_light, fill=theme["warning"])
        elif status_type == "error":
            self.status_indicator.itemconfig(self.status_light, fill=theme["error"])
        else:  # info
            self.status_indicator.itemconfig(self.status_light, fill=theme["accent"])
    
    def fetch_data(self):
        print("[DEBUG] fetch_data() called")
        # Make sure usage results are visible
        self.notebook.select(self.usage_tab)
        # Disable the button during fetch
        self.fetch_btn.set_enabled(False)
        self.set_status("Fetching data... Please wait.", "info")
        
        # Clear previous output and show fetching message
        self.clear_output()
        self.output_text.insert(tk.END, "Fetching data... Please wait.\n", "fetching")
        
        # Start a new thread to fetch data
        print("[DEBUG] Starting fetch data thread...")
        threading.Thread(target=self._fetch_data_thread, daemon=True).start()
    
    def _fetch_data_thread(self):
        print("[DEBUG] _fetch_data_thread() started")
        try:
            # Get credentials
            username = self.username_var.get()
            password = self.password_var.get()
            print(f"[DEBUG] Credentials - Username: '{username}', Password: {'*' * len(password)}")
        
            if not username or not password:
                print("[DEBUG] Missing credentials - username or password is empty")
                self.root.after(0, lambda: messagebox.showerror("Error", "Username and password are required"))
                self.root.after(0, lambda: self.set_status("Error: Missing credentials", "error"))
                self.root.after(0, lambda: self.fetch_btn.set_enabled(True))
                return

            # Use Python requests library instead of curl
            import requests
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            print("[DEBUG] Imports completed, warnings disabled")
            
            data = {
                "action": API_ACTIONS["authenticate"],
                "switch_package": "true",
                "login": username,
                "password": password,
                "policy_accept": "true",
                "private_policy_accept": "false",
                "from_ajax": "true",
                "wispr_mode": "false"
            }
            print(f"[DEBUG] Request URL: {API_URL}")
            print(f"[DEBUG] Request headers: {API_HEADERS}")
            print(f"[DEBUG] Request data (password masked): {dict(data, password='*' * len(password))}")
            
            # UCOPIA only accepts `authenticate` when a fresh GET to
            # /<zone>/portal/ immediately precedes it (the portal is a stateful
            # step-machine and the POST rotates PHPSESSID). A cached/stale
            # handshake makes the first POST return the portal HTML instead of
            # JSON, so force a fresh handshake right before authenticating.
            self._ensure_portal_session(force=True)
            
            # Make the request with retry/backoff (SSL verification disabled,
            # equivalent to curl -k). Redirects are not followed so we can detect
            # an unbound session.
            print("[DEBUG] Making POST request (with retry)...")
            response, post_err = self._portal_post(data)
            
            if response is None:
                # Every attempt timed out / connection failed. The authenticate
                # action may still have taken effect on the gateway, so verify
                # via init before declaring failure.
                print(f"[DEBUG] authenticate POST failed after retries: {post_err}")
                is_connected, state = self._query_connection_state()
                if is_connected and state is not None:
                    print("[DEBUG] Verified connected despite POST timeout")
                    self.current_data = state
                    self.root.after(0, lambda: self.display_info(state))
                    self.root.after(0, lambda: self.set_status(
                        "Connected (confirmed after timeout)", "success"))
                    return
                raise post_err if post_err else requests.exceptions.ConnectionError(
                    "authenticate failed after retries")
            
            # A redirect to the portal page means our session wasn't bound; redo
            # the handshake once and retry the authenticate.
            if response.status_code in (301, 302, 303, 307, 308):
                print(f"[DEBUG] authenticate redirected ({response.status_code}) "
                      f"-> re-handshaking and retrying")
                self._ensure_portal_session(force=True)
                response, post_err = self._portal_post(data)
                if response is None:
                    raise post_err if post_err else requests.exceptions.ConnectionError(
                        "authenticate failed after re-handshake")
            
            print(f"[DEBUG] Response status code: {response.status_code}")
            print(f"[DEBUG] Response headers: {dict(response.headers)}")
            print(f"[DEBUG] Response content length: {len(response.content)} bytes")
            
            # An unbound session can return the portal HTML page with a 200
            # status instead of JSON. Detect that, re-handshake and retry once.
            content_type = response.headers.get("Content-Type", "")
            looks_like_html = (
                "html" in content_type.lower()
                or response.text.lstrip()[:15].lower().startswith(("<!doctype", "<html"))
            )
            if response.status_code == 200 and looks_like_html:
                print("[DEBUG] authenticate returned HTML (unbound session) "
                      "-> re-handshaking and retrying")
                self._ensure_portal_session(force=True)
                retry_resp, retry_err = self._portal_post(data)
                if retry_resp is not None:
                    response = retry_resp
            
            if response.status_code == 200:
                print("[DEBUG] HTTP 200 response received")
                try:
                    data = response.json()
                    print(f"[DEBUG] JSON parsing successful, response type: {type(data)}")
                    print(f"[DEBUG] Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    
                    # Check if authentication was successful
                    if "user" in data and "consumedData" in data["user"]:
                        print("[DEBUG] Normal response detected - user data with consumedData found")
                        self.current_data = data
                        self.root.after(0, lambda: self.display_info(data))
                        self.root.after(0, lambda: self.set_status("Data fetched successfully", "success"))
                    elif "errorMsg" in data:
                        # Extract API error message if available
                        error_msg = data.get("errorMsg", "Authentication failed or no data returned")
                        print(f"[DEBUG] API error response detected: {error_msg}")
                        self.root.after(0, lambda: self.clear_output())
                        self.root.after(0, lambda: self.display_error(f"API Error: {error_msg}", json.dumps(data, indent=2)))
                        self.root.after(0, lambda: self.set_status("Error: API returned an error", "error"))
                    elif "error" in data and data["error"].get("code") == "error_logon_volume-quota-reached-detail":
                        print("[DEBUG] Quota reached response detected")
                        self.current_data = data
                        self.root.after(0, lambda: self.display_quota_reached_info(data))
                        self.root.after(0, lambda: self.set_status("Quota limit reached", "warning"))
                    elif "error" in data and data["error"].get("code") == "error_logon_bad-login-or-password":
                        print("[DEBUG] Bad login/password response detected")
                        self.root.after(0, lambda: self.clear_output())
                        self.root.after(0, lambda: self.display_bad_credentials(username))
                        self.root.after(0, lambda: self.set_status("Invalid credentials", "error"))
                    else:
                        print("[DEBUG] Unrecognized response format")
                        print(f"[DEBUG] Full response data: {json.dumps(data, indent=2)[:500]}...")
                        error_msg = "Authentication failed or no data returned"
                        self.root.after(0, lambda: self.clear_output())
                        self.root.after(0, lambda: self.display_error(error_msg, json.dumps(data, indent=2)))
                        self.root.after(0, lambda: self.set_status("Error: Authentication failed", "error"))
                except json.JSONDecodeError as je:
                    print(f"[DEBUG] JSON decode error: {je}")
                    print(f"[DEBUG] Raw response text: {response.text[:200]}...")
                    self.root.after(0, lambda: self.clear_output())
                    self.root.after(0, lambda: self.display_error(
                        "Error decoding JSON response", 
                        f"JSON Error: {str(je)}\n\nResponse Content:\n{response.text[:500]}...(truncated)"
                    ))
                    self.root.after(0, lambda: self.set_status("Error: Invalid response format", "error"))
            else:
                print(f"[DEBUG] HTTP request failed with status code: {response.status_code}")
                print(f"[DEBUG] Response text: {response.text[:200]}...")
                self.root.after(0, lambda: self.clear_output())
                self.root.after(0, lambda: self.display_error(
                    f"HTTP request failed with status code: {response.status_code}", 
                    f"Response content: {response.text[:500]}...(truncated)"
                ))
                self.root.after(0, lambda: self.set_status("Error: Request failed", "error"))
        except requests.exceptions.ConnectionError as ce:
            print(f"[DEBUG] Connection error: {ce}")
            self.root.after(0, lambda: self.clear_output())
            self.root.after(0, lambda: self.display_error(
                "Connection error occurred. You might need to flush DNS.", 
                f"Error details: {str(ce)}\n\nTry clicking the 'Flush DNS' button to resolve this issue."
            ))
            self.root.after(0, lambda: self.display_mac_refresh_tip())
            self.root.after(0, lambda: self.set_status("Error: Connection failed", "error"))
        except Exception as e:
            # Get the full traceback for detailed error information
            error_traceback = traceback.format_exc()
            print(f"[DEBUG] Unexpected error in _fetch_data_thread: {e}")
            print(f"[DEBUG] Error traceback: {error_traceback}")
            
            self.root.after(0, lambda: self.clear_output())
            self.root.after(0, lambda: self.display_error(
                f"Error executing request: {e}", 
                error_traceback
            ))
            self.root.after(0, lambda: self.set_status(f"Error: {str(e)[:50]}", "error"))
        finally:
            print("[DEBUG] _fetch_data_thread completed, re-enabling button")
            # Re-enable the button
            self.root.after(0, lambda: self.fetch_btn.set_enabled(True))
    
    def format_bytes(self, bytes_value):
        try:
            return f"{bytes_value / 1024 / 1024:.1f} MB"
        except (TypeError, ValueError) as e:
            # Handle type conversion errors
            self.display_error(f"Error formatting bytes: {e}", f"Value was: {bytes_value}")
            return "Error"
    
    def display_quota_reached_info(self, data):
        print("[DEBUG] display_quota_reached_info() called")
        try:
            # Clear previous output
            self.clear_output()
            
            # Extract error data
            error_value = data.get("error", {}).get("value", {})
            
            if not error_value:
                self.display_error("Missing quota details in API response", json.dumps(data, indent=2))
                return
            
            try:
                consumed_up = int(error_value.get("consumedUp", 0))
                consumed_down = int(error_value.get("consumedDown", 0))
                threshold_up = int(error_value.get("thresoldUp", 0))
                
                # Handle negative threshold values
                threshold_down_raw = int(error_value.get("thresoldDown", 0))
                threshold_down = abs(threshold_down_raw) if threshold_down_raw < 0 else threshold_down_raw
                
                renew_timestamp = int(error_value.get("renewTimeStamp", 0))
                
                # Calculate total consumption
                total_consumed = consumed_up + consumed_down
                total_consumed_mb = total_consumed / (1024 * 1024)
                threshold_up_mb = threshold_up / (1024 * 1024)
            except (ValueError, TypeError) as e:
                # Handle conversion errors
                self.display_error(f"Invalid data format in quota-reached response: {e}", 
                                f"Data received: {json.dumps(error_value, indent=2)}")
                return
            
            # Calculate time remaining
            current_time = datetime.now().timestamp()
            time_remaining_seconds = renew_timestamp - current_time
            time_remaining = timedelta(seconds=max(0, time_remaining_seconds))
            
            # Display information with formatting
            self.output_text.insert(tk.END, "QUOTA LIMIT REACHED\n\n", "alert")
            
            # Display quota alert message
            self.output_text.insert(tk.END, "Your internet quota has been reached. You will have limited or no internet access until the renewal time.\n\n", "warning")
            
            # Data usage section
            self.output_text.insert(tk.END, "DATA USAGE\n", "section")
            
            self.output_text.insert(tk.END, "Download: ", "label")
            self.output_text.insert(tk.END, f"{self.format_bytes(consumed_down)}\n", "value")
            
            self.output_text.insert(tk.END, "Upload: ", "label")
            self.output_text.insert(tk.END, f"{self.format_bytes(consumed_up)}\n", "value")
            
            self.output_text.insert(tk.END, "Total Usage: ", "label")
            self.output_text.insert(tk.END, f"{self.format_bytes(consumed_up + consumed_down)}\n\n", "value")
            
            # Quota information section
            self.output_text.insert(tk.END, "QUOTA INFORMATION\n", "section")
        
            if total_consumed > threshold_up and threshold_up > 0:
                self.output_text.insert(tk.END, "Total Data Limit: ", "label")
                self.output_text.insert(tk.END, f"{self.format_bytes(threshold_up)}\n", "value")
                
                usage_percentage = (total_consumed / threshold_up) * 100
                self.output_text.insert(tk.END, "Total Usage: ", "label")
                self.output_text.insert(tk.END, f"{usage_percentage:.1f}% ", "warning")
                
                # Calculate actual overage
                excess_mb = total_consumed_mb - threshold_up_mb
                if excess_mb > 0:
                    self.output_text.insert(tk.END, f"(Exceeded by {excess_mb:.1f} MB)\n", "warning")
                else:
                    self.output_text.insert(tk.END, "(Limit reached)\n", "warning")
            else:

                if threshold_up > 0:
                    self.output_text.insert(tk.END, "Upload Limit: ", "label")
                    self.output_text.insert(tk.END, f"{self.format_bytes(threshold_up)}\n", "value")
                    
                    upload_percentage = (consumed_up / threshold_up) * 100
                    self.output_text.insert(tk.END, "Upload Usage: ", "label")
                    self.output_text.insert(tk.END, f"{upload_percentage:.1f}% (Limit reached)\n", "warning")
            
            # Time information
            self.output_text.insert(tk.END, "\nTIME INFORMATION\n", "section")
            
            self.output_text.insert(tk.END, "Time until renewal: ", "label")
            self.output_text.insert(tk.END, f"{time_remaining.days} days, {time_remaining.seconds // 3600} hours, {(time_remaining.seconds % 3600) // 60} minutes\n", "value")
            
            renewal_time = datetime.fromtimestamp(renew_timestamp)
            self.output_text.insert(tk.END, "Renewal date: ", "label")
            self.output_text.insert(tk.END, f"{renewal_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n", "value")
            
            # Footer
            self.output_text.insert(tk.END, f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", "footer")
            
            # Scroll to the top to see all information
            self.output_text.see(1.0)
            
        except Exception as e:
            # Get the full traceback for detailed error information
            error_traceback = traceback.format_exc()
            self.display_error(
                f"Error processing quota-reached data: {e}", 
                f"Traceback:\n{error_traceback}\n\nData received:\n{json.dumps(data, indent=2)[:500]}...(truncated)"
            )
    
    def display_info(self, data):
        print("[DEBUG] display_info() called")
        if not data:
            print("[DEBUG] No data provided to display_info")
            self.output_text.insert(tk.END, "No data available\n")
            return
        
        try:
            print(f"[DEBUG] Processing data with keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            # Clear previous output
            self.clear_output()
            
            # Extract user consumption data
            consumed = data.get("user", {}).get("consumedData", {})
            
            if not consumed:
                self.display_error("Missing consumption data in API response", json.dumps(data, indent=2))
                return
            
            try:
                download_bytes = int(consumed.get("download", {}).get("value", 0))
                upload_bytes = int(consumed.get("upload", {}).get("value", 0))
            except (ValueError, TypeError) as e:
                # Handle conversion errors
                self.display_error(f"Invalid data format: {e}", f"Data received: {json.dumps(consumed, indent=2)}")
                return
            
            # Get quota information
            extra_data = consumed.get("extra", {}).get("value", [])
            quota_info = None
            for item in extra_data:
                if item.get("isSumQuota") and item.get("isDisconnectQuota"):
                    quota_info = item
                    break
            
            # Get time information
            try:
                renew_timestamp = int(consumed.get("renewTimestamp", {}).get("value", 0))
                current_timestamp = int(consumed.get("timestamp", {}).get("value", 0))
            except (ValueError, TypeError) as e:
                self.display_error(f"Invalid timestamp format: {e}", f"Data received: {json.dumps(consumed, indent=2)}")
                # Set default values to avoid further errors
                renew_timestamp = int(datetime.now().timestamp()) + 86400  # Default to 1 day
                current_timestamp = int(datetime.now().timestamp())
            
            # Calculate time remaining
            current_time = datetime.now().timestamp()
            time_remaining_seconds = renew_timestamp - current_time
            time_remaining = timedelta(seconds=max(0, time_remaining_seconds))
            
            # Display information with formatting
            self.output_text.insert(tk.END, "INTERNET USAGE SUMMARY\n\n", "header")
            
            # User info
            username = data.get('user', {}).get('login', {}).get('value', 'N/A')
            profile = data.get('user', {}).get('profile', {}).get('value', 'N/A')
            
            self.output_text.insert(tk.END, "User: ", "label")
            self.output_text.insert(tk.END, f"{username}\n", "value")
            
            self.output_text.insert(tk.END, "Profile: ", "label")
            self.output_text.insert(tk.END, f"{profile}\n\n", "value")
            
            # Data usage section
            self.output_text.insert(tk.END, "DATA USAGE\n", "section")
            
            self.output_text.insert(tk.END, "Download: ", "label")
            self.output_text.insert(tk.END, f"{self.format_bytes(download_bytes)}\n", "value")
            
            self.output_text.insert(tk.END, "Upload: ", "label")
            self.output_text.insert(tk.END, f"{self.format_bytes(upload_bytes)}\n", "value")
            
            self.output_text.insert(tk.END, "Total Usage: ", "label")
            self.output_text.insert(tk.END, f"{self.format_bytes(download_bytes + upload_bytes)}\n\n", "value")
            
            # Quota information
            if quota_info:
                try:
                    total_upload_quota = quota_info.get("total", {}).get("upload")
                    available_upload = quota_info.get("available", {}).get("upload")
                    
                    if total_upload_quota is not None:
                        self.output_text.insert(tk.END, "QUOTA INFORMATION\n", "section")
                        
                        self.output_text.insert(tk.END, "Total Traffic Quota: ", "label")
                        self.output_text.insert(tk.END, f"{self.format_bytes(total_upload_quota)}\n", "value")
                        
                        if available_upload is not None:
                            self.output_text.insert(tk.END, "Remaining: ", "label")
                            self.output_text.insert(tk.END, f"{self.format_bytes(available_upload)}\n", "value")
                            
                            usage_percentage = (total_upload_quota - available_upload) / total_upload_quota * 100
                            self.output_text.insert(tk.END, "Used: ", "label")
                            
                            # Use warning color if usage is high
                            used_bytes = total_upload_quota - available_upload
                            if usage_percentage > 80:
                                self.output_text.insert(tk.END, f"{self.format_bytes(used_bytes)} ({usage_percentage:.1f}%)\n\n", "warning")
                            else:
                                self.output_text.insert(tk.END, f"{self.format_bytes(used_bytes)} ({usage_percentage:.1f}%)\n\n", "value")

                            self._show_quota_gauge(used_bytes)
                except (TypeError, ValueError) as e:
                    # Handle calculation errors
                    self.output_text.insert(tk.END, "Error processing quota information:\n", "error")
                    self.output_text.insert(tk.END, f"{str(e)}\n\n", "error_details")
            
            # Time information
            self.output_text.insert(tk.END, "TIME INFORMATION\n", "section")
            
            self.output_text.insert(tk.END, "Time until renewal: ", "label")
            self.output_text.insert(tk.END, f"{time_remaining.days} days, {time_remaining.seconds // 3600} hours, {(time_remaining.seconds % 3600) // 60} minutes\n", "value")
            
            renewal_time = datetime.fromtimestamp(renew_timestamp)
            self.output_text.insert(tk.END, "Renewal date: ", "label")
            self.output_text.insert(tk.END, f"{renewal_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n", "value")
            
            # Footer
            self.output_text.insert(tk.END, f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", "footer")
            
            # Scroll to the top to see all information
            self.output_text.see(1.0)
            
        except Exception as e:
            # Get the full traceback for detailed error information
            error_traceback = traceback.format_exc()
            self.display_error(
                f"Error processing data: {e}", 
                f"Traceback:\n{error_traceback}\n\nData received:\n{json.dumps(data, indent=2)[:500]}...(truncated)"
            )
            
    def _layout_profile_row(self, event=None):
        """Flip the profile buttons between inline (right of the entry) and
        wrapped (own row below the entry) based on available width, so they
        never get clipped on narrow windows.
        """
        frame = self.new_profile_frame
        frame_w = frame.winfo_width()
        if frame_w <= 1:
            return
        # Inline-fit threshold: label + entry + at least the buttons' min width.
        label_w = self.new_profile_label.winfo_reqwidth() + 8
        entry_w = self.profile_name_entry.winfo_reqwidth() + 16
        buttons_min = sum(b.min_width for b in self._profile_buttons) + 8 * len(self._profile_buttons)
        wrap = frame_w < (label_w + entry_w + buttons_min)
        if wrap == getattr(self, "_profile_row_wrapped", None):
            return
        self._profile_row_wrapped = wrap
        if wrap:
            self.profile_buttons_frame.grid_configure(
                row=1, column=0, columnspan=4, sticky="ew", padx=0, pady=(0, 4)
            )
        else:
            self.profile_buttons_frame.grid_configure(
                row=0, column=2, columnspan=2, sticky="ew", padx=0, pady=4
            )
        # Force the inner button row to re-evaluate its column count for the
        # new frame width on the next idle tick.
        self._button_row_cols.pop("profile", None)
        self.profile_buttons_frame.after_idle(
            lambda: self._layout_button_row(self._profile_buttons, self.profile_buttons_frame, "profile")
        )

    def _layout_button_row(self, buttons, frame, key, event=None):
        """Re-flow a button row to fit the current frame width.

        Each button declares its own intrinsic `min_width`; we pack as many
        per row as fit, using the widest button's min as the column floor so
        no label gets clipped. Remaining buttons wrap to additional rows
        and the last row is balanced (e.g. 4 btns + 3-col fit -> 2x2).

        `key` is a unique identifier per row used to cache the active column
        count and skip no-op relayouts during drag-resize.
        """
        if not buttons:
            return
        frame_w = frame.winfo_width()
        if frame_w <= 1:
            return
        pad_x = 4  # gap on each side of a cell -> 8px gap between buttons
        min_w = max(b.min_width for b in buttons) + pad_x * 2
        max_cols = max(1, min(len(buttons), frame_w // min_w))
        rows = -(-len(buttons) // max_cols)  # ceil division
        cols = -(-len(buttons) // rows)
        if self._button_row_cols.get(key) == cols:
            return
        self._button_row_cols[key] = cols
        uniform = f"btnrow_{key}"
        for c in range(len(buttons)):
            frame.grid_columnconfigure(
                c, weight=1 if c < cols else 0, uniform=uniform if c < cols else ""
            )
        for i, btn in enumerate(buttons):
            r, c = divmod(i, cols)
            btn.grid(row=r, column=c, sticky="ew", padx=pad_x, pady=4)

    def clear_output(self):
        self._hide_quota_gauge()
        self.output_text.delete(1.0, tk.END)

    def _show_quota_gauge(self, used_bytes):
        """Show the right-side quota gauge with the given used-bytes value."""
        self.quota_gauge.set_value(used_bytes)
        if not self.gauge_panel.winfo_ismapped():
            # Pack to the right of the text widget. `before=output_text` ensures
            # the text widget keeps using the remaining space correctly when
            # the panel is re-shown after a hide.
            self.gauge_panel.pack(
                side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=8,
                before=self.output_text,
            )

    def _hide_quota_gauge(self):
        if self.gauge_panel.winfo_ismapped():
            self.gauge_panel.pack_forget()
        
    def open_wifi_settings(self):
        """Open the Windows Wi-Fi settings page (where MAC randomization lives)."""
        try:
            os.startfile('ms-settings:network-wifi')
            self.set_status("Opened Wi-Fi settings", "info")
        except Exception as e:
            print(f"[DEBUG] Failed to open Wi-Fi settings: {e}")
            self.set_status("Could not open Wi-Fi settings", "warning")

    def flush_dns(self):
        """Flush DNS cache to resolve potential connection issues"""
        print("[DEBUG] flush_dns() called")
        try:
            self.set_status("Flushing DNS cache...", "info")
            current_os = platform.system()
            print(f"[DEBUG] Operating system detected: {current_os}")
            
            # Create command based on operating system
            if current_os == 'Windows':
                print("[DEBUG] Using Windows DNS flush command")
                # Create hidden window for Windows
                result = subprocess.run(
                    ["ipconfig", "/flushdns"], 
                    capture_output=True, 
                    text=True,
                    creationflags=CREATE_NO_WINDOW
                )
            else:
                print("[DEBUG] Using non-Windows DNS flush command")
                # For non-Windows platforms (will need to be modified for specific OS)
                result = subprocess.run(
                    ["sudo", "killall", "-HUP", "mDNSResponder"], 
                    capture_output=True, 
                    text=True
                )
            
            print(f"[DEBUG] DNS flush command return code: {result.returncode}")
            print(f"[DEBUG] DNS flush stdout: {result.stdout}")
            print(f"[DEBUG] DNS flush stderr: {result.stderr}")
                
            if result.returncode == 0:
                print("[DEBUG] DNS flush successful")
                self.output_text.insert(tk.END, "DNS cache has been successfully flushed.\n", "normal")
                self.output_text.insert(tk.END, f"Result: {result.stdout}\n", "normal")
                self.set_status("DNS cache flushed successfully", "success")
            else:
                print("[DEBUG] DNS flush failed")
                self.display_error(
                    "Failed to flush DNS cache", 
                    f"Command output:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
                )
                self.set_status("Failed to flush DNS cache", "error")
        except Exception as e:
            print(f"[DEBUG] Error in flush_dns: {e}")
            error_details = traceback.format_exc()
            self.display_error(f"Error flushing DNS: {e}", error_details)
            self.set_status("Error flushing DNS", "error")
    
    def disconnect_profile(self):
        """Disconnect the current user from the Stena network"""
        print("[DEBUG] disconnect_profile() called")
        username = self.username_var.get()
        
        if not username:
            print("[DEBUG] No username provided for disconnect")
            messagebox.showerror("Error", "No username to disconnect. Please enter a username or select a profile.")
            return
        
        # Make sure usage results are visible
        self.notebook.select(self.usage_tab)
        # Disable the button during disconnect
        self.disconnect_btn.set_enabled(False)
        self.set_status("Disconnecting...", "info")
        
        # Clear previous output and show disconnecting message
        self.clear_output()
        self.output_text.insert(tk.END, f"Disconnecting user '{username}'... Please wait.\n", "fetching")
        
        # Start a new thread to perform disconnect
        print(f"[DEBUG] Starting disconnect thread for user: {username}")
        threading.Thread(target=self._disconnect_thread, args=(username,), daemon=True).start()
    
    def _disconnect_thread(self, username):
        """Thread to perform the disconnect API call"""
        print(f"[DEBUG] _disconnect_thread() started for user: {username}")
        try:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            data = {
                "action": API_ACTIONS["disconnect"],
                "login": username
            }
            
            print(f"[DEBUG] Disconnect request URL: {API_URL}")
            print(f"[DEBUG] Disconnect request data: {data}")
            
            # Same UCOPIA requirement as authenticate: a fresh GET to
            # /<zone>/portal/ must immediately precede the action.
            self._ensure_portal_session(force=True)
            
            # Make the disconnect request with retry/backoff (slow gateway link).
            print("[DEBUG] Making POST request for disconnect (with retry)...")
            response, post_err = self._portal_post(data)
            
            if response is None:
                # All attempts timed out. The disconnect may still have applied,
                # so verify via init before declaring failure.
                print(f"[DEBUG] disconnect POST failed after retries: {post_err}")
                is_connected, _ = self._query_connection_state()
                if is_connected is False:
                    print("[DEBUG] Verified disconnected despite POST timeout")
                    self.root.after(0, lambda: self.clear_output())
                    self.root.after(0, lambda: self.output_text.insert(
                        tk.END,
                        f"Successfully disconnected user '{username}' from the network.\n\n",
                        "subtitle"))
                    self.root.after(0, lambda: self.set_status(
                        "Disconnected (confirmed after timeout)", "success"))
                    return
                raise post_err if post_err else requests.exceptions.ConnectionError(
                    "disconnect failed after retries")
            
            print(f"[DEBUG] Disconnect response status code: {response.status_code}")
            print(f"[DEBUG] Disconnect response content: {response.text[:500]}")
            
            if response.status_code == 200:
                try:
                    response_data = response.json()
                    print(f"[DEBUG] Disconnect JSON response: {response_data}")
                    
                    # Check for successful disconnect
                    info_code = response_data.get("info", {}).get("code", "")
                    
                    if info_code == "disconnect_success":
                        print("[DEBUG] Disconnect successful")
                        self.root.after(0, lambda: self.clear_output())
                        self.root.after(0, lambda: self.output_text.insert(
                            tk.END, 
                            f"Successfully disconnected user '{username}' from the network.\n\n", 
                            "subtitle"
                        ))
                        self.root.after(0, lambda: self.output_text.insert(
                            tk.END, 
                            "You can now connect with a different profile or close the application.\n", 
                            "normal"
                        ))
                        self.root.after(0, lambda: self.set_status("Disconnected successfully", "success"))
                    else:
                        # Handle other responses
                        print(f"[DEBUG] Disconnect response code: {info_code}")
                        self.root.after(0, lambda: self.clear_output())
                        self.root.after(0, lambda: self.display_error(
                            f"Disconnect returned unexpected response",
                            json.dumps(response_data, indent=2)
                        ))
                        self.root.after(0, lambda: self.set_status("Disconnect: unexpected response", "warning"))
                        
                except json.JSONDecodeError as je:
                    print(f"[DEBUG] JSON decode error on disconnect: {je}")
                    self.root.after(0, lambda: self.clear_output())
                    self.root.after(0, lambda: self.display_error(
                        "Error decoding disconnect response",
                        f"JSON Error: {str(je)}\n\nResponse Content:\n{response.text[:500]}"
                    ))
                    self.root.after(0, lambda: self.set_status("Error: Invalid response format", "error"))
            else:
                print(f"[DEBUG] Disconnect HTTP request failed: {response.status_code}")
                self.root.after(0, lambda: self.clear_output())
                self.root.after(0, lambda: self.display_error(
                    f"Disconnect request failed with status code: {response.status_code}",
                    f"Response content: {response.text[:500]}"
                ))
                self.root.after(0, lambda: self.set_status("Error: Disconnect request failed", "error"))
                
        except requests.exceptions.ConnectionError as ce:
            print(f"[DEBUG] Connection error during disconnect: {ce}")
            self.root.after(0, lambda: self.clear_output())
            self.root.after(0, lambda: self.display_error(
                "Connection error during disconnect. You might need to flush DNS.",
                f"Error details: {str(ce)}"
            ))
            self.root.after(0, lambda: self.set_status("Error: Connection failed", "error"))
        except Exception as e:
            error_traceback = traceback.format_exc()
            print(f"[DEBUG] Unexpected error in _disconnect_thread: {e}")
            print(f"[DEBUG] Error traceback: {error_traceback}")
            
            self.root.after(0, lambda: self.clear_output())
            self.root.after(0, lambda: self.display_error(
                f"Error during disconnect: {e}",
                error_traceback
            ))
            self.root.after(0, lambda: self.set_status(f"Error: {str(e)[:50]}", "error"))
        finally:
            print("[DEBUG] _disconnect_thread completed, re-enabling button")
            self.root.after(0, lambda: self.disconnect_btn.set_enabled(True))
    
    def on_close(self):
        """Stop the background logger and close the application cleanly"""
        print("[DEBUG] on_close() called, stopping quality logger")
        try:
            self.quality_logger.stop()
        except Exception as e:
            print(f"[DEBUG] Error stopping quality logger: {e}")
        self.root.destroy()

def center_window(window):
    """Center the window on the screen"""
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry('{}x{}+{}+{}'.format(width, height, x, y))

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

def load_fonts():
    """Register the bundled Stena Sans fonts so Tkinter can use them by family name.

    On Windows the fonts are added privately (process-scoped) via GDI so no
    system-wide install is required. Non-Windows platforms fall back silently.
    """
    if platform.system() != 'Windows':
        return
    import ctypes
    FR_PRIVATE = 0x10
    for fname in ("StenaSans-Medium.ttf", "StenaSans-Bold.ttf"):
        path = resource_path(os.path.join("fonts", fname))
        try:
            if ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0) == 0:
                print(f"[DEBUG] Failed to register font: {path}")
        except Exception as e:
            print(f"[DEBUG] Error registering font {path}: {e}")

if __name__ == "__main__":
    print("[DEBUG] Starting application...")
    print(f"[DEBUG] Python version: {sys.version}")
    print(f"[DEBUG] Operating system: {platform.system()} {platform.release()}")
    print(f"[DEBUG] Current working directory: {os.getcwd()}")
    
    load_fonts()
    root = tk.Tk()
    print("[DEBUG] Tkinter root window created")
    
    try:
        icon_path = resource_path("icon.ico")
        print(f"[DEBUG] Attempting to load icon from: {icon_path}")
        root.iconbitmap(icon_path)
        print("[DEBUG] Icon loaded successfully")
    except Exception as e:
        print(f"[DEBUG] Could not load icon: {e}")
    
    print("[DEBUG] Creating StenaInternetMonitor instance...")
    app = StenaInternetMonitor(root)
    print("[DEBUG] Centering window...")
    center_window(root)
    print("[DEBUG] Starting main event loop...")
    root.mainloop()
    print("[DEBUG] Application terminated")