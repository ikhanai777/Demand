"""Dashboard API tests (local server on a random port, no external network)."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from demand_scanner import pain
from demand_scanner.cluster import cluster
from demand_scanner.dashboard import make_server
from demand_scanner.report import write_all
from demand_scanner.scanner import ScanResult
from demand_scanner.scoring import niche_score, score_points
from demand_scanner.solutions import recommend
from demand_scanner.text import niche_keywords

from .test_pipeline import corpus


@pytest.fixture()
def server(tmp_path):
    sigs = corpus()
    pain.annotate(sigs)
    points = [p for p in cluster(sigs, niche_keywords("freelance invoicing")) if len(p.signals) >= 2]
    score_points(points, None, 4)
    for p in points:
        p.solutions = recommend(p)
    r = ScanResult(niche="freelance invoicing", keywords=["freelance", "invoicing"],
                   generated_at="2026-01-01T00:00:00+00:00", summary=niche_score(points, sigs, None, 4),
                   points=points, sources=[])
    folder = write_all(r, tmp_path)
    httpd = make_server("127.0.0.1", 0, tmp_path, token="s3cret")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", folder.name
    httpd.shutdown()


def call(url, method="GET", body=None, headers=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


def test_read_endpoints(server):
    base, sid = server
    assert call(base + "/")[0] == 200
    assert json.loads(call(base + "/api/health")[1])["auth"] is True
    scans = json.loads(call(base + "/api/scans")[1])
    assert scans[0]["id"] == sid and scans[0]["niche"] == "freelance invoicing"
    detail = json.loads(call(f"{base}/api/scans/{sid}")[1])
    assert detail["pain_points"] and detail["briefs"] and len(detail["history"]) == 1
    status, brief = call(f"{base}/api/scans/{sid}/briefs/1")
    assert status == 200 and "Build brief #1" in brief
    assert call(f"{base}/reports/{sid}/report.html")[0] == 200


def test_rejects_bad_paths_and_auth(server):
    base, sid = server
    assert call(base + "/reports/..%2F..%2Fetc/passwd")[0] == 404
    assert call(f"{base}/reports/{sid}/..%2F..%2Fsecret")[0] in (403, 404)
    assert call(base + "/api/scans/NOT_VALID")[0] == 404
    assert call(base + "/api/scans", "POST", {"niche": "x"})[0] == 401            # token required
    assert call(base + "/api/scans", "POST", {"niche": ""}, {"X-Token": "s3cret"})[0] == 400
    assert call(f"{base}/api/scans/{sid}", "DELETE")[0] == 401
    assert call(f"{base}/api/scans/{sid}", "DELETE", headers={"X-Token": "s3cret"})[0] == 200
    assert json.loads(call(base + "/api/scans")[1]) == []
