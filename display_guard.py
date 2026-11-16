#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DisplayGuard
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
import logging.handlers
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

# 번들 리소스 위치 (PyInstaller 6+ onedir 은 datas 를 _internal 아래에 둔다)
RES_DIR = getattr(sys, "_MEIPASS", BASE_DIR)

APP_VERSION = "1.1.1"   # build.ps1 이 릴리스 버전으로 덮어쓴다


def _is_writable_dir(path: str) -> bool:
    probe = os.path.join(path, f".dg_write_test_{os.getpid()}")
    try:
        with open(probe, "w"):
            pass
        os.remove(probe)
        return True
    except OSError:
        return False


def _resolve_data_dir() -> str:
    """설정/로그 저장 위치.

    기존 설치와의 호환을 위해 실행 파일 폴더를 우선 사용하고, 쓰기 권한이 없으면
    (예: Program Files 에 전체 사용자용으로 설치) %LOCALAPPDATA%/DisplayGuard 로 대체한다.
    """
    if _is_writable_dir(BASE_DIR):
        return BASE_DIR
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    fallback = os.path.join(root, "DisplayGuard")
    try:
        os.makedirs(fallback, exist_ok=True)
        return fallback
    except OSError:
        return BASE_DIR


DATA_DIR    = _resolve_data_dir()
LOG_FILE    = os.path.join(DATA_DIR, "display_guard.log")
CONFIG_FILE = os.path.join(DATA_DIR, "display_guard_config.json")

# ─────────────────────────────────────────────────
# Windows API
# ─────────────────────────────────────────────────
# use_last_error=True: ctypes 가 호출 직후의 GetLastError 값을 보존한다.
# (kernel32.GetLastError() 를 따로 호출하면 그 사이에 값이 덮어써질 수 있다.)
user32   = ctypes.WinDLL("user32",   use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

ERROR_ALREADY_EXISTS          = 183
ERROR_CLASS_ALREADY_EXISTS    = 1410

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

# 64비트에서 핸들/포인터가 32비트로 잘리지 않도록 시그니처를 명시한다.
kernel32.CreateMutexW.restype      = wt.HANDLE
kernel32.CreateMutexW.argtypes     = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
kernel32.CloseHandle.restype       = wt.BOOL
kernel32.CloseHandle.argtypes      = [wt.HANDLE]
kernel32.GetModuleHandleW.restype  = wt.HMODULE
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
user32.MessageBoxW.restype         = ctypes.c_int
user32.MessageBoxW.argtypes        = [wt.HWND, wt.LPCWSTR, wt.LPCWSTR, ctypes.c_uint]

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
                       | DM_BITSPERPEL | DM_DISPLAYORIENTATION)
        if c["freq"] > 1:   # 0/1 = "하드웨어 기본값" → 주사율은 건드리지 않는다
            dm.dmFields |= DM_DISPLAYFREQUENCY
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
    def same(p: Dict, q: Dict) -> bool:
        if any(p[k] != q[k] for k in ("x", "y", "w", "h", "rot", "primary")):
            return False
        # 0/1 은 "하드웨어 기본 주사율" 이므로 비교 대상에서 제외
        if p["freq"] > 1 and q["freq"] > 1 and p["freq"] != q["freq"]:
            return False
        return True
    return all(same(ma[n], mb[n]) for n in ma)


_CONFIG_INT_KEYS = ("x", "y", "w", "h", "bpp", "freq", "rot")


def _valid_configs(configs) -> bool:
    """설정 파일에서 읽은 레이아웃이 복원에 쓸 수 있는 형태인지 검사."""
    if not isinstance(configs, list) or not configs:
        return False
    for c in configs:
        if not isinstance(c, dict):
            return False
        if not isinstance(c.get("name"), str) or not c["name"]:
            return False
        if not isinstance(c.get("primary"), bool):
            return False
        for k in _CONFIG_INT_KEYS:
            v = c.get(k)
            if not isinstance(v, int) or isinstance(v, bool):
                return False
    return True

# ─────────────────────────────────────────────────
# 단일 인스턴스
# ─────────────────────────────────────────────────

_MUTEX_HANDLE = None

def ensure_single_instance() -> bool:
    global _MUTEX_HANDLE
    handle = kernel32.CreateMutexW(None, False, "Global\\DisplayGuard_v2")
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        if handle:
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

DEFAULT_RESTORE_DELAY   = 2.0
MAX_RESTORE_DELAY       = 60.0
# 복원이 계속 실패하거나 적용 결과가 저장값과 달라질 때 "복원 → 변경 감지 → 복원"
# 이 끝없이 반복되지 않도록, 짧은 시간 안의 연속 자동 복원 횟수를 제한한다.
MAX_AUTO_RESTORE_TRIES  = 3
AUTO_RESTORE_WINDOW_SEC = 30.0


class DisplayGuard:
    def __init__(self):
        self._tries = 0
        self._last_try = 0.0
        self._gave_up = False
        self.saved: Optional[List[Dict]] = None
        self.enabled  = True
        self.restore_delay = DEFAULT_RESTORE_DELAY
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
            if not isinstance(data, dict):
                raise ValueError("config root is not an object")
            configs = data.get("configs")
            self.saved = configs if _valid_configs(configs) else None
            delay = data.get("delay", DEFAULT_RESTORE_DELAY)
            if (isinstance(delay, (int, float)) and not isinstance(delay, bool)
                    and 0 <= delay <= MAX_RESTORE_DELAY):
                self.restore_delay = float(delay)
            lang = data.get("language")
            self.language = lang if lang in i18n.LANGUAGES else None
        except Exception as e:
            self._log(t("log_config_load_failed", error=e))

    def _persist(self):
        # 임시 파일에 쓴 뒤 교체 → 저장 도중 종료돼도 기존 설정이 깨지지 않는다.
        tmp = CONFIG_FILE + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"configs": self.saved, "delay": self.restore_delay,
                           "language": self.language},
                          f, indent=2, ensure_ascii=False)
            os.replace(tmp, CONFIG_FILE)
        except Exception as e:
            try:
                os.remove(tmp)
            except OSError:
                pass
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
        if not configs:
            self._log(t("log_no_saved"))
            return
        with self._lock:
            self.saved = configs
            self._reset_tries()
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
        with self._lock:
            self._reset_tries()
        ok = restore_display_configs(saved)
        self._log(t("log_restore_done") if ok else t("log_restore_error"))
        if self.on_refresh:
            self.on_refresh()

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if not self.enabled:
            # 대기 중이던 자동 복원도 함께 취소
            with self._lock:
                if self._timer:
                    self._timer.cancel()
                    self._timer = None
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

    def _reset_tries(self):
        self._tries = 0
        self._gave_up = False

    def _do_restore(self):
        try:
            self._do_restore_inner()
        except Exception as e:   # 타이머 스레드가 조용히 죽지 않도록
            logging.getLogger("DisplayGuard").exception("auto-restore failed: %s", e)

    def _do_restore_inner(self):
        with self._lock:
            saved = self.saved
        if not saved or not self.enabled:
            return
        current = get_display_configs()
        if configs_equal(saved, current):
            with self._lock:
                self._reset_tries()
            self._log(t("log_config_equal"))
            if self.on_refresh:
                self.on_refresh()
            return
        now = time.monotonic()
        with self._lock:
            if now - self._last_try > AUTO_RESTORE_WINDOW_SEC:
                self._reset_tries()
            if self._tries >= MAX_AUTO_RESTORE_TRIES:
                announce = not self._gave_up
                self._gave_up = True
                proceed = False
            else:
                self._tries += 1
                self._last_try = now
                proceed = True
        if not proceed:
            if announce:
                self._log(t("log_restore_giveup", count=MAX_AUTO_RESTORE_TRIES))
            return
        ok = restore_display_configs(saved)
        self._log(t("log_auto_restore_done") if ok else t("log_auto_restore_error"))
        if self.on_refresh:
            self.on_refresh()

# ─────────────────────────────────────────────────
# WM_DISPLAYCHANGE 수신 창
# ─────────────────────────────────────────────────

LRESULT = ctypes.c_ssize_t   # 포인터 크기 (64비트에서 c_long 은 32비트라 잘린다)

WNDPROC_TYPE = ctypes.WINFUNCTYPE(
    LRESULT, wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM)


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


user32.DefWindowProcW.restype     = LRESULT
user32.DefWindowProcW.argtypes    = [wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM]
user32.RegisterClassExW.restype   = wt.ATOM
user32.RegisterClassExW.argtypes  = [ctypes.POINTER(WNDCLASSEXW)]
user32.UnregisterClassW.restype   = wt.BOOL
user32.UnregisterClassW.argtypes  = [wt.LPCWSTR, wt.HINSTANCE]
user32.CreateWindowExW.restype    = wt.HWND
user32.CreateWindowExW.argtypes   = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                     ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                     wt.HWND, wt.HMENU, wt.HINSTANCE, ctypes.c_void_p]
user32.GetMessageW.restype        = ctypes.c_int   # -1 = 오류
user32.GetMessageW.argtypes       = [ctypes.POINTER(MSG), wt.HWND, ctypes.c_uint, ctypes.c_uint]
user32.TranslateMessage.restype   = wt.BOOL
user32.TranslateMessage.argtypes  = [ctypes.POINTER(MSG)]
user32.DispatchMessageW.restype   = LRESULT
user32.DispatchMessageW.argtypes  = [ctypes.POINTER(MSG)]
user32.PostQuitMessage.restype    = None
user32.PostQuitMessage.argtypes   = [ctypes.c_int]


def run_message_loop(guard: DisplayGuard):
    def wnd_proc(hwnd, msg, wparam, lparam):
        if msg == WM_DISPLAYCHANGE:
            try:
                guard.on_display_change()
            except Exception as e:
                logging.getLogger("DisplayGuard").exception("display-change handler: %s", e)
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
    if not atom and ctypes.get_last_error() != ERROR_CLASS_ALREADY_EXISTS:
        logging.getLogger("DisplayGuard").error(
            "RegisterClassExW failed (error %d)", ctypes.get_last_error())
        return

    hwnd = user32.CreateWindowExW(0, cls_name, "DG", 0, 0, 0, 0, 0,
                                   None, None, hinstance, None)
    if not hwnd:
        logging.getLogger("DisplayGuard").error(
            "CreateWindowExW failed (error %d)", ctypes.get_last_error())
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
# Windows 시작 시 자동 실행 (HKCU Run — 설치 프로그램과 같은 값 이름 사용)
# ─────────────────────────────────────────────────

RUN_KEY   = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "DisplayGuard"


def _autostart_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --minimized'
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    return f'"{exe}" "{os.path.abspath(__file__)}" --minimized'


def is_autostart_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
        return True
    except (ImportError, OSError):
        return False


def set_autostart(enable: bool) -> None:
    """Raises OSError on failure."""
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
        if enable:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, _autostart_command())
        else:
            try:
                winreg.DeleteValue(key, RUN_VALUE)
            except FileNotFoundError:
                pass

# ─────────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────────

CLR_BG       = "#0f1117"
CLR_CARD     = "#181b24"
CLR_CARD_HI  = "#232836"
CLR_BORDER   = "#2a2f3d"
CLR_FG       = "#e8eaf0"
CLR_MUTED    = "#8a90a2"
CLR_GREEN    = "#4ade80"
CLR_RED      = "#f87171"
CLR_AMBER    = "#fbbf24"
CLR_ACCENT   = "#5b8cff"
CLR_ACCENT_H = "#7aa2ff"
CLR_OFF      = "#3a4050"
FONT         = "Segoe UI"
FONT_MONO    = "Consolas"


def _round_rect(canvas, x1, y1, x2, y2, r, **kw):
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


def _short_name(device_name: str) -> str:
    r"""'\\.\DISPLAY2' → 'DISPLAY2'"""
    return device_name.replace("\\\\.\\", "")


def _display_number(device_name: str, fallback: int) -> str:
    digits = "".join(ch for ch in device_name if ch.isdigit())
    return digits or str(fallback)


class App(tk.Tk):
    def __init__(self, guard: DisplayGuard):
        super().__init__()
        self.guard = guard
        self._log_queue: queue.Queue = queue.Queue()
        self._tray_icon = None
        self._has_tray  = False
        self._log_open  = False

        # 고해상도(배율) 화면에서 글꼴만 커지고 픽셀 크기는 그대로인 문제 보정
        try:
            self._scale = max(1.0, self.winfo_fpixels("1i") / 96.0)
        except Exception:
            self._scale = 1.0

        self.title(f"DisplayGuard v{APP_VERSION}")
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
        self._refresh_status()

    def _px(self, v: float) -> int:
        return int(round(v * self._scale))

    # ── UI 빌드 ───────────────────────────────────

    def _build_ui(self):
        px = self._px
        self._content_w = px(400)

        root = tk.Frame(self, bg=CLR_BG)
        root.pack(padx=px(20), pady=(px(16), px(14)))

        # ── 헤더: 이름 · 버전 · 언어 선택
        hdr = tk.Frame(root, bg=CLR_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text="DisplayGuard", font=(FONT, 15, "bold"),
                 bg=CLR_BG, fg=CLR_FG).pack(side="left")
        tk.Label(hdr, text=f"v{APP_VERSION}", font=(FONT, 9),
                 bg=CLR_BG, fg=CLR_MUTED).pack(side="left", padx=(px(8), 0), pady=(px(6), 0))

        self._lang_btn = tk.Menubutton(
            hdr, font=(FONT, 9), bg=CLR_CARD, fg=CLR_FG,
            activebackground=CLR_CARD_HI, activeforeground=CLR_FG,
            relief="flat", bd=0, padx=px(10), pady=px(4), cursor="hand2",
            highlightthickness=1, highlightbackground=CLR_BORDER)
        lang_menu = tk.Menu(self._lang_btn, tearoff=0, bg=CLR_CARD, fg=CLR_FG,
                            activebackground=CLR_ACCENT, activeforeground="#ffffff",
                            bd=0, font=(FONT, 9))
        for code, name in i18n.LANGUAGES.items():
            lang_menu.add_command(label=name,
                                  command=lambda c=code: self.set_language(c))
        self._lang_btn["menu"] = lang_menu
        self._lang_btn.pack(side="right")

        # ── 상태 카드: 상태 문구 + 켜기/끄기 스위치
        card = self._card(root, pady=(px(14), 0))
        inner = tk.Frame(card, bg=CLR_CARD)
        inner.pack(fill="x", padx=px(16), pady=px(14))

        self._switch = tk.Canvas(inner, width=px(52), height=px(28), bg=CLR_CARD,
                                 highlightthickness=0, cursor="hand2")
        self._switch.pack(side="right", padx=(px(12), 0))
        self._switch.bind("<Button-1>", lambda e: self._on_toggle())

        txt = tk.Frame(inner, bg=CLR_CARD)
        txt.pack(side="left", fill="x", expand=True)
        row = tk.Frame(txt, bg=CLR_CARD)
        row.pack(anchor="w")
        self._dot_lbl = tk.Label(row, text="●", font=(FONT, 11),
                                 bg=CLR_CARD, fg=CLR_GREEN)
        self._dot_lbl.pack(side="left")
        self._status_lbl = tk.Label(row, font=(FONT, 12, "bold"),
                                    bg=CLR_CARD, fg=CLR_FG)
        self._status_lbl.pack(side="left", padx=(px(6), 0))
        self._status_sub = tk.Label(txt, font=(FONT, 9), bg=CLR_CARD, fg=CLR_MUTED,
                                    wraplength=px(290), justify="left", anchor="w")
        self._status_sub.pack(anchor="w", pady=(px(2), 0))

        # ── 모니터 배치 카드: 저장된 배치를 그림으로 표시
        card = self._card(root, pady=(px(12), 0))
        top = tk.Frame(card, bg=CLR_CARD)
        top.pack(fill="x", padx=px(16), pady=(px(12), px(4)))
        self._monitors_lbl = tk.Label(top, font=(FONT, 9, "bold"),
                                      bg=CLR_CARD, fg=CLR_MUTED)
        self._monitors_lbl.pack(anchor="w")
        # 제목 아래 줄에 배치 (긴 번역에서도 창 너비가 늘어나지 않도록)
        self._match_lbl = tk.Label(top, font=(FONT, 9), bg=CLR_CARD, fg=CLR_GREEN)
        self._match_lbl.pack(anchor="w", pady=(px(2), 0))

        self._map = tk.Canvas(card, width=self._content_w - px(32), height=px(150),
                              bg=CLR_CARD, highlightthickness=0)
        self._map.pack(padx=px(16), pady=(0, px(14)))

        # ── 주요 동작 버튼
        row = tk.Frame(root, bg=CLR_BG)
        row.pack(fill="x", pady=(px(12), 0))
        row.columnconfigure(0, weight=1, uniform="btn")
        row.columnconfigure(1, weight=1, uniform="btn")
        wrap, self._save_btn = self._btn(row, self._on_snapshot, primary=True)
        wrap.grid(row=0, column=0, sticky="nsew", padx=(0, px(5)))
        wrap, self._restore_btn = self._btn(row, self._on_restore_now, primary=False)
        wrap.grid(row=0, column=1, sticky="nsew", padx=(px(5), 0))

        # ── 옵션 + 사용 안내
        self._autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        self._autostart_chk = tk.Checkbutton(
            root, variable=self._autostart_var, command=self._on_autostart,
            bg=CLR_BG, fg=CLR_FG, selectcolor=CLR_CARD,
            activebackground=CLR_BG, activeforeground=CLR_FG,
            font=(FONT, 9), bd=0, highlightthickness=0, cursor="hand2")
        self._autostart_chk.pack(anchor="w", pady=(px(12), 0))

        self._hint_lbl = tk.Label(root, font=(FONT, 8), bg=CLR_BG, fg=CLR_MUTED,
                                  wraplength=self._content_w, justify="left", anchor="w")
        self._hint_lbl.pack(fill="x", pady=(px(6), 0))

        # ── 로그 (기본은 접힌 상태: 마지막 한 줄만 표시)
        tk.Frame(root, bg=CLR_BORDER, height=1).pack(fill="x", pady=(px(12), 0))
        self._log_hdr = tk.Label(root, font=(FONT, 9, "bold"), bg=CLR_BG, fg=CLR_MUTED,
                                 anchor="w", cursor="hand2")
        self._log_hdr.pack(fill="x", pady=(px(8), 0))
        self._log_hdr.bind("<Button-1>", lambda e: self._toggle_log())

        self._last_log = tk.Label(root, font=(FONT_MONO, 8), bg=CLR_BG, fg=CLR_MUTED,
                                  anchor="w", width=1)
        self._last_log.pack(fill="x", pady=(px(2), 0))

        self._log_frame = tk.Frame(root, bg=CLR_CARD, highlightthickness=1,
                                   highlightbackground=CLR_BORDER)
        self._log_text = tk.Text(
            self._log_frame, bg=CLR_CARD, fg=CLR_FG,
            font=(FONT_MONO, 9), relief="flat", bd=0, highlightthickness=0,
            wrap="word", state="disabled", cursor="arrow",
            height=8, width=1,
        )
        sb = tk.Scrollbar(self._log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True, padx=px(6), pady=px(6))

        # 가로 폭 고정용 (내용 길이와 무관하게 창 너비 유지)
        tk.Frame(root, bg=CLR_BG, width=self._content_w, height=1).pack()

        self._retranslate()

    def _card(self, parent, **pack_opts):
        f = tk.Frame(parent, bg=CLR_CARD, highlightthickness=1,
                     highlightbackground=CLR_BORDER)
        f.pack(fill="x", **pack_opts)
        return f

    def _btn(self, parent, cmd, primary: bool):
        """(테두리 프레임, 버튼) 을 반환. 테두리 프레임을 배치한다."""
        bg, hover = (CLR_ACCENT, CLR_ACCENT_H) if primary else (CLR_CARD, CLR_CARD_HI)
        wrap = tk.Frame(parent, bg=CLR_ACCENT if primary else CLR_BORDER)
        b = tk.Button(wrap, command=cmd, bg=bg, fg="#ffffff" if primary else CLR_FG,
                      activebackground=hover,
                      activeforeground="#ffffff" if primary else CLR_FG,
                      relief="flat", bd=0, highlightthickness=0,
                      font=(FONT, 10, "bold" if primary else "normal"),
                      padx=self._px(8), pady=self._px(8), cursor="hand2",
                      wraplength=self._px(170))
        b.pack(fill="both", expand=True, padx=1, pady=1)
        b.bind("<Enter>", lambda e: b.configure(bg=hover))
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
        return wrap, b

    # ── 그리기 ────────────────────────────────────

    def _draw_switch(self, active: bool):
        c, px = self._switch, self._px
        c.delete("all")
        w, h = px(52), px(28)
        color = CLR_GREEN if active else CLR_OFF
        c.create_oval(0, 0, h, h, fill=color, outline=color)
        c.create_oval(w - h, 0, w, h, fill=color, outline=color)
        c.create_rectangle(h / 2, 0, w - h / 2, h, fill=color, outline=color)
        m = px(3)
        x = w - h if active else 0
        c.create_oval(x + m, m, x + h - m, h - m, fill="#ffffff", outline="#ffffff")

    def _draw_map(self):
        c, px = self._map, self._px
        c.delete("all")
        cw, ch = int(c["width"]), int(c["height"])
        saved = self.guard.saved
        if not saved:
            c.create_text(cw / 2, ch / 2, text=t("log_no_saved"),
                          fill=CLR_MUTED, font=(FONT, 10))
            return
        min_x = min(m["x"] for m in saved)
        min_y = min(m["y"] for m in saved)
        max_x = max(m["x"] + m["w"] for m in saved)
        max_y = max(m["y"] + m["h"] for m in saved)
        bw, bh = max(1, max_x - min_x), max(1, max_y - min_y)
        margin = px(4)
        k = min((cw - 2 * margin) / bw, (ch - 2 * margin) / bh)
        ox = (cw - bw * k) / 2
        oy = (ch - bh * k) / 2
        gap = px(2)
        for i, m in enumerate(saved, start=1):
            x1 = ox + (m["x"] - min_x) * k + gap
            y1 = oy + (m["y"] - min_y) * k + gap
            x2 = ox + (m["x"] + m["w"] - min_x) * k - gap
            y2 = oy + (m["y"] + m["h"] - min_y) * k - gap
            primary = m["primary"]
            _round_rect(c, x1, y1, x2, y2, px(8), fill=CLR_CARD_HI,
                        outline=CLR_ACCENT if primary else CLR_BORDER,
                        width=2 if primary else 1)
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            rw, rh = x2 - x1, y2 - y1
            num = _display_number(m["name"], i) + (" ★" if primary else "")
            detail = rh >= px(64) and rw >= px(84)
            c.create_text(cx, cy - (px(15) if detail else 0), text=num,
                          fill=CLR_FG, font=(FONT, 14, "bold"))
            if detail:
                info = f"{m['w']} × {m['h']}"
                if m["freq"] > 1:
                    info += f"\n{m['freq']} Hz"
                c.create_text(cx, cy + px(15), text=info, fill=CLR_MUTED,
                              font=(FONT, 8), justify="center")

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
        self._refresh_status()

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

    def _on_autostart(self):
        want = self._autostart_var.get()
        try:
            set_autostart(want)
        except Exception as e:
            self._autostart_var.set(not want)
            self.guard._log(t("log_config_save_failed", error=e))
            return
        self.guard._log(t("log_autostart_on") if want else t("log_autostart_off"))

    def _toggle_log(self):
        self._log_open = not self._log_open
        if self._log_open:
            self._last_log.pack_forget()
            self._log_frame.pack(fill="x", pady=(self._px(6), 0), after=self._log_hdr)
            self._log_text.see("end")
        else:
            self._log_frame.pack_forget()
            self._last_log.pack(fill="x", pady=(self._px(2), 0), after=self._log_hdr)
        self._set_log_header()

    def _set_log_header(self):
        arrow = "▾" if self._log_open else "▸"
        self._log_hdr.configure(text=f"{arrow}  {t('section_log')}")

    # ── UI 갱신 ───────────────────────────────────

    def _refresh_status(self):
        active = self.guard.enabled
        self._dot_lbl.configure(fg=CLR_GREEN if active else CLR_RED)
        self._status_lbl.configure(
            text=t("status_active") if active else t("status_inactive"))
        self._status_sub.configure(
            text=t("status_active_sub") if active else t("status_inactive_sub"))
        self._draw_switch(active)
        self._draw_map()

        # 현재 배치가 저장된 배치와 같은지 한눈에 표시
        saved = self.guard.saved
        try:
            current = get_display_configs()
        except Exception:
            current = None
        if not saved or not current:
            self._match_lbl.configure(text="")
        elif configs_equal(saved, current):
            self._match_lbl.configure(text="✓ " + t("layout_match"), fg=CLR_GREEN)
        else:
            self._match_lbl.configure(text="● " + t("layout_differs"), fg=CLR_AMBER)

        # 트레이 툴팁 갱신
        if self._tray_icon:
            try:
                status = t("status_short_active") if active else t("status_short_inactive")
                self._tray_icon.title = f"DisplayGuard [{status}]"
            except Exception:
                pass

    def set_language(self, code: str):
        """Switch UI language live (window language button or tray menu)."""
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
        self._lang_btn.configure(
            text=f"{i18n.language_name(i18n.get_language())}  ▾")
        self._save_btn.configure(text=t("btn_save"))
        self._restore_btn.configure(text=t("btn_restore_now"))
        self._monitors_lbl.configure(text=t("section_monitors"))
        self._autostart_chk.configure(text=" " + t("opt_autostart"))
        self._hint_lbl.configure(text=t("hint_rearrange") + "\n" + t("footer_hint"))
        self._set_log_header()
        # status card, switch and monitor map are handled by _refresh_status()

    # ── 스레드 안전 로그 ─────────────────────────

    def _enqueue_log(self, line: str):
        self._log_queue.put(line)

    def _process_log_queue(self):
        last = None
        try:
            self._log_text.configure(state="normal")
            while True:
                line = self._log_queue.get_nowait()
                self._log_text.insert("end", line + "\n")
                last = line
        except queue.Empty:
            pass
        finally:
            if last is not None:
                # 로그가 무한정 쌓이지 않도록 최근 500줄만 유지
                extra = int(self._log_text.index("end-1c").split(".")[0]) - 500
                if extra > 0:
                    self._log_text.delete("1.0", f"{extra + 1}.0")
                self._log_text.see("end")
                self._last_log.configure(text=last.strip())
            self._log_text.configure(state="disabled")
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
    # 번들에 포함된 아이콘 → 실행 폴더 → 데이터 폴더 순으로 찾는다.
    for d in (RES_DIR, BASE_DIR, DATA_DIR):
        candidate = os.path.join(d, "icon.ico")
        if os.path.exists(candidate):
            return candidate
    ico_path = os.path.join(DATA_DIR, "icon.ico")
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

def _make_log_handler() -> logging.Handler:
    # 로그 파일을 열 수 없어도 프로그램은 실행돼야 한다. 크기도 무한정 커지지 않게 회전.
    try:
        return logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=512 * 1024, backupCount=1, encoding="utf-8")
    except OSError:
        return logging.NullHandler()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[_make_log_handler()],
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
    if lang not in i18n.LANGUAGES:
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
        if configs:
            guard._persist()

    # WM_DISPLAYCHANGE 수신 스레드
    threading.Thread(target=run_message_loop, args=(guard,),
                     daemon=True, name="MsgLoop").start()

    # GUI (메인 스레드)
    app = App(guard)

    # 트레이 (별도 스레드로 실행)
    setup_tray(app, guard)

    # Windows 시작 시 자동 실행(--minimized)이면 창을 띄우지 않고 트레이에만 상주.
    if "--minimized" in sys.argv[1:] and app._has_tray:
        app.withdraw()

    app._enqueue_log(t("app_started", version=APP_VERSION, count=len(guard.saved)))
    for c in guard.saved:
        tag = " ★" if c["primary"] else ""
        app._enqueue_log(f"  {_short_name(c['name'])}{tag}: "
                         f"({c['x']},{c['y']}) {c['w']}×{c['h']} @{c['freq']}Hz")

    app.mainloop()


if __name__ == "__main__":
    main()
