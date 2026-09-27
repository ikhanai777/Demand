"""Shared HTTP client: polite user agent, retries, per-host throttling, disk cache."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import requests

USER_AGENT = os.environ.get(
    "DEMAND_SCANNER_UA",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 demand-scanner/1.0",
)
CACHE_DIR = Path(os.environ.get("DEMAND_SCANNER_CACHE", Path.home() / ".cache" / "demand-scanner"))
CACHE_TTL = int(os.environ.get("DEMAND_SCANNER_CACHE_TTL", 6 * 3600))


class HttpError(RuntimeError):
    def __init__(self, status: int, url: str, body: str = ""):
        super().__init__(f"HTTP {status} for {url.split('?')[0]}")
        self.status = status
        self.body = body


class Http:
    """Thin wrapper around requests.Session. One instance is shared by all sources."""

    def __init__(self, use_cache: bool = True, min_interval: float = 0.35, timeout: float = 20):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        self.use_cache = use_cache
        self.min_interval = min_interval
        self.timeout = timeout
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        if use_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # -- cache -----------------------------------------------------------------
    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")

    def _cache_get(self, key: str) -> Any | None:
        if not self.use_cache:
            return None
        p = self._cache_path(key)
        if p.exists() and time.time() - p.stat().st_mtime < CACHE_TTL:
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return None
        return None

    def _cache_put(self, key: str, value: Any) -> None:
        if self.use_cache:
            try:
                self._cache_path(key).write_text(json.dumps(value), encoding="utf-8")
            except (OSError, TypeError):
                pass

    # -- throttling --------------------------------------------------------------
    def _throttle(self, url: str) -> None:
        host = url.split("/")[2] if "://" in url else url
        with self._lock:
            wait = self._last.get(host, 0) + self.min_interval - time.time()
            self._last[host] = time.time() + max(0.0, wait)
        if wait > 0:
            time.sleep(wait)

    # -- requests ----------------------------------------------------------------
    def request(self, method: str, url: str, *, params: dict | None = None, data: Any = None,
                json_body: Any = None, headers: dict | None = None, as_json: bool = True,
                cache: bool = True, retries: int = 2) -> Any:
        key = json.dumps([method, url, params, data, json_body], sort_keys=True, default=str)
        if cache and (hit := self._cache_get(key)) is not None:
            return hit

        last_exc: Exception | None = None
        for attempt in range(retries + 1):
            self._throttle(url)
            try:
                resp = self.session.request(method, url, params=params, data=data, json=json_body,
                                            headers=headers, timeout=self.timeout)
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(1.5 * (attempt + 1))
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                retry_after = resp.headers.get("retry-after", "")
                time.sleep(min(float(retry_after) if retry_after.isdigit() else 2.0 * (attempt + 1), 10))
                continue
            if resp.status_code >= 400:
                raise HttpError(resp.status_code, url, resp.text[:300])
            value = resp.json() if as_json else resp.text
            if cache:
                self._cache_put(key, value)
            return value
        raise RuntimeError(f"request failed for {url.split('?')[0]}: {last_exc}")

    def get(self, url: str, **kw: Any) -> Any:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw: Any) -> Any:
        return self.request("POST", url, **kw)
