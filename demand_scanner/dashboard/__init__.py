"""Local demand dashboard: browse scans, compare niches, launch new scans, copy build briefs.

Pure standard library (http.server) so it runs anywhere Python runs, including Windows 10.

    python -m demand_scanner dashboard            # http://127.0.0.1:8765
    python -m demand_scanner dashboard --open --port 9000

JSON API (used by the web UI and handy for agents such as Hermes):
    GET    /api/health
    GET    /api/scans                     latest-first list of scan summaries
    GET    /api/scans/<id>                full report.json (+ briefs list, niche history)
    GET    /api/scans/<id>/briefs/<rank>  build brief (markdown)
    DELETE /api/scans/<id>                delete a scan folder
    POST   /api/scans                     {"niche": "...", "deep": false, "sources": [], "llm": "none"} -> job
    GET    /api/jobs, /api/jobs/<id>      scan job status + live log
    GET    /api/sources                   data source configuration
    GET    /reports/<id>/<file>           static report files (report.html, report.md, ...)
"""
from __future__ import annotations

import json
import mimetypes
import os
import queue
import re
import shutil
import threading
import time
import traceback
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .. import __version__

STATIC = Path(__file__).parent / "static"
SCAN_ID = re.compile(r"^[a-z0-9-]{1,80}$")


class JobRunner:
    """Runs scans one at a time in a background thread (polite to the data sources)."""

    def __init__(self, reports_dir: Path):
        self.reports_dir = reports_dir
        self.jobs: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []
        self.q: queue.Queue[str] = queue.Queue()
        self.lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True).start()

    def submit(self, opts: dict[str, Any]) -> dict[str, Any]:
        job = {"id": uuid.uuid4().hex[:10], "niche": opts["niche"], "options": opts, "status": "queued",
               "log": [], "created": time.time(), "started": None, "finished": None, "scan_id": None,
               "error": None}
        with self.lock:
            self.jobs[job["id"]] = job
            self.order.append(job["id"])
            for old in self.order[:-50]:
                self.jobs.pop(old, None)
            self.order = self.order[-50:]
        self.q.put(job["id"])
        return job

    def list(self) -> list[dict[str, Any]]:
        with self.lock:
            return [self.jobs[j] for j in reversed(self.order) if j in self.jobs]

    def _worker(self) -> None:
        from ..report import write_all
        from ..scanner import run_scan

        while True:
            jid = self.q.get()
            job = self.jobs.get(jid)
            if not job:
                continue
            job["status"], job["started"] = "running", time.time()
            o = job["options"]

            def progress(msg: str, job=job) -> None:
                job["log"].append(msg)

            try:
                result = run_scan(
                    o["niche"], sources=o.get("sources") or None, deep=bool(o.get("deep")),
                    days=int(o.get("days") or 730), geo=o.get("geo") or "US",
                    llm_provider=None if o.get("llm") in (None, "", "none") else o["llm"],
                    progress=progress)
                folder = write_all(result, self.reports_dir)
                job["scan_id"] = folder.name
                job["status"] = "done"
                progress(f"Done: demand {result.summary['score']}/100 ({result.summary['grade']})")
            except Exception as exc:  # report, never kill the worker
                job["status"], job["error"] = "failed", f"{type(exc).__name__}: {exc}"
                progress(traceback.format_exc(limit=3))
            job["finished"] = time.time()


def _summary(folder: Path) -> dict[str, Any] | None:
    try:
        data = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    s = data.get("summary", {})
    pts = data.get("pain_points", [])
    return {
        "id": folder.name,
        "niche": data.get("niche", folder.name),
        "generated_at": data.get("generated_at", ""),
        "score": s.get("score", 0),
        "grade": s.get("grade", ""),
        "signals_total": s.get("signals_total", 0),
        "signals_with_pain": s.get("signals_with_pain", 0),
        "wtp_signals": s.get("wtp_signals", 0),
        "pain_points": s.get("pain_points", 0),
        "trend_momentum": s.get("trend_momentum"),
        "top_pain": pts[0]["label"] if pts else "",
        "top_pain_score": pts[0]["score"] if pts else 0,
        "hot_pain_points": sum(1 for p in pts if p.get("score", 0) >= 60),
        "sources_ok": s.get("sources_ok", 0),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = f"DemandDashboard/{__version__}"
    reports_dir: Path
    runner: JobRunner
    token: str | None

    # -- helpers -------------------------------------------------------------------
    def log_message(self, fmt: str, *args: Any) -> None:  # quieter console
        if os.environ.get("DEMAND_DASHBOARD_VERBOSE"):
            super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, data: Any, status: int = 200) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status: int, msg: str) -> None:
        self._json({"error": msg}, status)

    def _file(self, path: Path) -> None:
        if not path.is_file():
            return self._error(404, "not found")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/json", "application/javascript"):
            ctype += "; charset=utf-8"
        self._send(200, path.read_bytes(), ctype)

    def _scan_dir(self, scan_id: str) -> Path | None:
        if not SCAN_ID.match(scan_id):
            return None
        folder = (self.reports_dir / scan_id).resolve()
        if folder.parent != self.reports_dir.resolve() or not (folder / "report.json").is_file():
            return None
        return folder

    def _authorized(self) -> bool:
        if not self.token:
            return True
        return self.headers.get("X-Token") == self.token

    def _all_scans(self) -> list[dict[str, Any]]:
        if not self.reports_dir.is_dir():
            return []
        rows = [s for f in self.reports_dir.iterdir() if f.is_dir() and (s := _summary(f))]
        return sorted(rows, key=lambda r: r["generated_at"], reverse=True)

    # -- routing -------------------------------------------------------------------
    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path).rstrip("/") or "/"
        parts = path.strip("/").split("/")
        if path in ("/", "/index.html"):
            return self._file(STATIC / "index.html")
        if path == "/api/health":
            return self._json({"ok": True, "version": __version__, "reports_dir": str(self.reports_dir),
                               "auth": bool(self.token)})
        if path == "/api/scans":
            return self._json(self._all_scans())
        if parts[:2] == ["api", "scans"] and len(parts) == 3:
            folder = self._scan_dir(parts[2])
            if not folder:
                return self._error(404, "scan not found")
            data = json.loads((folder / "report.json").read_text(encoding="utf-8"))
            data["id"] = folder.name
            data["briefs"] = sorted(p.name for p in (folder / "briefs").glob("*.md"))
            data["history"] = [{"id": s["id"], "generated_at": s["generated_at"], "score": s["score"]}
                               for s in self._all_scans() if s["niche"].lower() == data["niche"].lower()][::-1]
            return self._json(data)
        if parts[:2] == ["api", "scans"] and len(parts) == 5 and parts[3] == "briefs":
            folder = self._scan_dir(parts[2])
            if not folder or not parts[4].isdigit():
                return self._error(404, "scan not found")
            files = sorted((folder / "briefs").glob(f"{int(parts[4]):02d}-*.md"))
            if not files:
                return self._error(404, "brief not found")
            return self._send(200, files[0].read_bytes(), "text/markdown; charset=utf-8")
        if path == "/api/jobs":
            return self._json(self.runner.list())
        if parts[:2] == ["api", "jobs"] and len(parts) == 3:
            job = self.runner.jobs.get(parts[2])
            return self._json(job) if job else self._error(404, "job not found")
        if path == "/api/sources":
            return self._json(_sources())
        if parts[0] == "reports" and len(parts) >= 3:
            folder = self._scan_dir(parts[1])
            if not folder:
                return self._error(404, "not found")
            target = (folder / "/".join(parts[2:])).resolve()
            if folder not in target.parents:
                return self._error(403, "forbidden")
            return self._file(target)
        return self._error(404, "not found")

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if not self._authorized():
            return self._error(401, "missing or invalid X-Token")
        if path != "/api/scans":
            return self._error(404, "not found")
        try:
            length = min(int(self.headers.get("Content-Length") or 0), 64_000)
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            return self._error(400, "invalid JSON")
        niche = str(body.get("niche", "")).strip()
        if not niche or len(niche) > 120:
            return self._error(400, "niche is required (max 120 chars)")
        from ..sources import REGISTRY
        sources = [s for s in body.get("sources") or [] if s in REGISTRY]
        llm = body.get("llm") if body.get("llm") in ("none", "anthropic", "hermes", "openai") else "none"
        job = self.runner.submit({"niche": niche, "deep": bool(body.get("deep")), "sources": sources,
                                  "llm": llm, "geo": str(body.get("geo") or "US")[:4],
                                  "days": body.get("days") or 730})
        return self._json(job, HTTPStatus.ACCEPTED)

    def do_DELETE(self) -> None:
        parts = urlparse(self.path).path.strip("/").split("/")
        if not self._authorized():
            return self._error(401, "missing or invalid X-Token")
        if parts[:2] != ["api", "scans"] or len(parts) != 3:
            return self._error(404, "not found")
        folder = self._scan_dir(parts[2])
        if not folder:
            return self._error(404, "scan not found")
        shutil.rmtree(folder)
        return self._json({"deleted": parts[2]})


def _sources() -> list[dict[str, Any]]:
    from ..http import Http
    from ..sources import REGISTRY

    http = Http(use_cache=False)
    out = []
    for name, cls in REGISTRY.items():
        ok, why = cls(http).configured()
        missing = [e for e in cls.optional_env if not os.environ.get(e)]
        out.append({"name": name, "description": cls.description, "enabled": ok,
                    "note": why or (f"optional: {', '.join(missing)}" if missing else "")})
    return out


class _Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets two processes bind the same port silently; refuse instead.
    allow_reuse_address = os.name != "nt"
    daemon_threads = True


def make_server(host: str = "127.0.0.1", port: int = 8765, reports_dir: str | Path = "reports",
                token: str | None = None) -> _Server:
    reports = Path(reports_dir).resolve()
    reports.mkdir(parents=True, exist_ok=True)
    handler = type("BoundHandler", (Handler,), {"reports_dir": reports, "runner": JobRunner(reports),
                                                "token": token})
    return _Server((host, port), handler)


def serve(host: str = "127.0.0.1", port: int = 8765, reports_dir: str | Path = "reports",
          open_browser: bool = False) -> None:
    token = os.environ.get("DEMAND_DASHBOARD_TOKEN") or None
    try:
        httpd = make_server(host, port, reports_dir, token)
    except OSError as exc:
        raise SystemExit(f"Cannot listen on {host}:{port} ({exc}). Is the dashboard already running? "
                         f"Use --port or DEMAND_DASHBOARD_PORT to pick another port.")
    reports = Path(reports_dir).resolve()
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{port}/"
    print(f"Demand dashboard running at {url}  (reports: {reports})", flush=True)
    if host not in ("127.0.0.1", "localhost") and not token:
        print("WARNING: listening on a non-local address without DEMAND_DASHBOARD_TOKEN; "
              "anyone on the network can start scans.", flush=True)
    if open_browser:
        import webbrowser
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        httpd.server_close()
