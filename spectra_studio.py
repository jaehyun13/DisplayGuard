#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spectra Display Studio — multi-monitor layout, mode, colour and window-zone manager
with automatic layout protection (formerly DisplayGuard).

Entry point: starts the app core, the local UI server, the tray icon and the window.

    spectra_studio.py [--minimized] [--demo] [--no-window] [--port N]
"""
from __future__ import annotations

import json
import logging
import logging.handlers
import os
import subprocess
import sys
import threading
import time
import webbrowser
from typing import Dict, Optional

# UTF-8 console output (the log and messages contain non-ASCII text).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

import i18n
from i18n import t
from core import APP_ID, APP_NAME, APP_VERSION, Studio
from server import AppServer

# ─────────────────────────────────────────────────
# Paths (PyInstaller-aware)
# ─────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Bundled resources (PyInstaller 6+ onedir puts datas under _internal).
RES_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
UI_DIR = os.path.join(RES_DIR, "ui")


def _is_writable_dir(path: str) -> bool:
    probe = os.path.join(path, f".spectra_write_test_{os.getpid()}")
    try:
        with open(probe, "w"):
            pass
        os.remove(probe)
        return True
    except OSError:
        return False


def resolve_data_dir() -> str:
    """Settings/log location.

    The program folder is preferred (keeps existing installs working); if it is
    read-only (e.g. installed for all users) fall back to %LOCALAPPDATA%.
    """
    if _is_writable_dir(BASE_DIR):
        return BASE_DIR
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    fallback = os.path.join(root, APP_ID)
    try:
        os.makedirs(fallback, exist_ok=True)
        return fallback
    except OSError:
        return BASE_DIR


def setup_logging(data_dir: str) -> None:
    try:
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            os.path.join(data_dir, "spectra_studio.log"),
            maxBytes=512 * 1024, backupCount=1, encoding="utf-8")
    except OSError:
        handler = logging.NullHandler()
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format="%(asctime)s %(levelname)s: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")


def init_language(data_dir: str) -> None:
    """Pick the UI language before anything is shown (saved choice, else Windows')."""
    lang = None
    for name in ("spectra_config.json", "display_guard_config.json"):
        path = os.path.join(data_dir, name)
        try:
            if os.path.exists(path):
                with open(path, encoding="utf-8-sig") as f:
                    lang = json.load(f).get("language")
                break
        except Exception:
            lang = None
    if lang not in i18n.LANGUAGES:
        lang = None
    i18n.set_language(lang or i18n.detect_system_language())


# ─────────────────────────────────────────────────
# Icon (drawn in code — no image assets needed)
# ─────────────────────────────────────────────────

def make_icon(size: int = 64, active: bool = True):
    from PIL import Image, ImageDraw
    scale = 4                                   # supersample for smooth edges
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=s // 5, fill=(11, 19, 38, 255))
    accent = (173, 198, 255, 255) if active else (255, 180, 171, 255)
    glow = (77, 142, 255, 255) if active else (147, 0, 10, 255)
    stroke = max(scale, s // 14)
    # screen
    d.rounded_rectangle([s * 0.16, s * 0.22, s * 0.84, s * 0.66], radius=s // 16,
                        fill=glow, outline=accent, width=stroke)
    # stand + base
    d.rectangle([s * 0.46, s * 0.66, s * 0.54, s * 0.76], fill=accent)
    d.rounded_rectangle([s * 0.30, s * 0.75, s * 0.70, s * 0.82], radius=s // 40, fill=accent)
    return img.resize((size, size), Image.LANCZOS)


def write_ico(path: str) -> None:
    sizes = [256, 128, 64, 48, 32, 16]
    frames = [make_icon(sz) for sz in sizes]
    frames[0].save(path, format="ICO", sizes=[(sz, sz) for sz in sizes],
                   append_images=frames[1:])


# ─────────────────────────────────────────────────
# The window: the UI runs in a chromeless Edge/Chrome "app" window
# ─────────────────────────────────────────────────

def find_app_browser() -> Optional[str]:
    if sys.platform != "win32":
        return None
    candidates = []
    try:
        import winreg
        for exe in ("msedge.exe", "chrome.exe"):
            for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(root, r"SOFTWARE\Microsoft\Windows\CurrentVersion"
                                              r"\App Paths" + "\\" + exe) as key:
                        candidates.append(winreg.QueryValueEx(key, None)[0])
                except OSError:
                    pass
    except ImportError:
        pass
    for var in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(var)
        if base:
            candidates.append(os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"))
            candidates.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


class Window:
    def __init__(self, backend, url: str, data_dir: str):
        self.backend = backend
        self.url = url
        self.profile_dir = os.path.join(data_dir, "webview")
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def open(self) -> None:
        with self._lock:
            # If our browser process is alive and its window can be found, just raise it.
            # (The process can outlive a closed window, so fall through otherwise.)
            if self._proc and self._proc.poll() is None \
                    and self.backend.focus_window_by_title(APP_NAME):
                return
            exe = find_app_browser()
            if exe:
                try:
                    self._proc = subprocess.Popen([
                        exe, f"--app={self.url}", f"--user-data-dir={self.profile_dir}",
                        "--window-size=1440,920", "--no-first-run",
                        "--no-default-browser-check", "--disable-background-mode",
                        "--disable-features=Translate"])
                    return
                except OSError:
                    logging.getLogger("Spectra").exception("could not start %s", exe)
            webbrowser.open(self.url)

    def close(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                except OSError:
                    pass


# ─────────────────────────────────────────────────
# Start with Windows
# ─────────────────────────────────────────────────

def autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    return f'"{exe}" "{os.path.abspath(__file__)}" --minimized'


# ─────────────────────────────────────────────────
# Tray
# ─────────────────────────────────────────────────

def run_tray(studio: Studio, window: Window, on_exit) -> bool:
    """Blocks until Exit is chosen. Returns False if the tray is unavailable."""
    try:
        import pystray
    except Exception:
        studio.log(t("tray_missing_deps"))
        return False

    def tooltip() -> str:
        status = t("status_short_active") if studio.enabled else t("status_short_inactive")
        return f"{APP_NAME} [{status}]"

    def do_exit(icon, _item):
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: t("tray_open"), lambda icon, item: window.open(),
                         default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(lambda item: t("tray_save"),
                         lambda icon, item: _safe(studio.snapshot)),
        pystray.MenuItem(lambda item: t("btn_disable") if studio.enabled else t("btn_enable"),
                         lambda icon, item: studio.set_enabled(not studio.enabled)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(lambda item: t("tray_exit"), do_exit),
    )
    icon = pystray.Icon(APP_ID, make_icon(64, studio.enabled), tooltip(), menu)

    def refresh():
        try:
            icon.icon = make_icon(64, studio.enabled)
            icon.title = tooltip()
            icon.update_menu()
        except Exception:
            pass

    studio.on_change = refresh
    studio.log(t("tray_started"))
    icon.run()
    on_exit()
    return True


def _safe(fn) -> None:
    try:
        fn()
    except Exception as e:
        logging.getLogger("Spectra").warning("%s", e)


# ─────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────

def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    demo = "--demo" in args or sys.platform != "win32"
    port = 0
    if "--port" in args:
        try:
            port = int(args[args.index("--port") + 1])
        except (IndexError, ValueError):
            port = 0

    if demo:
        import displays_mock as backend
    else:
        import displays_win as backend
    backend.init_process()

    data_dir = resolve_data_dir()
    setup_logging(data_dir)
    init_language(data_dir)

    if not demo and not backend.acquire_single_instance("Global\\" + APP_ID):
        backend.message_box(t("already_running_title"), t("already_running_body"))
        return 0

    studio = Studio(backend, data_dir)
    studio.start()

    def settings_get() -> Dict:
        return {"autostart": backend.is_autostart_enabled(APP_ID)}

    def settings_set(patch: Dict) -> None:
        if "autostart" in patch:
            on = bool(patch["autostart"])
            backend.set_autostart(APP_ID, autostart_command() if on else None)
            studio.log(t("log_autostart_on") if on else t("log_autostart_off"))

    server = AppServer(studio, UI_DIR, port=port,
                       token=os.environ.get("SPECTRA_TOKEN") or None,
                       settings_get=settings_get, settings_set=settings_set)
    server.start()
    window = Window(backend, server.url, data_dir)

    if "--no-window" in args:
        print(server.url, flush=True)
    elif "--minimized" not in args:
        window.open()

    def shutdown():
        window.close()
        server.stop()

    if "--no-window" in args or not run_tray(studio, window, shutdown):
        # No tray available: keep serving until interrupted.
        if "--no-window" not in args and "--minimized" in args:
            window.open()   # without a tray there would be no way to reach the UI
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
