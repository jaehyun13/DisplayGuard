# -*- coding: utf-8 -*-
"""
server.py — the local HTTP server behind the Spectra Display Studio window.

It only listens on 127.0.0.1, and every API call must carry the per-launch token
(handed to the window in its URL) plus a matching Host header, so other programs
or web pages on the machine cannot drive the display settings through it.
"""
from __future__ import annotations

import hmac
import json
import logging
import mimetypes
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse

from core import Studio, UserError

log = logging.getLogger("Spectra")

MAX_BODY = 256 * 1024
_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
          ".js": "text/javascript; charset=utf-8", ".woff2": "font/woff2",
          ".ico": "image/x-icon", ".svg": "image/svg+xml", ".txt": "text/plain; charset=utf-8"}


def format_report(info: Dict) -> str:
    """Plain-text hardware report (what the 'export' button downloads)."""
    lines = [f"{info['app']['name']} {info['app']['version']} — hardware report",
             f"Generated: {info['generated']}", f"OS: {info.get('os', '')}", ""]
    lines.append("Graphics adapters")
    for a in info.get("adapters", []):
        lines.append(f"  - {a.get('name', '?')}")
        if a.get("driver_version"):
            lines.append(f"      driver:  {a['driver_version']} {a.get('driver_date', '')}".rstrip())
        if a.get("vram"):
            lines.append(f"      memory:  {a['vram'] / 1024 ** 3:.1f} GB")
    lines += ["", "Displays"]
    for m in info.get("monitors", []):
        lines.append(f"  {m['number']}. {m['label']} ({m['short']})"
                     + ("  [primary]" if m["primary"] else ""))
        lines.append(f"      mode:      {m['w']} x {m['h']} @ {m['freq']} Hz, "
                     f"{m['bpp']}-bit desktop, rotation {m['rot'] * 90} deg")
        lines.append(f"      position:  ({m['x']}, {m['y']})")
        for label, key in (("connector", "connector"), ("EDID id", "edid"),
                           ("adapter", "adapter")):
            if m.get(key):
                lines.append(f"      {label + ':':<10} {m[key]}")
        if m.get("bits_per_channel"):
            lines.append(f"      colour:    {m['bits_per_channel']} bits per channel")
        if m.get("scale"):
            lines.append(f"      scaling:   {m['scale']}%")
        if "hdr" in m:
            hdr = m["hdr"]
            state = ("on" if hdr["enabled"] else "off") if hdr["supported"] else "not supported"
            lines.append(f"      HDR:       {state}")
        if "ddc" in m:
            ddc = m["ddc"]
            if ddc:
                parts = [f"{k} {v['cur']}/{v['max']}" for k, v in ddc.items()]
                lines.append(f"      DDC/CI:    responding ({', '.join(parts)})")
            else:
                lines.append("      DDC/CI:    no response")
    return "\n".join(lines) + "\n"


class AppServer:
    def __init__(self, studio: Studio, ui_dir: str, port: int = 0,
                 token: Optional[str] = None,
                 settings_get: Optional[Callable[[], Dict]] = None,
                 settings_set: Optional[Callable[[Dict], None]] = None):
        self.studio = studio
        self.ui_dir = os.path.realpath(ui_dir)
        self.token = token or secrets.token_urlsafe(24)
        self.settings_get = settings_get or (lambda: {})
        self.settings_set = settings_set or (lambda patch: None)
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, fmt, *args):   # keep the console/log quiet
                pass

            # ── helpers ──
            def _send(self, code: int, body: bytes, ctype: str, extra: Optional[Dict] = None):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                for k, v in (extra or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _json(self, code: int, obj):
                self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                           "application/json; charset=utf-8")

            def _host_ok(self) -> bool:
                host = (self.headers.get("Host") or "").lower()
                port = outer.port
                return host in (f"127.0.0.1:{port}", f"localhost:{port}")

            def _authorized(self) -> bool:
                given = self.headers.get("X-Spectra-Token") or ""
                return hmac.compare_digest(given, outer.token)

            def _body(self) -> Dict:
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    raise UserError("bad request")
                if length > MAX_BODY:
                    raise UserError("request too large")
                if length == 0:
                    return {}
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                except Exception:
                    raise UserError("bad request")
                if not isinstance(data, dict):
                    raise UserError("bad request")
                return data

            def _static(self, path: str):
                rel = "index.html" if path in ("", "/") else path.lstrip("/")
                full = os.path.realpath(os.path.join(outer.ui_dir, rel))
                if not (full == outer.ui_dir or full.startswith(outer.ui_dir + os.sep)) \
                        or not os.path.isfile(full):
                    return self._send(404, b"not found", "text/plain")
                ext = os.path.splitext(full)[1].lower()
                ctype = _TYPES.get(ext) or mimetypes.guess_type(full)[0] \
                    or "application/octet-stream"
                with open(full, "rb") as f:
                    self._send(200, f.read(), ctype)

            def _api(self, method: str, path: str, query: Dict):
                if not self._authorized():
                    return self._json(403, {"error": "forbidden"})
                try:
                    result = outer._dispatch(method, path, query,
                                             self._body() if method == "POST" else {})
                except UserError as e:
                    return self._json(400, {"error": str(e)})
                except Exception as e:
                    log.exception("API %s %s failed", method, path)
                    return self._json(500, {"error": f"{type(e).__name__}: {e}"})
                if isinstance(result, tuple):      # (bytes, content-type, filename)
                    body, ctype, filename = result
                    return self._send(200, body, ctype, {
                        "Content-Disposition": f'attachment; filename="{filename}"'})
                self._json(200, result if result is not None else {"ok": True})

            def _handle(self, method: str):
                if not self._host_ok():
                    return self._send(403, b"forbidden", "text/plain")
                url = urlparse(self.path)
                if url.path.startswith("/api/"):
                    query = {k: v[0] for k, v in parse_qs(url.query).items()}
                    return self._api(method, url.path[5:], query)
                if method != "GET":
                    return self._send(405, b"method not allowed", "text/plain")
                self._static(url.path)

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/#t={self.token}"

    def start(self) -> None:
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="HTTP").start()

    def stop(self) -> None:
        try:
            self.httpd.shutdown()
        except Exception:
            pass

    # ── routes ────────────────────────────────────

    def _state(self, query: Dict) -> Dict:
        try:
            since = int(query.get("since", 0))
        except ValueError:
            since = 0
        state = self.studio.state(since)
        state["settings"] = self.settings_get()
        return state

    def _dispatch(self, method: str, path: str, q: Dict, body: Dict):
        s = self.studio
        if method == "GET":
            if path == "state":
                return self._state(q)
            if path == "modes":
                return {"modes": s.b.list_modes(q.get("name", ""))}
            if path == "hardware":
                return s.hardware(with_ddc=q.get("ddc") == "1")
            if path == "gpu":
                return {"gpus": s.b.gpu_stats()}
            if path == "ddc":
                return {"ddc": s.ddc_get(q.get("name", ""))}
            if path == "report":
                text = format_report(s.hardware(with_ddc=True))
                return (text.encode("utf-8"), "text/plain; charset=utf-8",
                        "spectra-hardware-report.txt")
            raise UserError("unknown endpoint")

        if path == "guard":
            if "enabled" in body:
                s.set_enabled(bool(body["enabled"]))
            if "delay" in body:
                if not isinstance(body["delay"], (int, float)) or isinstance(body["delay"], bool):
                    raise UserError("bad request")
                s.set_delay(body["delay"])
        elif path == "snapshot":
            s.snapshot()
        elif path == "restore":
            s.restore_now()
        elif path == "layout":
            s.apply_layout(body.get("configs"))
        elif path == "layout/confirm":
            s.confirm_layout()
        elif path == "layout/revert":
            s.revert_layout()
        elif path == "identify":
            s.identify()
        elif path == "profiles":
            action = body.get("action")
            if action == "save":
                s.save_profile(body.get("name"))
            elif action == "delete":
                s.delete_profile(body.get("name"))
            elif action == "apply":
                s.apply_profile(body.get("name"))
            else:
                raise UserError("bad request")
        elif path == "color":
            s.set_color(body.get("name"), body.get("settings"))
        elif path == "hdr":
            s.set_hdr(body.get("name"), body.get("enabled"))
        elif path == "ddc":
            s.ddc_set(body.get("name"), body.get("key"), body.get("value"))
        elif path == "zones":
            s.set_zones(body)
        elif path == "zones/tile":
            return {"moved": s.tile_windows()}
        elif path == "settings":
            if "language" in body:
                s.set_language(body["language"])
            self.settings_set(body)
        else:
            raise UserError("unknown endpoint")
        return self._state({})
