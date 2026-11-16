# -*- coding: utf-8 -*-
"""
gpu_nvml.py — read-only GPU telemetry through NVIDIA's NVML library (nvml.dll),
which ships with the NVIDIA driver. Nothing here changes any GPU setting.

Other vendors have no equivalent public library, so stats() returns [] for them.
"""
from __future__ import annotations

import ctypes
import logging
import os
import threading
from typing import Dict, List, Optional

log = logging.getLogger("Spectra")

_lock = threading.Lock()
_lib = None
_state = "new"          # new → ready | unavailable


class _Utilization(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _Memory(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong),
                ("used", ctypes.c_ulonglong)]


def _load():
    candidates = ["nvml.dll"]
    for var in ("ProgramW6432", "ProgramFiles"):
        base = os.environ.get(var)
        if base:
            candidates.append(os.path.join(base, "NVIDIA Corporation", "NVSMI", "nvml.dll"))
    for path in candidates:
        try:
            return ctypes.CDLL(path)
        except OSError:
            continue
    return None


def _init() -> bool:
    global _lib, _state
    if _state == "ready":
        return True
    if _state == "unavailable":
        return False
    lib = _load()
    if lib is None:
        _state = "unavailable"
        return False
    try:
        handle = ctypes.c_void_p
        uint_p = ctypes.POINTER(ctypes.c_uint)
        lib.nvmlInit_v2.restype = ctypes.c_int
        lib.nvmlInit_v2.argtypes = []
        lib.nvmlDeviceGetCount_v2.restype = ctypes.c_int
        lib.nvmlDeviceGetCount_v2.argtypes = [uint_p]
        lib.nvmlDeviceGetHandleByIndex_v2.restype = ctypes.c_int
        lib.nvmlDeviceGetHandleByIndex_v2.argtypes = [ctypes.c_uint, ctypes.POINTER(handle)]
        lib.nvmlDeviceGetName.restype = ctypes.c_int
        lib.nvmlDeviceGetName.argtypes = [handle, ctypes.c_char_p, ctypes.c_uint]
        lib.nvmlDeviceGetTemperature.restype = ctypes.c_int
        lib.nvmlDeviceGetTemperature.argtypes = [handle, ctypes.c_int, uint_p]
        lib.nvmlDeviceGetUtilizationRates.restype = ctypes.c_int
        lib.nvmlDeviceGetUtilizationRates.argtypes = [handle, ctypes.POINTER(_Utilization)]
        lib.nvmlDeviceGetMemoryInfo.restype = ctypes.c_int
        lib.nvmlDeviceGetMemoryInfo.argtypes = [handle, ctypes.POINTER(_Memory)]
        for fn in ("nvmlDeviceGetPowerUsage", "nvmlDeviceGetEnforcedPowerLimit",
                   "nvmlDeviceGetFanSpeed"):
            getattr(lib, fn).restype = ctypes.c_int
            getattr(lib, fn).argtypes = [handle, uint_p]
        lib.nvmlDeviceGetClockInfo.restype = ctypes.c_int
        lib.nvmlDeviceGetClockInfo.argtypes = [handle, ctypes.c_int, uint_p]
        if lib.nvmlInit_v2() != 0:
            _state = "unavailable"
            return False
    except Exception as e:
        log.warning("NVML init failed: %s", e)
        _state = "unavailable"
        return False
    _lib = lib
    _state = "ready"
    return True


def _uint(fn, *args) -> Optional[int]:
    """Call an NVML getter whose last parameter is `unsigned int*`; None if unsupported."""
    v = ctypes.c_uint()
    try:
        return v.value if fn(*args, ctypes.byref(v)) == 0 else None
    except Exception:
        return None


def stats() -> List[Dict]:
    """One dict per NVIDIA GPU. Keys are omitted when a sensor is not available."""
    with _lock:
        if not _init():
            return []
        lib = _lib
        count = _uint(lib.nvmlDeviceGetCount_v2) or 0
        out: List[Dict] = []
        for i in range(count):
            dev = ctypes.c_void_p()
            if lib.nvmlDeviceGetHandleByIndex_v2(i, ctypes.byref(dev)) != 0:
                continue
            g: Dict = {"index": i, "name": f"GPU {i}"}
            buf = ctypes.create_string_buffer(96)
            if lib.nvmlDeviceGetName(dev, buf, len(buf)) == 0:
                g["name"] = buf.value.decode("utf-8", "replace")
            temp = _uint(lib.nvmlDeviceGetTemperature, dev, 0)
            if temp is not None:
                g["temp_c"] = temp
            util = _Utilization()
            if lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(util)) == 0:
                g["load_pct"] = util.gpu
            mem = _Memory()
            if lib.nvmlDeviceGetMemoryInfo(dev, ctypes.byref(mem)) == 0:
                g["vram_used"] = mem.used
                g["vram_total"] = mem.total
            power = _uint(lib.nvmlDeviceGetPowerUsage, dev)
            if power is not None:
                g["power_w"] = round(power / 1000.0, 1)
            limit = _uint(lib.nvmlDeviceGetEnforcedPowerLimit, dev)
            if limit:
                g["power_limit_w"] = round(limit / 1000.0, 1)
            fan = _uint(lib.nvmlDeviceGetFanSpeed, dev)
            if fan is not None:
                g["fan_pct"] = fan
            core = _uint(lib.nvmlDeviceGetClockInfo, dev, 0)
            if core is not None:
                g["clock_core_mhz"] = core
            memclk = _uint(lib.nvmlDeviceGetClockInfo, dev, 2)
            if memclk is not None:
                g["clock_mem_mhz"] = memclk
            out.append(g)
        return out
