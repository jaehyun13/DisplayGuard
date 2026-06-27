#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DisplayGuard v2.0
멀티모니터 디스플레이 위치 보호 프로그램
"""

import ctypes
import ctypes.wintypes as wt
import sys
import os

# 한글 출력 인코딩 설정 (콘솔/파일 모두 UTF-8)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
import time
import threading
import json
import logging
import queue
from typing import List, Dict, Optional, Callable
import tkinter as tk
from tkinter import ttk

import i18n
from i18n import t

# ─────────────────────────────────────────────────
# 경로 (PyInstaller frozen 환경 대응)
# ─────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)   # .exe 위치
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOG_FILE    = os.path.join(BASE_DIR, "display_guard.log")
CONFIG_FILE = os.path.join(BASE_DIR, "display_guard_config.json")

# ─────────────────────────────────────────────────
# Windows API
# ─────────────────────────────────────────────────
user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

ENUM_CURRENT_SETTINGS         = 0xFFFFFFFF
CDS_UPDATEREGISTRY            = 0x00000001
CDS_NORESET                   = 0x10000000
CDS_SET_PRIMARY               = 0x00000010
DISP_CHANGE_SUCCESSFUL        = 0
DM_POSITION                   = 0x00000020
DM_BITSPERPEL                 = 0x00040000
DM_PELSWIDTH                  = 0x00080000
DM_PELSHEIGHT                 = 0x00100000
DM_DISPLAYFREQUENCY           = 0x00400000
DM_DISPLAYORIENTATION         = 0x00000080
DISPLAY_DEVICE_ACTIVE         = 0x00000001
DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004
WM_DISPLAYCHANGE              = 0x007E
WM_DESTROY                    = 0x0002
MB_ICONINFORMATION            = 0x40
MB_ICONWARNING                = 0x30

# ─────────────────────────────────────────────────
# 구조체
# ─────────────────────────────────────────────────

class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName",         ctypes.c_wchar * 32),
        ("dmSpecVersion",        ctypes.c_uint16),
        ("dmDriverVersion",      ctypes.c_uint16),
        ("dmSize",               ctypes.c_uint16),
        ("dmDriverExtra",        ctypes.c_uint16),
        ("dmFields",             ctypes.c_uint32),
        ("dmPositionX",          ctypes.c_int32),
        ("dmPositionY",          ctypes.c_int32),
        ("dmDisplayOrientation", ctypes.c_uint32),
        ("dmDisplayFixedOutput", ctypes.c_uint32),
        ("dmColor",              ctypes.c_int16),
        ("dmDuplex",             ctypes.c_int16),
        ("dmYResolution",        ctypes.c_int16),
        ("dmTTOption",           ctypes.c_int16),
        ("dmCollate",            ctypes.c_int16),
        ("dmFormName",           ctypes.c_wchar * 32),
        ("dmLogPixels",          ctypes.c_uint16),
        ("dmBitsPerPel",         ctypes.c_uint32),
        ("dmPelsWidth",          ctypes.c_uint32),
        ("dmPelsHeight",         ctypes.c_uint32),
        ("dmDisplayFlags",       ctypes.c_uint32),
        ("dmDisplayFrequency",   ctypes.c_uint32),
        ("dmICMMethod",          ctypes.c_uint32),
        ("dmICMIntent",          ctypes.c_uint32),
        ("dmMediaType",          ctypes.c_uint32),
        ("dmDitherType",         ctypes.c_uint32),
        ("dmReserved1",          ctypes.c_uint32),
        ("dmReserved2",          ctypes.c_uint32),
        ("dmPanningWidth",       ctypes.c_uint32),
        ("dmPanningHeight",      ctypes.c_uint32),
    ]
    def __init__(self):
        super().__init__()
        self.dmSize = ctypes.sizeof(self)


class DISPLAY_DEVICE(ctypes.Structure):
    _fields_ = [
        ("cb",           ctypes.c_uint32),
        ("DeviceName",   ctypes.c_wchar * 32),
        ("DeviceString", ctypes.c_wchar * 128),
        ("StateFlags",   ctypes.c_uint32),
        ("DeviceID",     ctypes.c_wchar * 128),
        ("DeviceKey",    ctypes.c_wchar * 128),
    ]
    def __init__(self):
        super().__init__()
        self.cb = ctypes.sizeof(self)


user32.EnumDisplayDevicesW.restype  = wt.BOOL
user32.EnumDisplayDevicesW.argtypes = [wt.LPCWSTR, ctypes.c_uint32,
                                        ctypes.POINTER(DISPLAY_DEVICE), ctypes.c_uint32]
user32.EnumDisplaySettingsExW.restype  = wt.BOOL
user32.EnumDisplaySettingsExW.argtypes = [wt.LPCWSTR, ctypes.c_uint32,
                                           ctypes.POINTER(DEVMODE), ctypes.c_uint32]
user32.ChangeDisplaySettingsExW.restype  = ctypes.c_long
user32.ChangeDisplaySettingsExW.argtypes = [wt.LPCWSTR, ctypes.POINTER(DEVMODE),
                                             wt.HWND, ctypes.c_uint32, ctypes.c_void_p]

# ─────────────────────────────────────────────────
# 디스플레이 함수
# ─────────────────────────────────────────────────

def get_display_configs() -> List[Dict]:
    configs, i = [], 0
    while True:
        dd = DISPLAY_DEVICE()
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        if not (dd.StateFlags & DISPLAY_DEVICE_ACTIVE):
            continue
        dm = DEVMODE()
        if not user32.EnumDisplaySettingsExW(dd.DeviceName, ENUM_CURRENT_SETTINGS,
                                              ctypes.byref(dm), 0):
            continue
        configs.append({
            "name":    dd.DeviceName,
            "primary": bool(dd.StateFlags & DISPLAY_DEVICE_PRIMARY_DEVICE),
            "x": dm.dmPositionX, "y": dm.dmPositionY,
            "w": dm.dmPelsWidth, "h": dm.dmPelsHeight,
            "bpp": dm.dmBitsPerPel, "freq": dm.dmDisplayFrequency,
            "rot": dm.dmDisplayOrientation,
        })
    return configs


def restore_display_configs(saved: List[Dict]) -> bool:
    ok = True
    for c in sorted(saved, key=lambda c: (not c["primary"])):
        dm = DEVMODE()
        dm.dmFields = (DM_POSITION | DM_PELSWIDTH | DM_PELSHEIGHT
                       | DM_BITSPERPEL | DM_DISPLAYFREQUENCY | DM_DISPLAYORIENTATION)
        dm.dmPositionX = c["x"]; dm.dmPositionY = c["y"]
        dm.dmPelsWidth = c["w"]; dm.dmPelsHeight = c["h"]
        dm.dmBitsPerPel = c["bpp"]; dm.dmDisplayFrequency = c["freq"]
        dm.dmDisplayOrientation = c["rot"]
        flags = CDS_UPDATEREGISTRY | CDS_NORESET
        if c["primary"]:
            flags |= CDS_SET_PRIMARY
        ret = user32.ChangeDisplaySettingsExW(c["name"], ctypes.byref(dm), None, flags, None)
        if ret != DISP_CHANGE_SUCCESSFUL:
            ok = False
    user32.ChangeDisplaySettingsExW(None, None, None, 0, None)
    return ok


def configs_equal(a: List[Dict], b: List[Dict]) -> bool:
    if len(a) != len(b):
        return False
    ma, mb = {c["name"]: c for c in a}, {c["name"]: c for c in b}
    if set(ma) != set(mb):
        return False
    return all(ma[n]["x"] == mb[n]["x"] and ma[n]["y"] == mb[n]["y"]
               and ma[n]["w"] == mb[n]["w"] and ma[n]["h"] == mb[n]["h"]
               for n in ma)

# ─────────────────────────────────────────────────
# 단일 인스턴스
# ─────────────────────────────────────────────────

_MUTEX_HANDLE = None

def ensure_single_instance() -> bool:
    global _MUTEX_HANDLE
    handle = kernel32.CreateMutexW(None, False, "Global\\DisplayGuard_v2")
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        user32.MessageBoxW(
            None,
            t("already_running_body"),
            t("already_running_title"),
            MB_ICONWARNING,
        )
        return False
    _MUTEX_HANDLE = handle
    return True

# ─────────────────────────────────────────────────
# 핵심 로직
# ─────────────────────────────────────────────────

class DisplayGuard:
    def __init__(self):
        self.saved: Optional[List[Dict]] = None
        self.enabled  = True
        self.restore_delay = 2.0
        self.language: Optional[str] = None   # user override; None = auto-detect
        self._timer: Optional[threading.Timer] = None
        self._lock  = threading.Lock()
        self.on_log: Optional[Callable[[str], None]] = None   # UI 콜백
        self.on_refresh: Optional[Callable[[], None]] = None  # UI 갱신 콜백
        self._load()

    # ── 파일 I/O ──────────────────────────────────

    def _load(self):
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            # utf-8-sig tolerates a BOM (e.g. if the user edits the config in Notepad).
            with open(CONFIG_FILE, encoding="utf-8-sig") as f:
                data = json.load(f)
            self.saved = data.get("configs")
            self.restore_delay = data.get("delay", 2.0)
            self.language = data.get("language")
        except Exception as e:
            self._log(t("log_config_load_failed", error=e))

    def _persist(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"configs": self.saved, "delay": self.restore_delay,
                           "language": self.language},
                          f, indent=2, ensure_ascii=False)
        except Exception as e:
            self._log(t("log_config_save_failed", error=e))

    # ── 언어 변경 ─────────────────────────────────

    def set_language(self, code: str):
        self.language = code
        i18n.set_language(code)
        self._persist()
        self._log(t("lang_changed", lang=i18n.language_name(code)))
        if self.on_refresh:
            self.on_refresh()

    # ── 내부 로그 ─────────────────────────────────

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        logging.getLogger("DisplayGuard").info(msg)
        if self.on_log:
            self.on_log(line)

    # ── 공개 메서드 ───────────────────────────────

    def snapshot(self):
        configs = get_display_configs()
        with self._lock:
            self.saved = configs
        self._persist()
        self._log(t("log_saved", count=len(configs)))
        if self.on_refresh:
            self.on_refresh()

    def restore_now(self):
        with self._lock:
            saved = self.saved
        if not saved:
            self._log(t("log_no_saved"))
            return
        self._log(t("log_restore_manual"))
        ok = restore_display_configs(saved)
        self._log(t("log_restore_done") if ok else t("log_restore_error"))

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        self._log(t("log_protection_on") if self.enabled else t("log_protection_off"))
        if self.on_refresh:
            self.on_refresh()
        return self.enabled

    def on_display_change(self):
        if not self.enabled:
            return
        with self._lock:
            if self._timer:
                self._timer.cancel()
            timer = threading.Timer(self.restore_delay, self._do_restore)
            timer.daemon = True
            self._timer = timer
        timer.start()
        self._log(t("log_change_detected", delay=self.restore_delay))

    def _do_restore(self):
        with self._lock:
            saved = self.saved
        if not saved:
            return
        current = get_display_configs()
        if configs_equal(saved, current):
            self._log(t("log_config_equal"))
            return
        ok = restore_display_configs(saved)
        self._log(t("log_auto_restore_done") if ok else t("log_auto_restore_error"))

# ─────────────────────────────────────────────────
# WM_DISPLAYCHANGE 수신 창
# ─────────────────────────────────────────────────

WNDPROC_TYPE = ctypes.WINFUNCTYPE(
    ctypes.c_long, wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize",        ctypes.c_uint),  ("style",         ctypes.c_uint),
        ("lpfnWndProc",   WNDPROC_TYPE),   ("cbClsExtra",    ctypes.c_int),
        ("cbWndExtra",    ctypes.c_int),   ("hInstance",     wt.HINSTANCE),
        ("hIcon",         wt.HICON),       ("hCursor",       wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),      ("lpszMenuName",  wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),     ("hIconSm",       wt.HICON),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wt.HWND), ("message", ctypes.c_uint),
        ("wParam", wt.WPARAM), ("lParam", wt.LPARAM),
        ("time", ctypes.c_uint32), ("pt_x", ctypes.c_long), ("pt_y", ctypes.c_long),
    ]


def run_message_loop(guard: DisplayGuard):
    def wnd_proc(hwnd, msg, wparam, lparam):
        if msg == WM_DISPLAYCHANGE:
            guard.on_display_change()
        elif msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    cb = WNDPROC_TYPE(wnd_proc)
    hinstance = kernel32.GetModuleHandleW(None)
    cls_name  = "DG_MsgWnd_v2"

    wc = WNDCLASSEXW()
    wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
    wc.lpfnWndProc = cb
    wc.hInstance = hinstance
    wc.lpszClassName = cls_name

    atom = user32.RegisterClassExW(ctypes.byref(wc))
    if not atom and kernel32.GetLastError() != 1410:
        return

    hwnd = user32.CreateWindowExW(0, cls_name, "DG", 0, 0, 0, 0, 0,
                                   None, None, hinstance, None)
    if not hwnd:
        return

    msg = MSG()
    while True:
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == 0 or ret == -1:
            break
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    user32.UnregisterClassW(cls_name, hinstance)

# ─────────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────────

CLR_BG     = "#1e1e2e"
CLR_PANEL  = "#2a2a3e"
CLR_BORDER = "#44475a"
CLR_GREEN  = "#50fa7b"
CLR_RED    = "#ff5555"
CLR_YELLOW = "#f1fa8c"
CLR_FG     = "#f8f8f2"
CLR_MUTED  = "#6272a4"
CLR_BTN    = "#44475a"
CLR_BTN_H  = "#6272a4"


class App(tk.Tk):
    def __init__(self, guard: DisplayGuard):
        super().__init__()
        self.guard = guard
        self._log_queue: queue.Queue = queue.Queue()
        self._tray_icon = None
        self._has_tray  = False

        self.title("DisplayGuard v2.0")
        self.geometry("520x600")
        self.resizable(False, False)
        self.configure(bg=CLR_BG)

        # 윈도우 아이콘 적용 (없으면 자동 생성)
        try:
            ico_path = ensure_ico()
            if ico_path:
                self.iconbitmap(ico_path)
        except Exception:
            pass

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        guard.on_log     = self._enqueue_log
        guard.on_refresh = lambda: self.after(0, self._refresh_status)

        self._process_log_queue()
        self.after(100, self._refresh_status)

    # ── UI 빌드 ───────────────────────────────────

    def _build_ui(self):
        pad = dict(padx=16, pady=8)

        # ── 헤더
        hdr = tk.Frame(self, bg=CLR_PANEL)
        hdr.pack(fill="x")
        tk.Label(hdr, text="DisplayGuard", font=("Segoe UI", 16, "bold"),
                 bg=CLR_PANEL, fg=CLR_FG).pack(side="left", padx=16, pady=12)
        tk.Label(hdr, text="v2.0", font=("Segoe UI", 9),
                 bg=CLR_PANEL, fg=CLR_MUTED).pack(side="left", pady=12)

        # ── 상태 배너
        self._status_frame = tk.Frame(self, bg=CLR_BG)
        self._status_frame.pack(fill="x", padx=16, pady=(12, 4))
        self._dot_lbl = tk.Label(self._status_frame, text="●", font=("Segoe UI", 14),
                                  bg=CLR_BG, fg=CLR_GREEN)
        self._dot_lbl.pack(side="left")
        self._status_lbl = tk.Label(self._status_frame,
                                     text=t("status_active"),
                                     font=("Segoe UI", 12, "bold"),
                                     bg=CLR_BG, fg=CLR_GREEN)
        self._status_lbl.pack(side="left", padx=6)

        # ── 버튼 영역
        btn_frame = tk.Frame(self, bg=CLR_BG)
        btn_frame.pack(fill="x", padx=16, pady=4)

        self._toggle_btn = self._btn(btn_frame, t("btn_disable"),
                                      self._on_toggle, CLR_RED)
        self._toggle_btn.pack(side="left", padx=(0, 8))

        self._save_btn = self._btn(btn_frame, t("btn_save"),
                                   self._on_snapshot, CLR_YELLOW)
        self._save_btn.pack(side="left", padx=(0, 8))

        self._restore_btn = self._btn(btn_frame, t("btn_restore_now"),
                                      self._on_restore_now, CLR_BTN)
        self._restore_btn.pack(side="left")

        # ── 모니터 목록
        self._monitors_lbl = tk.Label(self, text=t("section_monitors"),
                                       font=("Segoe UI", 10, "bold"),
                                       bg=CLR_BG, fg=CLR_MUTED)
        self._monitors_lbl.pack(anchor="w", padx=16, pady=(12, 4))

        mon_frame = tk.Frame(self, bg=CLR_PANEL, bd=0, highlightbackground=CLR_BORDER,
                              highlightthickness=1)
        mon_frame.pack(fill="x", padx=16)

        # Stable column ids (don't change with language); headings are translated.
        self._col_ids = ("monitor", "position", "resolution", "refresh")
        self._col_keys = ("col_monitor", "col_position", "col_resolution", "col_refresh")
        self._tree = ttk.Treeview(mon_frame, columns=self._col_ids, show="headings",
                                   height=5, style="DG.Treeview")
        for cid, key, w in zip(self._col_ids, self._col_keys, (140, 110, 120, 80)):
            self._tree.heading(cid, text=t(key))
            self._tree.column(cid, width=w, anchor="center")
        self._tree.pack(fill="x")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("DG.Treeview",
                         background=CLR_PANEL, foreground=CLR_FG,
                         fieldbackground=CLR_PANEL, rowheight=26,
                         font=("Segoe UI", 9))
        style.configure("DG.Treeview.Heading",
                         background=CLR_BTN, foreground=CLR_FG,
                         font=("Segoe UI", 9, "bold"))
        style.map("DG.Treeview", background=[("selected", CLR_BTN_H)])

        # ── 로그
        self._log_lbl = tk.Label(self, text=t("section_log"),
                                 font=("Segoe UI", 10, "bold"),
                                 bg=CLR_BG, fg=CLR_MUTED)
        self._log_lbl.pack(anchor="w", padx=16, pady=(12, 4))

        log_frame = tk.Frame(self, bg=CLR_PANEL, highlightbackground=CLR_BORDER,
                              highlightthickness=1)
        log_frame.pack(fill="both", expand=True, padx=16, pady=(0, 4))

        self._log_text = tk.Text(
            log_frame, bg=CLR_PANEL, fg=CLR_FG,
            font=("Consolas", 9), relief="flat",
            wrap="word", state="disabled", cursor="arrow",
            height=8,
        )
        sb = tk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # ── 하단 힌트
        self._footer_lbl = tk.Label(self,
                 text=t("footer_hint"),
                 font=("Segoe UI", 8), bg=CLR_BG, fg=CLR_MUTED)
        self._footer_lbl.pack(pady=(0, 10))

    def _btn(self, parent, text, cmd, fg=CLR_FG):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=CLR_BTN, fg=fg, activebackground=CLR_BTN_H,
                      activeforeground=CLR_FG, relief="flat",
                      font=("Segoe UI", 9), padx=12, pady=6, cursor="hand2",
                      bd=0)
        return b

    # ── 이벤트 핸들러 ────────────────────────────

    def _on_close(self):
        if self._has_tray:
            self.withdraw()
        else:
            self._quit()

    def _quit(self):
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        self.destroy()

    def show(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _on_toggle(self):
        active = self.guard.toggle()
        self._refresh_status()
        # 트레이 아이콘 색상 갱신
        if self._tray_icon:
            try:
                self._tray_icon.icon = _make_icon(active)
            except Exception:
                pass

    def _on_snapshot(self):
        self.guard.snapshot()
        self._refresh_status()

    def _on_restore_now(self):
        threading.Thread(target=self.guard.restore_now, daemon=True).start()

    # ── UI 갱신 ───────────────────────────────────

    def _refresh_status(self):
        active = self.guard.enabled
        color  = CLR_GREEN if active else CLR_RED
        self._dot_lbl.configure(fg=color)
        self._status_lbl.configure(
            text=t("status_active") if active else t("status_inactive"),
            fg=color,
        )
        self._toggle_btn.configure(
            text=t("btn_disable") if active else t("btn_enable"),
            fg=CLR_RED if active else CLR_GREEN,
        )
        self._refresh_monitor_list()
        # 트레이 툴팁 갱신
        if self._tray_icon:
            try:
                status = t("status_short_active") if active else t("status_short_inactive")
                self._tray_icon.title = f"DisplayGuard [{status}]"
            except Exception:
                pass

    def set_language(self, code: str):
        """Switch UI language live (called from the tray language menu)."""
        self.guard.set_language(code)
        self._retranslate()
        self._refresh_status()
        if self._tray_icon:
            try:
                self._tray_icon.update_menu()
            except Exception:
                pass

    def _retranslate(self):
        """Re-apply all static UI text in the current language."""
        self._save_btn.configure(text=t("btn_save"))
        self._restore_btn.configure(text=t("btn_restore_now"))
        self._monitors_lbl.configure(text=t("section_monitors"))
        self._log_lbl.configure(text=t("section_log"))
        self._footer_lbl.configure(text=t("footer_hint"))
        for cid, key in zip(self._col_ids, self._col_keys):
            self._tree.heading(cid, text=t(key))
        # status banner + toggle button are handled by _refresh_status()

    def _refresh_monitor_list(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        if not self.guard.saved:
            return
        for c in self.guard.saved:
            name = c["name"].replace("\\\\.\\", "")
            if c["primary"]:
                name += " ★"
            pos  = f"({c['x']}, {c['y']})"
            res  = f"{c['w']} × {c['h']}"
            freq = f"{c['freq']} Hz"
            self._tree.insert("", "end", values=(name, pos, res, freq))

    # ── 스레드 안전 로그 ─────────────────────────

    def _enqueue_log(self, line: str):
        self._log_queue.put(line)

    def _process_log_queue(self):
        try:
            while True:
                line = self._log_queue.get_nowait()
                self._log_text.configure(state="normal")
                self._log_text.insert("end", line + "\n")
                self._log_text.see("end")
                self._log_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(150, self._process_log_queue)

# ─────────────────────────────────────────────────
# 아이콘 생성 (외부 파일 없이 코드로 생성)
# ─────────────────────────────────────────────────

def _draw_shield_frame(draw, size: int, fill, stroke):
    """방패 모양 그리기"""
    p   = max(1, size // 10)
    r   = max(2, size // 5)
    mid = int(size * 0.60)
    draw.rounded_rectangle([p, p, size - p, mid + r], radius=r, fill=fill)
    draw.polygon([(p, mid), (size - p, mid), (size // 2, size - p)], fill=fill)
    draw.rounded_rectangle([p, p, size - p, mid + r], radius=r,
                            fill=None, outline=stroke, width=max(2, size // 28))
    draw.polygon([(p, mid), (size - p, mid), (size // 2, size - p)],
                 fill=None, outline=stroke)


def _make_ico_frame(size: int) -> "Image":
    from PIL import Image, ImageDraw, ImageFont
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad  = max(1, size // 14)
    # 배경 원
    draw.ellipse([pad, pad, size - pad - 1, size - pad - 1],
                 fill=(22, 22, 36, 255))
    # 방패
    sp = size // 9
    sh_size = size - sp * 2
    sh_img  = Image.new("RGBA", (sh_size, sh_size), (0, 0, 0, 0))
    _draw_shield_frame(ImageDraw.Draw(sh_img), sh_size,
                       fill=(40, 40, 60, 255), stroke=(80, 250, 123, 255))
    img.paste(sh_img, (sp, sp), sh_img)
    # "D" 글자
    font_size = size * 40 // 100
    font = None
    for path in ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/verdanab.ttf"]:
        try:
            font = ImageFont.truetype(path, font_size)
            break
        except Exception:
            pass
    cx, cy = size // 2, int(size * 0.42)
    try:
        draw.text((cx, cy), "D", fill=(80, 250, 123, 255), anchor="mm", font=font)
    except TypeError:
        draw.text((cx - font_size // 3, cy - font_size // 2),
                  "D", fill=(80, 250, 123, 255))
    return img


def ensure_ico() -> str:
    """icon.ico 가 없으면 생성하고 경로를 반환합니다."""
    from PIL import Image
    ico_path = os.path.join(BASE_DIR, "icon.ico")
    if not os.path.exists(ico_path):
        try:
            sizes  = [256, 128, 64, 48, 32, 16]
            frames = [_make_ico_frame(s) for s in sizes]
            frames[0].save(ico_path, format="ICO",
                           sizes=[(s, s) for s in sizes],
                           append_images=frames[1:])
        except Exception:
            return ""
    return ico_path


# ─────────────────────────────────────────────────
# 트레이 아이콘
# ─────────────────────────────────────────────────

def _make_icon(active: bool):
    from PIL import Image, ImageDraw
    sz   = 64
    img  = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad  = max(1, sz // 14)
    draw.ellipse([pad, pad, sz - pad - 1, sz - pad - 1], fill=(22, 22, 36, 255))
    sp     = sz // 9
    sh_sz  = sz - sp * 2
    sh_img = Image.new("RGBA", (sh_sz, sh_sz), (0, 0, 0, 0))
    fill   = (80, 250, 123) if active else (255, 85, 85)
    _draw_shield_frame(ImageDraw.Draw(sh_img), sh_sz,
                       fill=(40, 40, 60, 255), stroke=fill)
    img.paste(sh_img, (sp, sp), sh_img)
    try:
        draw.text((sz // 2, int(sz * 0.42)), "D", fill=fill, anchor="mm")
    except Exception:
        pass
    return img


def setup_tray(app: App, guard: DisplayGuard):
    try:
        import pystray
        from PIL import Image
    except ImportError:
        app._enqueue_log(t("tray_missing_deps"))
        return

    def on_show(icon, item):
        app.after(0, app.show)

    def on_toggle(icon, item):
        app.after(0, app._on_toggle)

    def on_snapshot(icon, item):
        app.after(0, app._on_snapshot)

    def on_exit(icon, item):
        icon.stop()
        app.after(0, app._quit)

    def make_lang_setter(code):
        def _set(icon, item):
            app.after(0, lambda: app.set_language(code))
        return _set

    # Language submenu: one radio item per available language.
    lang_items = [
        pystray.MenuItem(
            name,
            make_lang_setter(code),
            checked=(lambda item, c=code: i18n.get_language() == c),
            radio=True,
        )
        for code, name in i18n.LANGUAGES.items()
    ]
    language_menu = pystray.MenuItem(lambda item: t("tray_language"),
                                     pystray.Menu(*lang_items))

    menu = pystray.Menu(
        pystray.MenuItem(lambda item: t("tray_open"), on_show, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(lambda item: t("tray_save"), on_snapshot),
        pystray.MenuItem(
            lambda item: t("btn_disable") if guard.enabled else t("btn_enable"),
            on_toggle,
        ),
        language_menu,
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(lambda item: t("tray_exit"), on_exit),
    )

    icon = pystray.Icon(
        "DisplayGuard",
        _make_icon(guard.enabled),
        f"DisplayGuard [{t('status_short_active')}]",
        menu,
    )
    icon.run_detached()
    app._tray_icon = icon
    app._has_tray  = True
    app._enqueue_log(t("tray_started"))

# ─────────────────────────────────────────────────
# 파일 로깅
# ─────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
)

# ─────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────

def _init_language():
    """Set the active UI language from the saved override, or auto-detect.

    Done before anything is shown (including the 'already running' dialog) so the
    very first UI a user sees is already localized.
    """
    lang = None
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, encoding="utf-8-sig") as f:
                lang = json.load(f).get("language")
    except Exception:
        lang = None
    i18n.set_language(lang or i18n.detect_system_language())


def main():
    _init_language()

    if not ensure_single_instance():
        return

    guard = DisplayGuard()
    if not guard.saved:
        guard._log(t("log_no_saved_autosave"))
        configs = get_display_configs()
        guard.saved = configs
        guard._persist()

    # WM_DISPLAYCHANGE 수신 스레드
    threading.Thread(target=run_message_loop, args=(guard,),
                     daemon=True, name="MsgLoop").start()

    # GUI (메인 스레드)
    app = App(guard)

    # 트레이 (별도 스레드로 실행)
    setup_tray(app, guard)

    app._enqueue_log(t("app_started", count=len(guard.saved)))
    for c in guard.saved:
        tag = " ★" if c["primary"] else ""
        app._enqueue_log(f"  {c['name'].replace(chr(92)+chr(92)+'.'+chr(92), '')}{tag}: "
                         f"({c['x']},{c['y']}) {c['w']}×{c['h']} @{c['freq']}Hz")

    app.mainloop()


if __name__ == "__main__":
    main()
