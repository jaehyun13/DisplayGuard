# -*- coding: utf-8 -*-
"""
core.py — application state and logic for Spectra Display Studio.

Platform-independent: all OS access goes through a backend module
(displays_win on Windows, displays_mock elsewhere / with --demo).
"""
from __future__ import annotations

import collections
import copy
import json
import logging
import os
import threading
import time
from typing import Dict, List, Optional, Tuple

import i18n
from i18n import t

APP_NAME    = "Spectra Display Studio"
APP_ID      = "SpectraDisplayStudio"
APP_VERSION = "2.0.0"   # build.ps1 overwrites this with the release version

DEFAULT_RESTORE_DELAY   = 2.0
MAX_RESTORE_DELAY       = 60.0
# If a restore keeps failing (or what Windows applies differs from what was saved)
# we would otherwise loop "restore → change detected → restore" forever.
MAX_AUTO_RESTORE_TRIES  = 3
AUTO_RESTORE_WINDOW_SEC = 30.0
CONFIRM_SECONDS         = 15
MAX_PROFILES            = 12

log = logging.getLogger("Spectra")

_CONFIG_INT_KEYS = ("x", "y", "w", "h", "bpp", "freq", "rot")


class UserError(Exception):
    """A problem to show to the user (bad input, action not possible)."""


# ─────────────────────────────────────────────────
# Layout helpers
# ─────────────────────────────────────────────────

def configs_equal(a: List[Dict], b: List[Dict]) -> bool:
    if len(a) != len(b):
        return False
    ma, mb = {c["name"]: c for c in a}, {c["name"]: c for c in b}
    if set(ma) != set(mb):
        return False

    def same(p: Dict, q: Dict) -> bool:
        if any(p[k] != q[k] for k in ("x", "y", "w", "h", "rot", "primary")):
            return False
        # 0/1 mean "hardware default refresh rate" — not comparable.
        if p["freq"] > 1 and q["freq"] > 1 and p["freq"] != q["freq"]:
            return False
        return True
    return all(same(ma[n], mb[n]) for n in ma)


def valid_configs(configs) -> bool:
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


def normalize_origin(configs: List[Dict]) -> List[Dict]:
    """Windows requires the primary display at (0, 0)."""
    primary = next((c for c in configs if c["primary"]), configs[0])
    ox, oy = primary["x"], primary["y"]
    out = copy.deepcopy(configs)
    for c in out:
        c["x"] -= ox
        c["y"] -= oy
    return out


# ─────────────────────────────────────────────────
# Physical (real-world) layout and cursor mapping
# ─────────────────────────────────────────────────

MM_PER_INCH = 25.4


def mm_from_inches(inches: float, w: int, h: int) -> Tuple[float, float]:
    """Width/height in mm of a panel with this diagonal and pixel aspect ratio."""
    diag_px = (w * w + h * h) ** 0.5
    k = inches * MM_PER_INCH / diag_px
    return w * k, h * k


def _touch_side(a: Dict, b: Dict) -> Optional[str]:
    """Where b sits against a in the Windows (pixel) layout, if they share an edge."""
    v = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
    hz = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    if v > 0:
        if b["x"] == a["x"] + a["w"]:
            return "right"
        if b["x"] + b["w"] == a["x"]:
            return "left"
    if hz > 0:
        if b["y"] == a["y"] + a["h"]:
            return "below"
        if b["y"] + b["h"] == a["y"]:
            return "above"
    return None


def physical_layout(configs: List[Dict],
                    mm: Dict[str, Tuple[float, float]]) -> Dict[str, Tuple[float, float, float, float]]:
    """Real-world rectangles (x, y, w, h in mm) derived from the pixel layout.

    Monitors keep their neighbours; along a shared edge, the centre of the
    neighbour sits at the same *fraction* of the edge as it does in pixels. So the
    pixel layout fully determines the physical one (the UI mirrors this exactly —
    see physLayout() in ui/app.js — and inverts it when you drag in real-size view).
    """
    if not configs:
        return {}
    primary = next((c for c in configs if c["primary"]), configs[0])
    out = {primary["name"]: (0.0, 0.0, mm[primary["name"]][0], mm[primary["name"]][1])}
    queue = [primary]
    while queue:
        a = queue.pop(0)
        ax, ay, aw, ah = out[a["name"]]
        for b in configs:
            if b["name"] in out:
                continue
            side = _touch_side(a, b)
            if not side:
                continue
            bw, bh = mm[b["name"]]
            if side in ("right", "left"):
                x = ax + aw if side == "right" else ax - bw
                frac = (b["y"] + b["h"] / 2 - a["y"]) / a["h"]
                y = ay + frac * ah - bh / 2
            else:
                y = ay + ah if side == "below" else ay - bh
                frac = (b["x"] + b["w"] / 2 - a["x"]) / a["w"]
                x = ax + frac * aw - bw / 2
            out[b["name"]] = (x, y, bw, bh)
            queue.append(b)
    k = mm[primary["name"]][0] / primary["w"]
    for b in configs:          # not touching anything: keep the pixel offset, scaled
        if b["name"] not in out:
            out[b["name"]] = ((b["x"] - primary["x"]) * k, (b["y"] - primary["y"]) * k,
                              mm[b["name"]][0], mm[b["name"]][1])
    return out


class CursorMapper:
    """Decides where the cursor lands when it leaves one monitor for another, so
    that it crosses where the monitors really touch on the desk rather than where
    their pixel rectangles happen to line up.

    Each monitor is (x, y, w, h, px, py, pw, ph): pixel rect + physical rect (mm).
    """

    def __init__(self, monitors: List[Tuple], start: Tuple[int, int]):
        self.mons = [tuple(m) for m in monitors]
        self.last = start

    def _at(self, x: float, y: float):
        for m in self.mons:
            if m[0] <= x < m[0] + m[2] and m[1] <= y < m[1] + m[3]:
                return m
        return None

    def move(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        """Feed every proposed cursor position. Returns a replacement position, or
        None to let the move through unchanged."""
        a = self._at(*self.last)
        if a is None:
            if self._at(x, y):
                self.last = (x, y)
            return None
        ax, ay, aw, ah, apx, apy, apw, aph = a
        if ax <= x < ax + aw and ay <= y < ay + ah:
            self.last = (x, y)
            return None
        target = self._cross(a, x, y)
        if target is None:
            # Either Windows' own crossing is fine, or there is nothing there (a wall).
            self.last = (x, y) if self._at(x, y) else (
                max(ax, min(ax + aw - 1, x)), max(ay, min(ay + ah - 1, y)))
            return None
        self.last = target
        return target

    def _cross(self, a, x: int, y: int) -> Optional[Tuple[int, int]]:
        ax, ay, aw, ah, apx, apy, apw, aph = a
        over_x = x - (ax + aw - 1) if x >= ax + aw else (x - ax if x < ax else 0)
        over_y = y - (ay + ah - 1) if y >= ay + ah else (y - ay if y < ay else 0)
        cx = max(ax, min(ax + aw - 1, x))
        cy = max(ay, min(ay + ah - 1, y))
        ppx = apx + (cx - ax + 0.5) / aw * apw
        ppy = apy + (cy - ay + 0.5) / ah * aph
        natural = self._at(x, y)
        horizontal = abs(over_x) >= abs(over_y)
        if horizontal:
            right = over_x > 0
            edge = apx + apw if right else apx
            cands = [b for b in self.mons if b is not a
                     and abs((b[4] if right else b[4] + b[6]) - edge) < 1.0]
            b = next((m for m in cands if m[5] <= ppy < m[5] + m[7]), None)
        else:
            down = over_y > 0
            edge = apy + aph if down else apy
            cands = [b for b in self.mons if b is not a
                     and abs((b[5] if down else b[5] + b[7]) - edge) < 1.0]
            b = next((m for m in cands if m[4] <= ppx < m[4] + m[6]), None)
        if b is None:
            if natural is None or natural not in cands:
                return None
            b = natural       # Windows lets it through here: enter at the nearest point
        bx, by, bw, bh, bpx, bpy, bpw, bph = b
        if horizontal:
            tx = bx if over_x > 0 else bx + bw - 1
            ty = max(by, min(by + bh - 1, by + int((ppy - bpy) / bph * bh)))
            if natural is b and abs(ty - y) <= 1:
                return None
        else:
            ty = by if over_y > 0 else by + bh - 1
            tx = max(bx, min(bx + bw - 1, bx + int((ppx - bpx) / bpw * bw)))
            if natural is b and abs(tx - x) <= 1:
                return None
        return tx, ty


def short_name(device_name: str) -> str:
    return device_name.replace("\\\\.\\", "")


# ─────────────────────────────────────────────────
# Colour correction
# ─────────────────────────────────────────────────

COLOR_DEFAULT = {"r": 100, "g": 100, "b": 100, "gamma": 100, "brightness": 0, "contrast": 100}
COLOR_LIMITS  = {"r": (80, 120), "g": (80, 120), "b": (80, 120),
                 "gamma": (60, 160), "brightness": (-20, 20), "contrast": (70, 130)}


def clean_color(raw) -> Dict[str, int]:
    out = dict(COLOR_DEFAULT)
    if isinstance(raw, dict):
        for k, (lo, hi) in COLOR_LIMITS.items():
            v = raw.get(k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = int(max(lo, min(hi, round(v))))
    return out


def build_gamma_ramp(s: Dict[str, int]) -> List[List[int]]:
    """Per-channel 256-entry lookup table from the colour settings."""
    gamma = s["gamma"] / 100.0
    contrast = s["contrast"] / 100.0
    brightness = s["brightness"] / 100.0
    ramp = []
    for ch in ("r", "g", "b"):
        gain = s[ch] / 100.0
        row = []
        for i in range(256):
            v = (i / 255.0) ** (1.0 / gamma)
            v = (v - 0.5) * contrast + 0.5 + brightness
            v = max(0.0, min(1.0, v * gain))
            row.append(int(round(v * 65535)))
        ramp.append(row)
    return ramp


# ─────────────────────────────────────────────────
# Zones
# ─────────────────────────────────────────────────

# Each preset is a list of (x, y, w, h) fractions of the monitor's work area.
ZONE_PRESETS: Dict[str, List[Tuple[float, float, float, float]]] = {
    "full":   [(0, 0, 1, 1)],
    "cols2":  [(0, 0, .5, 1), (.5, 0, .5, 1)],
    "cols3":  [(0, 0, .25, 1), (.25, 0, .5, 1), (.75, 0, .25, 1)],
    "focus":  [(0, 0, 1 / 6, 1), (1 / 6, 0, 2 / 3, 1), (5 / 6, 0, 1 / 6, 1)],
    "main70": [(0, 0, .7, 1), (.7, 0, .3, 1)],
    "quad":   [(0, 0, .5, .5), (.5, 0, .5, .5), (0, .5, .5, .5), (.5, .5, .5, .5)],
    "rows2":  [(0, 0, 1, .5), (0, .5, 1, .5)],
    "rows3":  [(0, 0, 1, 1 / 3), (0, 1 / 3, 1, 1 / 3), (0, 2 / 3, 1, 1 / 3)],
}
ZONE_DEFAULT = {"enabled": True, "shift_snap": True, "padding": 8, "layouts": {}}


def zone_rects(work: Tuple[int, int, int, int], preset: str,
               padding: int) -> List[Tuple[int, int, int, int]]:
    """Pixel rectangles (l, t, r, b) for a preset inside a work area."""
    l, t, r, b = work
    w, h = r - l, b - t
    half = padding / 2.0
    rects = []
    for fx, fy, fw, fh in ZONE_PRESETS.get(preset, ZONE_PRESETS["full"]):
        x1 = l + fx * w + (padding if fx == 0 else half)
        y1 = t + fy * h + (padding if fy == 0 else half)
        x2 = l + (fx + fw) * w - (padding if fx + fw >= 0.999 else half)
        y2 = t + (fy + fh) * h - (padding if fy + fh >= 0.999 else half)
        rects.append((int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))))
    return rects


def default_zone_preset(w: int, h: int) -> str:
    if h > w:
        return "rows2"
    return "cols3" if w >= 3000 else "cols2"


VK_LEFT, VK_UP, VK_RIGHT, VK_SHIFT = 0x25, 0x26, 0x27, 0x10


# ─────────────────────────────────────────────────
# The application
# ─────────────────────────────────────────────────

class Studio:
    def __init__(self, backend, data_dir: str):
        self.b = backend
        self.data_dir = data_dir
        self.config_file = os.path.join(data_dir, "spectra_config.json")
        self._legacy_config = os.path.join(data_dir, "display_guard_config.json")

        self.saved: Optional[List[Dict]] = None
        self.enabled = True
        self.restore_delay = DEFAULT_RESTORE_DELAY
        self.language: Optional[str] = None
        self.profiles: List[Dict] = []
        self.color: Dict[str, Dict[str, int]] = {}
        self.zones: Dict = copy.deepcopy(ZONE_DEFAULT)
        self.sizes: Dict[str, float] = {}      # user-entered diagonal (inches) per display
        self.mouse_map = False

        self._lock = threading.RLock()
        self._timer: Optional[threading.Timer] = None
        self._tries = 0
        self._last_try = 0.0
        self._gave_up = False
        self._pending: Optional[Dict] = None
        self._log: collections.deque = collections.deque(maxlen=200)
        self._log_seq = 0
        self.on_change = None            # callback(): tray refresh etc.
        self.loop = None

        self._load()

    # ── persistence ───────────────────────────────

    def _load(self) -> None:
        path = self.config_file if os.path.exists(self.config_file) else self._legacy_config
        if not os.path.exists(path):
            return
        try:
            # utf-8-sig tolerates a BOM (e.g. the file was edited in Notepad).
            with open(path, encoding="utf-8-sig") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("config root is not an object")
        except Exception as e:
            self.log(t("log_config_load_failed", error=e))
            return
        configs = data.get("configs")
        self.saved = configs if valid_configs(configs) else None
        delay = data.get("delay", DEFAULT_RESTORE_DELAY)
        if (isinstance(delay, (int, float)) and not isinstance(delay, bool)
                and 0 <= delay <= MAX_RESTORE_DELAY):
            self.restore_delay = float(delay)
        if isinstance(data.get("enabled"), bool):
            self.enabled = data["enabled"]
        lang = data.get("language")
        self.language = lang if lang in i18n.LANGUAGES else None
        profiles = data.get("profiles")
        for p in profiles if isinstance(profiles, list) else []:
            if (isinstance(p, dict) and isinstance(p.get("name"), str) and p["name"].strip()
                    and valid_configs(p.get("configs")) and len(self.profiles) < MAX_PROFILES):
                self.profiles.append({"name": p["name"].strip()[:40],
                                      "configs": p["configs"]})
        if isinstance(data.get("color"), dict):
            for name, raw in data["color"].items():
                if isinstance(name, str):
                    self.color[name] = clean_color(raw)
        z = data.get("zones")
        if isinstance(z, dict):
            self._merge_zones(z)
        if isinstance(data.get("sizes"), dict):
            for name, inches in data["sizes"].items():
                if (isinstance(name, str) and isinstance(inches, (int, float))
                        and not isinstance(inches, bool) and 5 <= inches <= 200):
                    self.sizes[name] = float(inches)
        if isinstance(data.get("mouse_map"), bool):
            self.mouse_map = data["mouse_map"]

    def _persist(self) -> None:
        # Write to a temp file and swap, so a crash mid-write cannot corrupt settings.
        tmp = self.config_file + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"configs": self.saved, "delay": self.restore_delay,
                           "enabled": self.enabled, "language": self.language,
                           "profiles": self.profiles, "color": self.color,
                           "zones": self.zones, "sizes": self.sizes,
                           "mouse_map": self.mouse_map},
                          f, indent=2, ensure_ascii=False)
            os.replace(tmp, self.config_file)
        except Exception as e:
            try:
                os.remove(tmp)
            except OSError:
                pass
            self.log(t("log_config_save_failed", error=e))

    # ── log ───────────────────────────────────────

    def log(self, msg: str) -> None:
        log.info(msg)
        with self._lock:
            self._log_seq += 1
            self._log.append({"seq": self._log_seq, "time": time.strftime("%H:%M:%S"),
                              "text": msg})

    def _changed(self) -> None:
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                log.exception("on_change callback failed")

    # ── startup ───────────────────────────────────

    def start(self) -> None:
        """Called once after construction: first-run save, colour, hotkeys."""
        current = self.b.get_display_configs()
        if not self.saved and current:
            self.log(t("log_no_saved_autosave"))
            self.saved = current
            self._persist()
        self.log(t("app_started", version=APP_VERSION, count=len(current)))
        self.apply_all_color(quiet=True)
        self.loop = self.b.EventLoop(self.on_display_change, self.on_hotkey,
                                     self.on_window_dropped)
        self.loop.start()
        self._sync_hotkeys()
        self._refresh_mouse_map()

    def _after_layout_change(self) -> None:
        """Things that must follow any change of the display layout."""
        try:
            self.apply_all_color(quiet=True)   # Windows resets gamma ramps on mode changes
            self._refresh_mouse_map()
        except Exception:
            log.exception("post-layout refresh failed")

    # ── layout protection ─────────────────────────

    def _reset_tries(self) -> None:
        self._tries = 0
        self._gave_up = False

    def snapshot(self) -> None:
        configs = self.b.get_display_configs()
        if not configs:
            raise UserError(t("log_no_saved"))
        with self._lock:
            self.saved = configs
            self._reset_tries()
        self._persist()
        self.log(t("log_saved", count=len(configs)))
        self._changed()

    def restore_now(self) -> bool:
        with self._lock:
            saved = self.saved
            self._reset_tries()
        if not saved:
            raise UserError(t("log_no_saved"))
        self.log(t("log_restore_manual"))
        ok = self.b.apply_display_configs(saved)
        self.log(t("log_restore_done") if ok else t("log_restore_error"))
        self._after_layout_change()
        self._changed()
        return ok

    def set_enabled(self, enabled: bool) -> None:
        with self._lock:
            if enabled == self.enabled:
                return
            self.enabled = enabled
            if not enabled and self._timer:
                self._timer.cancel()     # also drop a restore that was pending
                self._timer = None
        self._persist()
        self.log(t("log_protection_on") if enabled else t("log_protection_off"))
        self._changed()

    def set_delay(self, delay: float) -> None:
        if not (0 <= delay <= MAX_RESTORE_DELAY):
            raise UserError("delay out of range")
        self.restore_delay = float(delay)
        self._persist()

    def on_display_change(self) -> None:
        with self._lock:
            follow_up = threading.Timer(1.0, self._after_layout_change)
            follow_up.daemon = True
            follow_up.start()
            if not self.enabled or self._pending:
                return
            if self._timer:
                self._timer.cancel()
            timer = threading.Timer(self.restore_delay, self._do_restore)
            timer.daemon = True
            self._timer = timer
        timer.start()
        self.log(t("log_change_detected", delay=self.restore_delay))

    def _do_restore(self) -> None:
        try:
            self._do_restore_inner()
        except Exception as e:   # never let the timer thread die silently
            log.exception("auto-restore failed: %s", e)

    def _do_restore_inner(self) -> None:
        with self._lock:
            saved = self.saved
            if not saved or not self.enabled or self._pending:
                return
        current = self.b.get_display_configs()
        if configs_equal(saved, current):
            with self._lock:
                self._reset_tries()
            self.log(t("log_config_equal"))
            self._after_layout_change()
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
                self.log(t("log_restore_giveup", count=MAX_AUTO_RESTORE_TRIES))
            return
        ok = self.b.apply_display_configs(saved)
        self.log(t("log_auto_restore_done") if ok else t("log_auto_restore_error"))
        self._after_layout_change()
        self._changed()

    # ── applying a layout from the UI ─────────────

    def _validate_target(self, configs, current: List[Dict]) -> Tuple[List[Dict], bool]:
        """Returns (clean target, needs_confirmation). Raises UserError."""
        if not isinstance(configs, list):
            raise UserError("invalid layout")
        cur = {c["name"]: c for c in current}
        if len(configs) != len(cur):
            raise UserError(t("err_layout_mismatch"))
        target, risky = [], False
        for raw in configs:
            if not isinstance(raw, dict) or raw.get("name") not in cur:
                raise UserError(t("err_layout_mismatch"))
            base = cur[raw["name"]]
            c = dict(base)
            for k in ("x", "y", "w", "h", "freq", "rot"):
                v = raw.get(k, base[k])
                if not isinstance(v, int) or isinstance(v, bool):
                    raise UserError("invalid layout")
                c[k] = v
            c["primary"] = bool(raw.get("primary", base["primary"]))
            if c["rot"] not in (0, 1, 2, 3) or abs(c["x"]) > 100000 or abs(c["y"]) > 100000:
                raise UserError("invalid layout")
            if (c["w"], c["h"], c["freq"], c["rot"]) != (base["w"], base["h"],
                                                         base["freq"], base["rot"]):
                risky = True
                # Only accept modes the driver actually advertises.
                modes = self.b.list_modes(c["name"])
                turned = (c["rot"] in (1, 3)) != (base["rot"] in (1, 3))
                mw, mh = (c["h"], c["w"]) if turned else (c["w"], c["h"])
                if not any(m["w"] == mw and m["h"] == mh
                           and (c["freq"] <= 1 or m["freq"] == c["freq"]) for m in modes):
                    raise UserError(t("err_mode_unsupported"))
            target.append(c)
        if len({c["name"] for c in target}) != len(target):
            raise UserError(t("err_layout_mismatch"))
        if sum(1 for c in target if c["primary"]) != 1:
            raise UserError(t("err_one_primary"))
        return normalize_origin(target), risky

    def apply_layout(self, configs) -> Dict:
        with self._lock:
            if self._pending:
                raise UserError(t("err_pending"))
        current = self.b.get_display_configs()
        target, risky = self._validate_target(configs, current)
        with self._lock:
            prev_saved = self.saved
            self.saved = target          # so the guard does not fight the change
            self._reset_tries()
            if risky:
                self._pending = {"prev": current, "prev_saved": prev_saved,
                                 "deadline": time.monotonic() + CONFIRM_SECONDS}
        ok = self.b.apply_display_configs(target)
        if not ok:
            self.b.apply_display_configs(current)
            with self._lock:
                self.saved = prev_saved
                self._pending = None
            self.log(t("log_restore_error"))
            raise UserError(t("err_apply_failed"))
        actual = self.b.get_display_configs() or target
        with self._lock:
            # Windows may adjust positions (e.g. close gaps); protect what it really set.
            self.saved = actual
            if risky:
                timer = threading.Timer(CONFIRM_SECONDS, self.revert_layout,
                                        kwargs={"auto": True})
                timer.daemon = True
                self._pending["timer"] = timer
                timer.start()
        if risky:
            self.log(t("log_layout_pending", seconds=CONFIRM_SECONDS))
        else:
            self._persist()
            self.log(t("log_layout_applied"))
        self._after_layout_change()
        self._changed()
        return {"pending": risky}

    def confirm_layout(self) -> None:
        with self._lock:
            p, self._pending = self._pending, None
        if not p:
            return
        if p.get("timer"):
            p["timer"].cancel()
        with self._lock:
            self.saved = self.b.get_display_configs() or self.saved
        self._persist()
        self.log(t("log_layout_applied"))
        self._after_layout_change()
        self._changed()

    def revert_layout(self, auto: bool = False) -> None:
        with self._lock:
            p, self._pending = self._pending, None
        if not p:
            return
        if p.get("timer") and not auto:
            p["timer"].cancel()
        with self._lock:
            self.saved = p["prev_saved"]
            self._reset_tries()
        self.b.apply_display_configs(p["prev"])
        self.log(t("log_layout_reverted"))
        self._after_layout_change()
        self._changed()

    def identify(self) -> None:
        numbered = [(str(i), (c["x"], c["y"], c["w"], c["h"]))
                    for i, c in enumerate(self._ordered(self.b.get_display_configs()), 1)]
        self.b.identify(numbered)

    @staticmethod
    def _ordered(configs: List[Dict]) -> List[Dict]:
        """Stable numbering: by the trailing number in the device name."""
        def key(c):
            digits = "".join(ch for ch in c["name"] if ch.isdigit())
            return (int(digits) if digits else 0, c["name"])
        return sorted(configs, key=key)

    # ── profiles ──────────────────────────────────

    def save_profile(self, name) -> None:
        if not isinstance(name, str) or not name.strip():
            raise UserError(t("err_profile_name"))
        name = name.strip()[:40]
        configs = self.b.get_display_configs()
        if not configs:
            raise UserError(t("log_no_saved"))
        with self._lock:
            existing = next((p for p in self.profiles if p["name"] == name), None)
            if existing:
                existing["configs"] = configs
            elif len(self.profiles) >= MAX_PROFILES:
                raise UserError(t("err_profile_limit", count=MAX_PROFILES))
            else:
                self.profiles.append({"name": name, "configs": configs})
        self._persist()
        self.log(t("log_profile_saved", name=name))
        self._changed()

    def delete_profile(self, name) -> None:
        with self._lock:
            self.profiles = [p for p in self.profiles if p["name"] != name]
        self._persist()
        self._changed()

    def apply_profile(self, name) -> Dict:
        with self._lock:
            profile = next((p for p in self.profiles if p["name"] == name), None)
        if not profile:
            raise UserError(t("err_profile_missing"))
        result = self.apply_layout(profile["configs"])
        self.log(t("log_profile_applied", name=profile["name"]))
        return result

    # ── colour ────────────────────────────────────

    def set_color(self, name, settings) -> None:
        if name not in {c["name"] for c in self.b.get_display_configs()}:
            raise UserError(t("err_layout_mismatch"))
        clean = clean_color(settings)
        ok = self.b.set_gamma_ramp(name, build_gamma_ramp(clean))
        if not ok:
            raise UserError(t("err_color_rejected"))
        with self._lock:
            if clean == COLOR_DEFAULT:
                self.color.pop(name, None)
            else:
                self.color[name] = clean
        self._persist()

    def apply_all_color(self, quiet: bool = False) -> None:
        with self._lock:
            items = list(self.color.items())
        if not items:
            return
        active = {c["name"] for c in self.b.get_display_configs()}
        for name, settings in items:
            if name in active:
                try:
                    self.b.set_gamma_ramp(name, build_gamma_ramp(settings))
                except Exception:
                    if not quiet:
                        raise

    def set_hdr(self, name, enabled) -> None:
        if not self.b.set_hdr(name, bool(enabled)):
            raise UserError(t("err_hdr_failed"))
        self.log(t("log_hdr_on" if enabled else "log_hdr_off", name=short_name(str(name))))

    def ddc_get(self, name):
        return self.b.ddc_get(name)

    def ddc_set(self, name, key, value) -> None:
        if key not in ("brightness", "contrast") or not isinstance(value, (int, float)):
            raise UserError("invalid request")
        if not self.b.ddc_set(name, key, int(value)):
            raise UserError(t("err_ddc_failed"))

    # ── physical size and cursor mapping ──────────

    def _mm(self, c: Dict, details: Dict) -> Tuple[float, float, str]:
        """(width mm, height mm, source) for a display in its current orientation."""
        w, h = c["w"], c["h"]
        if c["name"] in self.sizes:
            mw, mh = mm_from_inches(self.sizes[c["name"]], w, h)
            return mw, mh, "user"
        mm = details.get(c["name"], {}).get("mm")
        if mm and mm[0] > 10 and mm[1] > 10:
            mw, mh = float(mm[0]), float(mm[1])
            if (mw > mh) != (w > h):          # reported for the unrotated panel
                mw, mh = mh, mw
            return mw, mh, "edid"
        scale = details.get(c["name"], {}).get("scale") or 100
        k = MM_PER_INCH / (96.0 * scale / 100.0)
        return w * k, h * k, "guess"

    def set_physical_size(self, name, inches) -> None:
        if name not in {c["name"] for c in self.b.get_display_configs()}:
            raise UserError(t("err_layout_mismatch"))
        with self._lock:
            if inches is None:
                self.sizes.pop(name, None)
            elif (isinstance(inches, (int, float)) and not isinstance(inches, bool)
                  and 5 <= inches <= 200):
                self.sizes[name] = round(float(inches), 1)
            else:
                raise UserError(t("err_size_range"))
        self._persist()
        self._refresh_mouse_map()

    def set_mouse_map(self, enabled: bool) -> None:
        self.mouse_map = bool(enabled)
        self._persist()
        self._refresh_mouse_map()
        self.log(t("log_mouse_map_on") if self.mouse_map else t("log_mouse_map_off"))

    def build_cursor_mapper(self) -> Optional[CursorMapper]:
        configs = self.b.get_display_configs()
        if len(configs) < 2:
            return None
        details = self.b.get_monitor_details()
        mm = {c["name"]: self._mm(c, details)[:2] for c in configs}
        phys = physical_layout(configs, mm)
        mons = [(c["x"], c["y"], c["w"], c["h"]) + tuple(phys[c["name"]]) for c in configs]
        return CursorMapper(mons, self.b.cursor_pos())

    def _refresh_mouse_map(self) -> None:
        if not self.loop:
            return
        mapper = self.build_cursor_mapper() if self.mouse_map else None
        self.loop.set_cursor_mapper(mapper.move if mapper else None)

    # ── zones ─────────────────────────────────────

    def _merge_zones(self, z: Dict) -> None:
        if isinstance(z.get("enabled"), bool):
            self.zones["enabled"] = z["enabled"]
        if isinstance(z.get("shift_snap"), bool):
            self.zones["shift_snap"] = z["shift_snap"]
        pad = z.get("padding")
        if isinstance(pad, (int, float)) and not isinstance(pad, bool) and 0 <= pad <= 32:
            self.zones["padding"] = int(pad)
        if isinstance(z.get("layouts"), dict):
            for name, preset in z["layouts"].items():
                if isinstance(name, str) and preset in ZONE_PRESETS:
                    self.zones["layouts"][name] = preset

    def set_zones(self, patch) -> None:
        if not isinstance(patch, dict):
            raise UserError("invalid request")
        with self._lock:
            self._merge_zones(patch)
        self._persist()
        self._sync_hotkeys()

    def _preset_for(self, c: Dict) -> str:
        return self.zones["layouts"].get(c["name"]) or default_zone_preset(c["w"], c["h"])

    def _all_zones(self) -> List[Tuple[int, int, int, int]]:
        """Every zone on every monitor, left-to-right then top-to-bottom."""
        details = self.b.get_monitor_details()
        out = []
        for c in sorted(self.b.get_display_configs(), key=lambda c: (c["x"], c["y"])):
            work = details.get(c["name"], {}).get("work") or \
                [c["x"], c["y"], c["x"] + c["w"], c["y"] + c["h"]]
            out.extend(zone_rects(tuple(work), self._preset_for(c), self.zones["padding"]))
        return out

    def _sync_hotkeys(self) -> None:
        if not self.loop:
            return
        b = self.b
        keys: Dict[str, Tuple[int, int]] = {}
        if self.zones["enabled"]:
            mods = b.MOD_WIN | b.MOD_ALT
            keys = {"zone_prev": (mods, VK_LEFT), "zone_next": (mods, VK_RIGHT),
                    "zone_fill": (mods, VK_UP)}
            for i in range(1, 4):
                keys[f"profile_{i}"] = (mods, 0x30 + i)
        self.loop.set_hotkeys(keys)

    def on_hotkey(self, action: str) -> None:
        if action.startswith("profile_"):
            idx = int(action.split("_")[1]) - 1
            with self._lock:
                name = self.profiles[idx]["name"] if idx < len(self.profiles) else None
            if name:
                try:
                    self.apply_profile(name)
                except UserError as e:
                    self.log(str(e))
            return
        hwnd = self.b.foreground_window()
        rect = self.b.window_rect(hwnd) if hwnd else None
        if not rect:
            return
        cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
        if action == "zone_fill":
            details = self.b.get_monitor_details()
            for c in self.b.get_display_configs():
                if c["x"] <= cx < c["x"] + c["w"] and c["y"] <= cy < c["y"] + c["h"]:
                    work = details.get(c["name"], {}).get("work")
                    if work:
                        self.b.move_window(hwnd, zone_rects(tuple(work), "full",
                                                            self.zones["padding"])[0])
            return
        zones = self._all_zones()
        if not zones:
            return
        # The zone whose centre is nearest to the window's centre is "where it is".
        cur = min(range(len(zones)), key=lambda i: (
            ((zones[i][0] + zones[i][2]) // 2 - cx) ** 2
            + ((zones[i][1] + zones[i][3]) // 2 - cy) ** 2))
        step = 1 if action == "zone_next" else -1
        self.b.move_window(hwnd, zones[(cur + step) % len(zones)])

    def on_window_dropped(self, hwnd: int) -> None:
        """A window drag just ended; with Shift held, snap it to the zone under the cursor."""
        if not (self.zones["enabled"] and self.zones["shift_snap"]):
            return
        if not self.b.is_key_down(VK_SHIFT):
            return
        x, y = self.b.cursor_pos()
        for z in self._all_zones():
            if z[0] <= x < z[2] and z[1] <= y < z[3]:
                self.b.move_window(hwnd, z)
                return

    def tile_windows(self) -> int:
        """Put the open windows of each monitor into that monitor's zones."""
        details = self.b.get_monitor_details()
        windows = self.b.list_app_windows()
        moved = 0
        for c in self.b.get_display_configs():
            work = details.get(c["name"], {}).get("work")
            if not work:
                continue
            zones = zone_rects(tuple(work), self._preset_for(c), self.zones["padding"])
            here = []
            for hwnd in windows:
                r = self.b.window_rect(hwnd)
                if not r:
                    continue
                cx, cy = (r[0] + r[2]) // 2, (r[1] + r[3]) // 2
                if c["x"] <= cx < c["x"] + c["w"] and c["y"] <= cy < c["y"] + c["h"]:
                    here.append(hwnd)
            for hwnd, zone in zip(here, zones):
                if self.b.move_window(hwnd, zone):
                    moved += 1
        self.log(t("log_tiled", count=moved))
        return moved

    # ── settings ──────────────────────────────────

    def set_language(self, code) -> None:
        if code not in i18n.LANGUAGES:
            raise UserError("unknown language")
        self.language = code
        i18n.set_language(code)
        self._persist()
        self.log(t("lang_changed", lang=i18n.language_name(code)))
        self._changed()

    # ── state for the UI ──────────────────────────

    def monitors(self) -> List[Dict]:
        details = self.b.get_monitor_details()
        out = []
        for i, c in enumerate(self._ordered(self.b.get_display_configs()), 1):
            d = details.get(c["name"], {})
            m = dict(c)
            m["number"] = i
            m["short"] = short_name(c["name"])
            m["label"] = d.get("label") or short_name(c["name"])
            for k in ("adapter", "connector", "edid", "bits_per_channel", "scale", "hdr", "work"):
                if k in d:
                    m[k] = d[k]
            mw, mh, source = self._mm(c, details)
            m["mm"] = [round(mw, 1), round(mh, 1)]
            m["mm_source"] = source
            m["inches"] = round((mw * mw + mh * mh) ** 0.5 / MM_PER_INCH, 1)
            m["color"] = self.color.get(c["name"], dict(COLOR_DEFAULT))
            m["zone_preset"] = self._preset_for(c)
            out.append(m)
        return out

    def state(self, since: int = 0) -> Dict:
        monitors = self.monitors()
        current = [{k: m[k] for k in ("name", "primary", "x", "y", "w", "h", "bpp", "freq", "rot")}
                   for m in monitors]
        with self._lock:
            saved = copy.deepcopy(self.saved)
            pending = None
            if self._pending:
                pending = {"seconds_left": max(0, int(round(
                    self._pending["deadline"] - time.monotonic())))}
            logs = [e for e in self._log if e["seq"] > since]
            profiles = [{"name": p["name"], "count": len(p["configs"]),
                         "active": configs_equal(p["configs"], current)}
                        for p in self.profiles]
        return {
            "app": {"name": APP_NAME, "version": APP_VERSION,
                    "demo": bool(getattr(self.b, "IS_DEMO", False)),
                    "language": i18n.get_language(),
                    "languages": i18n.LANGUAGES},
            "guard": {"enabled": self.enabled, "delay": self.restore_delay,
                      "has_saved": bool(saved),
                      "match": bool(saved) and configs_equal(saved, current),
                      "pending": pending},
            "monitors": monitors,
            "mouse": {"enabled": self.mouse_map},
            "saved": saved or [],
            "profiles": profiles,
            "zones": {**self.zones, "presets": {k: [list(z) for z in v]
                                                for k, v in ZONE_PRESETS.items()},
                      "hotkeys_failed": list(self.loop.failed) if self.loop else []},
            "log": logs,
        }

    def hardware(self, with_ddc: bool = False) -> Dict:
        info = self.b.system_info()
        monitors = self.monitors()
        if with_ddc:
            for m in monitors:
                try:
                    m["ddc"] = self.b.ddc_get(m["name"])
                except Exception:
                    m["ddc"] = None
        info["monitors"] = monitors
        info["app"] = {"name": APP_NAME, "version": APP_VERSION}
        info["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return info
