# -*- coding: utf-8 -*-
"""
displays_win.py — Windows display backend (pure ctypes, no extra dependencies).

Everything that touches the Win32 API lives here so the rest of the app can be
exercised on any OS against displays_mock.py, which implements the same functions.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import threading
from typing import Callable, Dict, List, Optional, Tuple

log = logging.getLogger("Spectra")

user32   = ctypes.WinDLL("user32",   use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32    = ctypes.WinDLL("gdi32",    use_last_error=True)

IS_DEMO = False

# ─────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────
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
WM_HOTKEY                     = 0x0312
WM_APP                        = 0x8000
ERROR_ALREADY_EXISTS          = 183
ERROR_CLASS_ALREADY_EXISTS    = 1410

LRESULT = ctypes.c_ssize_t

# ─────────────────────────────────────────────────
# Structures
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


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize",    wt.DWORD),
        ("rcMonitor", wt.RECT),
        ("rcWork",    wt.RECT),
        ("dwFlags",   wt.DWORD),
        ("szDevice",  ctypes.c_wchar * 32),
    ]


class LUID(ctypes.Structure):
    _fields_ = [("LowPart", ctypes.c_uint32), ("HighPart", ctypes.c_int32)]


class DISPLAYCONFIG_RATIONAL(ctypes.Structure):
    _fields_ = [("Numerator", ctypes.c_uint32), ("Denominator", ctypes.c_uint32)]


class DISPLAYCONFIG_PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [("adapterId", LUID), ("id", ctypes.c_uint32),
                ("modeInfoIdx", ctypes.c_uint32), ("statusFlags", ctypes.c_uint32)]


class DISPLAYCONFIG_PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [("adapterId", LUID), ("id", ctypes.c_uint32),
                ("modeInfoIdx", ctypes.c_uint32),
                ("outputTechnology", ctypes.c_uint32),
                ("rotation", ctypes.c_uint32), ("scaling", ctypes.c_uint32),
                ("refreshRate", DISPLAYCONFIG_RATIONAL),
                ("scanLineOrdering", ctypes.c_uint32),
                ("targetAvailable", ctypes.c_int32), ("statusFlags", ctypes.c_uint32)]


class DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
    _fields_ = [("sourceInfo", DISPLAYCONFIG_PATH_SOURCE_INFO),
                ("targetInfo", DISPLAYCONFIG_PATH_TARGET_INFO),
                ("flags", ctypes.c_uint32)]


class DISPLAYCONFIG_MODE_INFO(ctypes.Structure):
    # The trailing union is 48 bytes with 8-byte alignment; we never read it.
    _fields_ = [("infoType", ctypes.c_uint32), ("id", ctypes.c_uint32),
                ("adapterId", LUID), ("_union", ctypes.c_uint64 * 6)]


class DISPLAYCONFIG_DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [("type", ctypes.c_uint32), ("size", ctypes.c_uint32),
                ("adapterId", LUID), ("id", ctypes.c_uint32)]


class DISPLAYCONFIG_SOURCE_DEVICE_NAME(ctypes.Structure):
    _fields_ = [("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
                ("viewGdiDeviceName", ctypes.c_wchar * 32)]


class DISPLAYCONFIG_TARGET_DEVICE_NAME(ctypes.Structure):
    _fields_ = [("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
                ("flags", ctypes.c_uint32),
                ("outputTechnology", ctypes.c_uint32),
                ("edidManufactureId", ctypes.c_uint16),
                ("edidProductCodeId", ctypes.c_uint16),
                ("connectorInstance", ctypes.c_uint32),
                ("monitorFriendlyDeviceName", ctypes.c_wchar * 64),
                ("monitorDevicePath", ctypes.c_wchar * 128)]


class DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO(ctypes.Structure):
    _fields_ = [("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
                ("value", ctypes.c_uint32),
                ("colorEncoding", ctypes.c_uint32),
                ("bitsPerColorChannel", ctypes.c_uint32)]


class DISPLAYCONFIG_SET_ADVANCED_COLOR_STATE(ctypes.Structure):
    _fields_ = [("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
                ("value", ctypes.c_uint32)]


class PHYSICAL_MONITOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("hPhysicalMonitor", wt.HANDLE),
                ("szPhysicalMonitorDescription", ctypes.c_wchar * 128)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wt.HWND), ("message", ctypes.c_uint),
                ("wParam", wt.WPARAM), ("lParam", wt.LPARAM),
                ("time", wt.DWORD), ("pt", wt.POINT)]


WNDPROC_TYPE = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM)
MONITORENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HMONITOR, wt.HDC,
                                     ctypes.POINTER(wt.RECT), wt.LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
WINEVENTPROC = ctypes.WINFUNCTYPE(None, wt.HANDLE, wt.DWORD, wt.HWND, wt.LONG,
                                  wt.LONG, wt.DWORD, wt.DWORD)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize",        ctypes.c_uint),  ("style",         ctypes.c_uint),
        ("lpfnWndProc",   WNDPROC_TYPE),   ("cbClsExtra",    ctypes.c_int),
        ("cbWndExtra",    ctypes.c_int),   ("hInstance",     wt.HINSTANCE),
        ("hIcon",         wt.HICON),       ("hCursor",       wt.HANDLE),
        ("hbrBackground", wt.HBRUSH),      ("lpszMenuName",  wt.LPCWSTR),
        ("lpszClassName", wt.LPCWSTR),     ("hIconSm",       wt.HICON),
    ]


# ─────────────────────────────────────────────────
# Signatures (explicit so 64-bit handles/pointers are never truncated)
# ─────────────────────────────────────────────────

def _sig(func, restype, *argtypes):
    func.restype = restype
    func.argtypes = list(argtypes)


_sig(user32.EnumDisplayDevicesW, wt.BOOL, wt.LPCWSTR, wt.DWORD,
     ctypes.POINTER(DISPLAY_DEVICE), wt.DWORD)
_sig(user32.EnumDisplaySettingsExW, wt.BOOL, wt.LPCWSTR, wt.DWORD,
     ctypes.POINTER(DEVMODE), wt.DWORD)
_sig(user32.ChangeDisplaySettingsExW, ctypes.c_long, wt.LPCWSTR,
     ctypes.POINTER(DEVMODE), wt.HWND, wt.DWORD, ctypes.c_void_p)
_sig(user32.EnumDisplayMonitors, wt.BOOL, wt.HDC, ctypes.POINTER(wt.RECT),
     MONITORENUMPROC, wt.LPARAM)
_sig(user32.GetMonitorInfoW, wt.BOOL, wt.HMONITOR, ctypes.POINTER(MONITORINFOEXW))
_sig(user32.GetDisplayConfigBufferSizes, ctypes.c_long, ctypes.c_uint32,
     ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32))
_sig(user32.QueryDisplayConfig, ctypes.c_long, ctypes.c_uint32,
     ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(DISPLAYCONFIG_PATH_INFO),
     ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(DISPLAYCONFIG_MODE_INFO),
     ctypes.c_void_p)
_sig(user32.DisplayConfigGetDeviceInfo, ctypes.c_long, ctypes.c_void_p)
_sig(user32.DisplayConfigSetDeviceInfo, ctypes.c_long, ctypes.c_void_p)

_sig(kernel32.CreateMutexW, wt.HANDLE, ctypes.c_void_p, wt.BOOL, wt.LPCWSTR)
_sig(kernel32.CloseHandle, wt.BOOL, wt.HANDLE)
_sig(kernel32.GetModuleHandleW, wt.HMODULE, wt.LPCWSTR)
_sig(kernel32.GetCurrentThreadId, wt.DWORD)
_sig(user32.MessageBoxW, ctypes.c_int, wt.HWND, wt.LPCWSTR, wt.LPCWSTR, ctypes.c_uint)

_sig(user32.DefWindowProcW, LRESULT, wt.HWND, ctypes.c_uint, wt.WPARAM, wt.LPARAM)
_sig(user32.RegisterClassExW, wt.ATOM, ctypes.POINTER(WNDCLASSEXW))
_sig(user32.UnregisterClassW, wt.BOOL, wt.LPCWSTR, wt.HINSTANCE)
_sig(user32.CreateWindowExW, wt.HWND, wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
     ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
     wt.HWND, wt.HMENU, wt.HINSTANCE, ctypes.c_void_p)
_sig(user32.GetMessageW, ctypes.c_int, ctypes.POINTER(MSG), wt.HWND,
     ctypes.c_uint, ctypes.c_uint)
_sig(user32.TranslateMessage, wt.BOOL, ctypes.POINTER(MSG))
_sig(user32.DispatchMessageW, LRESULT, ctypes.POINTER(MSG))
_sig(user32.PostQuitMessage, None, ctypes.c_int)
_sig(user32.PostThreadMessageW, wt.BOOL, wt.DWORD, ctypes.c_uint, wt.WPARAM, wt.LPARAM)
_sig(user32.RegisterHotKey, wt.BOOL, wt.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint)
_sig(user32.UnregisterHotKey, wt.BOOL, wt.HWND, ctypes.c_int)
_sig(user32.SetWinEventHook, wt.HANDLE, wt.DWORD, wt.DWORD, wt.HMODULE,
     WINEVENTPROC, wt.DWORD, wt.DWORD, wt.DWORD)

_sig(user32.GetForegroundWindow, wt.HWND)
_sig(user32.SetForegroundWindow, wt.BOOL, wt.HWND)
_sig(user32.FindWindowW, wt.HWND, wt.LPCWSTR, wt.LPCWSTR)
_sig(user32.GetWindowRect, wt.BOOL, wt.HWND, ctypes.POINTER(wt.RECT))
_sig(user32.SetWindowPos, wt.BOOL, wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
     ctypes.c_int, ctypes.c_int, ctypes.c_uint)
_sig(user32.ShowWindow, wt.BOOL, wt.HWND, ctypes.c_int)
_sig(user32.IsZoomed, wt.BOOL, wt.HWND)
_sig(user32.IsIconic, wt.BOOL, wt.HWND)
_sig(user32.IsWindowVisible, wt.BOOL, wt.HWND)
_sig(user32.GetWindowTextLengthW, ctypes.c_int, wt.HWND)
_sig(user32.GetWindowLongW, wt.LONG, wt.HWND, ctypes.c_int)
_sig(user32.GetWindow, wt.HWND, wt.HWND, ctypes.c_uint)
_sig(user32.EnumWindows, wt.BOOL, WNDENUMPROC, wt.LPARAM)
_sig(user32.MonitorFromWindow, wt.HMONITOR, wt.HWND, wt.DWORD)
_sig(user32.MonitorFromPoint, wt.HMONITOR, wt.POINT, wt.DWORD)
_sig(user32.GetCursorPos, wt.BOOL, ctypes.POINTER(wt.POINT))
_sig(user32.GetAsyncKeyState, ctypes.c_short, ctypes.c_int)

_sig(gdi32.CreateDCW, wt.HDC, wt.LPCWSTR, wt.LPCWSTR, wt.LPCWSTR, ctypes.c_void_p)
_sig(gdi32.DeleteDC, wt.BOOL, wt.HDC)
_sig(gdi32.SetDeviceGammaRamp, wt.BOOL, wt.HDC, ctypes.c_void_p)


def _optional_dll(name: str):
    try:
        return ctypes.WinDLL(name, use_last_error=True)
    except OSError:
        return None


dxva2  = _optional_dll("dxva2")
dwmapi = _optional_dll("dwmapi")
shcore = _optional_dll("shcore")

if dxva2:
    _sig(dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR, wt.BOOL, wt.HMONITOR,
         ctypes.POINTER(wt.DWORD))
    _sig(dxva2.GetPhysicalMonitorsFromHMONITOR, wt.BOOL, wt.HMONITOR, wt.DWORD,
         ctypes.POINTER(PHYSICAL_MONITOR))
    _sig(dxva2.DestroyPhysicalMonitors, wt.BOOL, wt.DWORD,
         ctypes.POINTER(PHYSICAL_MONITOR))
    for _n in ("GetMonitorBrightness", "GetMonitorContrast"):
        _sig(getattr(dxva2, _n), wt.BOOL, wt.HANDLE, ctypes.POINTER(wt.DWORD),
             ctypes.POINTER(wt.DWORD), ctypes.POINTER(wt.DWORD))
    for _n in ("SetMonitorBrightness", "SetMonitorContrast"):
        _sig(getattr(dxva2, _n), wt.BOOL, wt.HANDLE, wt.DWORD)
if dwmapi:
    _sig(dwmapi.DwmGetWindowAttribute, ctypes.c_long, wt.HWND, wt.DWORD,
         ctypes.c_void_p, wt.DWORD)
if shcore:
    _sig(shcore.GetDpiForMonitor, ctypes.c_long, wt.HMONITOR, ctypes.c_int,
         ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint))


def init_process() -> None:
    """Per-monitor DPI awareness, so every coordinate we read is in real pixels."""
    try:
        _sig(user32.SetProcessDpiAwarenessContext, wt.BOOL, ctypes.c_void_p)
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return
    except Exception:
        pass
    try:
        if shcore:
            shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


# ─────────────────────────────────────────────────
# Single instance / message box
# ─────────────────────────────────────────────────

_mutex = None


def acquire_single_instance(name: str) -> bool:
    global _mutex
    handle = kernel32.CreateMutexW(None, False, name)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        if handle:
            kernel32.CloseHandle(handle)
        return False
    _mutex = handle
    return True


def message_box(title: str, body: str) -> None:
    user32.MessageBoxW(None, body, title, 0x30)


def focus_window_by_title(title: str) -> bool:
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        return False
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True


# ─────────────────────────────────────────────────
# Monitor enumeration
# ─────────────────────────────────────────────────

def _hmonitors() -> Dict[str, Tuple[int, Tuple[int, int, int, int]]]:
    """GDI device name → (HMONITOR, work-area rect)."""
    out: Dict[str, Tuple[int, Tuple[int, int, int, int]]] = {}

    def cb(hmon, _hdc, _rect, _lp):
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(mi)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            w = mi.rcWork
            out[mi.szDevice] = (hmon, (w.left, w.top, w.right, w.bottom))
        return True

    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(cb), 0)
    return out


_OUTPUT_TECH = {
    0: "VGA", 1: "S-Video", 2: "Composite", 3: "Component", 4: "DVI", 5: "HDMI",
    6: "LVDS", 9: "SDI", 10: "DisplayPort", 11: "DisplayPort (internal)",
    12: "UDI", 13: "UDI (internal)", 15: "Miracast", 16: "Indirect (wired)",
    17: "Indirect (virtual)", 0x80000000: "Internal",
}


def _edid_vendor(raw: int) -> str:
    v = ((raw & 0xFF) << 8) | (raw >> 8)
    chars = [(v >> 10) & 0x1F, (v >> 5) & 0x1F, v & 0x1F]
    if not all(1 <= c <= 26 for c in chars):
        return ""
    return "".join(chr(64 + c) for c in chars)


def _display_paths() -> Dict[str, Dict]:
    """GDI device name → target details from QueryDisplayConfig (best effort)."""
    out: Dict[str, Dict] = {}
    n_paths, n_modes = ctypes.c_uint32(), ctypes.c_uint32()
    if user32.GetDisplayConfigBufferSizes(2, ctypes.byref(n_paths), ctypes.byref(n_modes)):
        return out
    paths = (DISPLAYCONFIG_PATH_INFO * max(1, n_paths.value))()
    modes = (DISPLAYCONFIG_MODE_INFO * max(1, n_modes.value))()
    if user32.QueryDisplayConfig(2, ctypes.byref(n_paths), paths,
                                 ctypes.byref(n_modes), modes, None):
        return out
    for i in range(n_paths.value):
        p = paths[i]
        src = DISPLAYCONFIG_SOURCE_DEVICE_NAME()
        src.header.type = 1
        src.header.size = ctypes.sizeof(src)
        src.header.adapterId = p.sourceInfo.adapterId
        src.header.id = p.sourceInfo.id
        if user32.DisplayConfigGetDeviceInfo(ctypes.byref(src)):
            continue
        info: Dict = {"adapter_id": (p.targetInfo.adapterId.LowPart,
                                     p.targetInfo.adapterId.HighPart),
                      "target_id": p.targetInfo.id,
                      "connector": _OUTPUT_TECH.get(p.targetInfo.outputTechnology, "")}
        tgt = DISPLAYCONFIG_TARGET_DEVICE_NAME()
        tgt.header.type = 2
        tgt.header.size = ctypes.sizeof(tgt)
        tgt.header.adapterId = p.targetInfo.adapterId
        tgt.header.id = p.targetInfo.id
        if not user32.DisplayConfigGetDeviceInfo(ctypes.byref(tgt)):
            info["label"] = tgt.monitorFriendlyDeviceName
            vendor = _edid_vendor(tgt.edidManufactureId)
            if vendor:
                info["edid"] = f"{vendor}-{tgt.edidProductCodeId:04X}"
        col = DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO()
        col.header.type = 9
        col.header.size = ctypes.sizeof(col)
        col.header.adapterId = p.targetInfo.adapterId
        col.header.id = p.targetInfo.id
        if not user32.DisplayConfigGetDeviceInfo(ctypes.byref(col)):
            info["hdr_supported"] = bool(col.value & 1) and not bool(col.value & 8)
            info["hdr_enabled"] = bool(col.value & 2)
            info["bits_per_channel"] = col.bitsPerColorChannel
        out[src.viewGdiDeviceName] = info
    return out


def get_display_configs() -> List[Dict]:
    """The layout: one dict per active display (the fields the guard compares)."""
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


def get_monitor_details() -> Dict[str, Dict]:
    """Extra, display-only details per GDI device name."""
    details: Dict[str, Dict] = {}
    adapters: Dict[str, str] = {}
    i = 0
    while True:
        dd = DISPLAY_DEVICE()
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        adapters[dd.DeviceName] = dd.DeviceString
    try:
        paths = _display_paths()
    except Exception as e:
        log.warning("QueryDisplayConfig failed: %s", e)
        paths = {}
    hmons = _hmonitors()
    for name, adapter in adapters.items():
        d: Dict = {"adapter": adapter}
        p = paths.get(name, {})
        for k in ("label", "connector", "edid", "bits_per_channel"):
            if p.get(k):
                d[k] = p[k]
        if "hdr_supported" in p:
            d["hdr"] = {"supported": p["hdr_supported"], "enabled": p["hdr_enabled"]}
        if name in hmons:
            hmon, work = hmons[name]
            d["work"] = list(work)
            if shcore:
                dx, dy = ctypes.c_uint(), ctypes.c_uint()
                if shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dx), ctypes.byref(dy)) == 0:
                    d["scale"] = round(dx.value / 96 * 100)
        details[name] = d
    return details


def list_modes(name: str) -> List[Dict]:
    seen, i = set(), 0
    while True:
        dm = DEVMODE()
        if not user32.EnumDisplaySettingsExW(name, i, ctypes.byref(dm), 0):
            break
        i += 1
        if dm.dmBitsPerPel != 32:
            continue
        seen.add((dm.dmPelsWidth, dm.dmPelsHeight, dm.dmDisplayFrequency))
    return [{"w": w, "h": h, "freq": f}
            for w, h, f in sorted(seen, key=lambda m: (-m[0] * m[1], -m[0], -m[2]))]


def apply_display_configs(configs: List[Dict]) -> bool:
    ok = True
    for c in sorted(configs, key=lambda c: (not c["primary"])):
        dm = DEVMODE()
        dm.dmFields = (DM_POSITION | DM_PELSWIDTH | DM_PELSHEIGHT
                       | DM_BITSPERPEL | DM_DISPLAYORIENTATION)
        if c["freq"] > 1:   # 0/1 = "hardware default" → leave the refresh rate alone
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
            log.warning("ChangeDisplaySettingsEx(%s) returned %d", c["name"], ret)
            ok = False
    user32.ChangeDisplaySettingsExW(None, None, None, 0, None)
    return ok


# ─────────────────────────────────────────────────
# HDR
# ─────────────────────────────────────────────────

def set_hdr(name: str, enabled: bool) -> bool:
    p = _display_paths().get(name)
    if not p or not p.get("hdr_supported"):
        return False
    st = DISPLAYCONFIG_SET_ADVANCED_COLOR_STATE()
    st.header.type = 10
    st.header.size = ctypes.sizeof(st)
    st.header.adapterId.LowPart, st.header.adapterId.HighPart = p["adapter_id"]
    st.header.id = p["target_id"]
    st.value = 1 if enabled else 0
    return user32.DisplayConfigSetDeviceInfo(ctypes.byref(st)) == 0


# ─────────────────────────────────────────────────
# Software colour correction (GDI gamma ramp)
# ─────────────────────────────────────────────────

def set_gamma_ramp(name: str, ramp: List[List[int]]) -> bool:
    """ramp: 3 channels × 256 entries, each 0..65535."""
    buf = ((ctypes.c_uint16 * 256) * 3)()
    for ch in range(3):
        for i in range(256):
            buf[ch][i] = ramp[ch][i]
    hdc = gdi32.CreateDCW(None, name, None, None)
    if not hdc:
        return False
    try:
        return bool(gdi32.SetDeviceGammaRamp(hdc, ctypes.byref(buf)))
    finally:
        gdi32.DeleteDC(hdc)


# ─────────────────────────────────────────────────
# DDC/CI (monitor hardware brightness / contrast)
# ─────────────────────────────────────────────────

def _with_physical_monitor(name: str, fn):
    if not dxva2:
        return None
    entry = _hmonitors().get(name)
    if not entry:
        return None
    hmon = entry[0]
    count = wt.DWORD()
    if not dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, ctypes.byref(count)) \
            or count.value == 0:
        return None
    arr = (PHYSICAL_MONITOR * count.value)()
    if not dxva2.GetPhysicalMonitorsFromHMONITOR(hmon, count.value, arr):
        return None
    try:
        return fn(arr[0].hPhysicalMonitor)
    finally:
        dxva2.DestroyPhysicalMonitors(count.value, arr)


def ddc_get(name: str) -> Optional[Dict]:
    """{'brightness': {'cur','max'}, 'contrast': {...}} or None if not responding."""
    def read(h):
        out = {}
        for key, fn in (("brightness", dxva2.GetMonitorBrightness),
                        ("contrast", dxva2.GetMonitorContrast)):
            lo, cur, hi = wt.DWORD(), wt.DWORD(), wt.DWORD()
            if fn(h, ctypes.byref(lo), ctypes.byref(cur), ctypes.byref(hi)):
                out[key] = {"min": lo.value, "cur": cur.value, "max": hi.value}
        return out or None
    return _with_physical_monitor(name, read)


def ddc_set(name: str, key: str, value: int) -> bool:
    fn = {"brightness": "SetMonitorBrightness", "contrast": "SetMonitorContrast"}.get(key)
    if not fn or not dxva2:
        return False
    return bool(_with_physical_monitor(name, lambda h: getattr(dxva2, fn)(h, int(value))))


# ─────────────────────────────────────────────────
# Graphics adapter info (registry, best effort)
# ─────────────────────────────────────────────────

def system_info() -> Dict:
    import platform
    import winreg
    adapters, seen, i = [], set(), 0
    while True:
        dd = DISPLAY_DEVICE()
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        i += 1
        if not (dd.StateFlags & DISPLAY_DEVICE_ACTIVE) or dd.DeviceString in seen:
            continue
        seen.add(dd.DeviceString)
        a = {"name": dd.DeviceString}
        key_path = dd.DeviceKey
        prefix = "\\Registry\\Machine\\"
        if key_path.lower().startswith(prefix.lower()):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path[len(prefix):]) as k:
                    for out_key, value_name in (("driver_version", "DriverVersion"),
                                                ("driver_date", "DriverDate"),
                                                ("vram", "HardwareInformation.qwMemorySize")):
                        try:
                            v, _ = winreg.QueryValueEx(k, value_name)
                            if isinstance(v, bytes):
                                v = int.from_bytes(v, "little")
                            a[out_key] = v
                        except OSError:
                            pass
            except OSError:
                pass
        adapters.append(a)
    return {"os": f"Windows {platform.release()} ({platform.version()})",
            "adapters": adapters}


def gpu_stats() -> List[Dict]:
    """Live read-only GPU sensors (NVIDIA only; [] when unavailable)."""
    import gpu_nvml
    return gpu_nvml.stats()


# ─────────────────────────────────────────────────
# Windows (for zones)
# ─────────────────────────────────────────────────

SWP_NOZORDER, SWP_NOACTIVATE = 0x0004, 0x0010
GWL_EXSTYLE, WS_EX_TOOLWINDOW, GW_OWNER = -20, 0x00000080, 4


def cursor_pos() -> Tuple[int, int]:
    pt = wt.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def is_key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def foreground_window() -> int:
    return user32.GetForegroundWindow() or 0


def window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    r = wt.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r.left, r.top, r.right, r.bottom


def _frame_margins(hwnd: int) -> Tuple[int, int, int, int]:
    """Invisible resize borders (window rect is larger than what you see)."""
    if not dwmapi:
        return 0, 0, 0, 0
    outer, vis = wt.RECT(), wt.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(outer)):
        return 0, 0, 0, 0
    if dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(vis), ctypes.sizeof(vis)):
        return 0, 0, 0, 0
    return (vis.left - outer.left, vis.top - outer.top,
            outer.right - vis.right, outer.bottom - vis.bottom)


def move_window(hwnd: int, rect: Tuple[int, int, int, int]) -> bool:
    """Place the *visible* frame of hwnd exactly on rect (left, top, right, bottom)."""
    if not hwnd:
        return False
    if user32.IsZoomed(hwnd) or user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    ml, mt, mr, mb = _frame_margins(hwnd)
    l, t, r, b = rect
    return bool(user32.SetWindowPos(hwnd, None, l - ml, t - mt,
                                    (r - l) + ml + mr, (b - t) + mt + mb,
                                    SWP_NOZORDER | SWP_NOACTIVATE))


def list_app_windows() -> List[int]:
    """Top-level windows a user would call 'open windows', front to back."""
    result: List[int] = []

    def cb(hwnd, _lp):
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        if user32.GetWindowTextLengthW(hwnd) == 0 or user32.GetWindow(hwnd, GW_OWNER):
            return True
        if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        if dwmapi:
            cloaked = wt.DWORD()
            if dwmapi.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked),
                                            ctypes.sizeof(cloaked)) == 0 and cloaked.value:
                return True
        result.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return result


# ─────────────────────────────────────────────────
# Message loop: display-change notifications, global hotkeys, window-drag events
# ─────────────────────────────────────────────────

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 1, 2, 4, 8, 0x4000
EVENT_SYSTEM_MOVESIZEEND = 0x000B
_WM_SET_HOTKEYS = WM_APP + 1


class EventLoop:
    """One background thread that owns everything needing a Win32 message queue."""

    def __init__(self, on_display_change: Callable[[], None],
                 on_hotkey: Callable[[str], None],
                 on_window_dropped: Callable[[int], None]):
        self._on_display_change = on_display_change
        self._on_hotkey = on_hotkey
        self._on_window_dropped = on_window_dropped
        self._thread_id = 0
        self._wanted: Dict[str, Tuple[int, int]] = {}
        self._registered: Dict[int, str] = {}
        self.failed: List[str] = []
        self._lock = threading.Lock()
        self._ready = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True, name="Win32Loop").start()
        self._ready.wait(5)

    def set_hotkeys(self, hotkeys: Dict[str, Tuple[int, int]]) -> None:
        """hotkeys: action → (modifiers, virtual-key). Applied on the loop thread."""
        with self._lock:
            self._wanted = dict(hotkeys)
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, _WM_SET_HOTKEYS, 0, 0)

    def _apply_hotkeys(self) -> None:
        for hk_id in list(self._registered):
            user32.UnregisterHotKey(None, hk_id)
        self._registered.clear()
        failed = []
        with self._lock:
            wanted = dict(self._wanted)
        for n, (action, (mods, vk)) in enumerate(wanted.items(), start=1):
            if user32.RegisterHotKey(None, n, mods | MOD_NOREPEAT, vk):
                self._registered[n] = action
            else:
                failed.append(action)
        self.failed = failed

    def _run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_DISPLAYCHANGE:
                try:
                    self._on_display_change()
                except Exception:
                    log.exception("display-change handler failed")
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        def win_event(_hook, event, hwnd, id_object, _id_child, _thread, _time):
            if event == EVENT_SYSTEM_MOVESIZEEND and hwnd and id_object == 0:
                try:
                    self._on_window_dropped(hwnd)
                except Exception:
                    log.exception("window-drop handler failed")

        # Keep references alive for the lifetime of the loop.
        wnd_cb, event_cb = WNDPROC_TYPE(wnd_proc), WINEVENTPROC(win_event)
        hinstance = kernel32.GetModuleHandleW(None)
        cls_name = "SpectraStudio_MsgWnd"
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = wnd_cb
        wc.hInstance = hinstance
        wc.lpszClassName = cls_name
        atom = user32.RegisterClassExW(ctypes.byref(wc))
        if not atom and ctypes.get_last_error() != ERROR_CLASS_ALREADY_EXISTS:
            log.error("RegisterClassExW failed (%d)", ctypes.get_last_error())
        # A hidden top-level window (message-only windows do not get broadcasts).
        hwnd = user32.CreateWindowExW(0, cls_name, "SpectraStudio", 0, 0, 0, 0, 0,
                                      None, None, hinstance, None)
        if not hwnd:
            log.error("CreateWindowExW failed (%d)", ctypes.get_last_error())
        user32.SetWinEventHook(EVENT_SYSTEM_MOVESIZEEND, EVENT_SYSTEM_MOVESIZEEND,
                               None, event_cb, 0, 0, 0)

        msg = MSG()
        # Touch the queue so PostThreadMessage works before the first GetMessage.
        user32.GetAsyncKeyState(0)
        self._apply_hotkeys()
        self._ready.set()
        while True:
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret in (0, -1):
                break
            if msg.message == WM_HOTKEY:
                action = self._registered.get(int(msg.wParam))
                if action:
                    try:
                        self._on_hotkey(action)
                    except Exception:
                        log.exception("hotkey handler failed")
                continue
            if msg.message == _WM_SET_HOTKEYS:
                self._apply_hotkeys()
                continue
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))


# ─────────────────────────────────────────────────
# "Identify" overlay — a big number on every monitor for two seconds
# ─────────────────────────────────────────────────

def identify(numbered: List[Tuple[str, Tuple[int, int, int, int]]]) -> None:
    """numbered: [(label, (x, y, w, h)), ...] in physical pixels."""
    def run():
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            for label, (x, y, w, h) in numbered:
                size = max(120, min(w, h) // 5)
                top = tk.Toplevel(root)
                top.overrideredirect(True)
                top.attributes("-topmost", True)
                top.configure(bg="#4d8eff")
                tk.Label(top, text=label, font=("Segoe UI", size // 2, "bold"),
                         bg="#0b1326", fg="#adc6ff").pack(fill="both", expand=True,
                                                          padx=4, pady=4)
                top.geometry(f"{size}x{size}+{x + 40}+{y + 40}")
            root.after(2000, root.destroy)
            root.mainloop()
        except Exception:
            log.exception("identify overlay failed")

    threading.Thread(target=run, daemon=True, name="Identify").start()


# ─────────────────────────────────────────────────
# Start with Windows (HKCU Run)
# ─────────────────────────────────────────────────

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_autostart_enabled(value_name: str) -> bool:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, value_name)
        return True
    except OSError:
        return False


def set_autostart(value_name: str, command: Optional[str]) -> None:
    """command=None removes the entry. Raises OSError on failure."""
    import winreg
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
        if command:
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, value_name)
            except FileNotFoundError:
                pass
