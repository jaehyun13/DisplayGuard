# -*- coding: utf-8 -*-
"""
displays_mock.py — in-memory stand-in for displays_win.py.

Used by `--demo` and on non-Windows machines so the UI and the app logic can be
developed and tested without touching real display hardware. Nothing here talks
to the OS; the "monitors" below are made up.
"""
from __future__ import annotations

import copy
import threading
from typing import Callable, Dict, List, Optional, Tuple

IS_DEMO = True

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 1, 2, 4, 8

_lock = threading.Lock()

_configs: List[Dict] = [
    {"name": "\\\\.\\DISPLAY1", "primary": True,  "x": 0,     "y": 0,
     "w": 3840, "h": 2160, "bpp": 32, "freq": 144, "rot": 0},
    {"name": "\\\\.\\DISPLAY2", "primary": False, "x": -1440, "y": -200,
     "w": 1440, "h": 2560, "bpp": 32, "freq": 240, "rot": 1},
    {"name": "\\\\.\\DISPLAY3", "primary": False, "x": 3840,  "y": 360,
     "w": 2560, "h": 1440, "bpp": 32, "freq": 60,  "rot": 0},
]

_details: Dict[str, Dict] = {
    "\\\\.\\DISPLAY1": {"adapter": "Demo Graphics Adapter", "label": "Demo 32\" 4K",
                        "connector": "DisplayPort", "edid": "DEM-3201",
                        "bits_per_channel": 10, "scale": 150,
                        "hdr": {"supported": True, "enabled": False}},
    "\\\\.\\DISPLAY2": {"adapter": "Demo Graphics Adapter", "label": "Demo 27\" QHD",
                        "connector": "DisplayPort", "edid": "DEM-2702",
                        "bits_per_channel": 8, "scale": 100,
                        "hdr": {"supported": False, "enabled": False}},
    "\\\\.\\DISPLAY3": {"adapter": "Demo Graphics Adapter", "label": "Demo 27\" QHD B",
                        "connector": "HDMI", "edid": "DEM-2703",
                        "bits_per_channel": 8, "scale": 100,
                        "hdr": {"supported": True, "enabled": True}},
}

_NATIVE = {"\\\\.\\DISPLAY1": (3840, 2160, (144, 120, 60)),
           "\\\\.\\DISPLAY2": (2560, 1440, (240, 144, 60)),
           "\\\\.\\DISPLAY3": (2560, 1440, (60,))}
_SIZES = [(3840, 2160), (2560, 1440), (1920, 1080), (1600, 900), (1280, 720)]

_ddc: Dict[str, Dict] = {
    "\\\\.\\DISPLAY1": {"brightness": {"min": 0, "cur": 75, "max": 100},
                        "contrast": {"min": 0, "cur": 70, "max": 100}},
    "\\\\.\\DISPLAY3": {"brightness": {"min": 0, "cur": 40, "max": 100},
                        "contrast": {"min": 0, "cur": 50, "max": 100}},
}

gamma_calls: List[str] = []
moved_windows: List[Tuple[int, Tuple[int, int, int, int]]] = []


def init_process() -> None:
    pass


def acquire_single_instance(name: str) -> bool:
    return True


def message_box(title: str, body: str) -> None:
    print(f"[{title}] {body}")


def focus_window_by_title(title: str) -> bool:
    return False


def get_display_configs() -> List[Dict]:
    with _lock:
        return copy.deepcopy(_configs)


def get_monitor_details() -> Dict[str, Dict]:
    with _lock:
        out = copy.deepcopy(_details)
        for c in _configs:
            out[c["name"]]["work"] = [c["x"], c["y"], c["x"] + c["w"], c["y"] + c["h"] - 48]
        return out


def list_modes(name: str) -> List[Dict]:
    if name not in _NATIVE:
        return []
    nw, nh, freqs = _NATIVE[name]
    with _lock:
        portrait = next(c for c in _configs if c["name"] == name)["rot"] in (1, 3)
    modes = []
    for w, h in _SIZES:
        if w > nw:
            continue
        for f in freqs:
            modes.append({"w": h if portrait else w, "h": w if portrait else h, "freq": f})
    return modes


def apply_display_configs(configs: List[Dict]) -> bool:
    global _configs
    with _lock:
        _configs = copy.deepcopy(configs)
    return True


def set_hdr(name: str, enabled: bool) -> bool:
    with _lock:
        hdr = _details.get(name, {}).get("hdr")
        if not hdr or not hdr["supported"]:
            return False
        hdr["enabled"] = bool(enabled)
        return True


def set_gamma_ramp(name: str, ramp: List[List[int]]) -> bool:
    gamma_calls.append(name)
    return True


def ddc_get(name: str) -> Optional[Dict]:
    with _lock:
        return copy.deepcopy(_ddc.get(name))


def ddc_set(name: str, key: str, value: int) -> bool:
    with _lock:
        if name not in _ddc or key not in _ddc[name]:
            return False
        _ddc[name][key]["cur"] = int(value)
        return True


def system_info() -> Dict:
    return {"os": "Demo mode (no real hardware)",
            "adapters": [{"name": "Demo Graphics Adapter",
                          "driver_version": "0.0.0.0", "vram": 8 * 1024 ** 3}]}


def gpu_stats() -> List[Dict]:
    """Synthetic numbers so the monitoring panel can be previewed in demo mode."""
    import math
    import time
    t = time.time()
    wave = (math.sin(t / 4.0) + 1) / 2
    return [{"index": 0, "name": "Demo Graphics Adapter",
             "temp_c": int(48 + 20 * wave), "load_pct": int(20 + 70 * wave),
             "vram_used": int((2.5 + 3 * wave) * 1024 ** 3), "vram_total": 8 * 1024 ** 3,
             "power_w": round(60 + 140 * wave, 1), "power_limit_w": 220.0,
             "fan_pct": int(30 + 35 * wave),
             "clock_core_mhz": int(1500 + 600 * wave), "clock_mem_mhz": 7000}]


def cursor_pos() -> Tuple[int, int]:
    return 0, 0


def is_key_down(vk: int) -> bool:
    return False


def foreground_window() -> int:
    return 0


def window_rect(hwnd: int) -> Optional[Tuple[int, int, int, int]]:
    return None


def move_window(hwnd: int, rect: Tuple[int, int, int, int]) -> bool:
    moved_windows.append((hwnd, tuple(rect)))
    return True


def list_app_windows() -> List[int]:
    return []


class EventLoop:
    def __init__(self, on_display_change: Callable[[], None],
                 on_hotkey: Callable[[str], None],
                 on_window_dropped: Callable[[int], None]):
        self.failed: List[str] = []

    def start(self) -> None:
        pass

    def set_hotkeys(self, hotkeys: Dict[str, Tuple[int, int]]) -> None:
        pass


def identify(numbered) -> None:
    pass


_autostart = False


def is_autostart_enabled(value_name: str) -> bool:
    return _autostart


def set_autostart(value_name: str, command: Optional[str]) -> None:
    global _autostart
    _autostart = bool(command)
