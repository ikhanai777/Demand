"""MCP server helpers (skipped when the optional `mcp` package isn't installed)."""
from __future__ import annotations

import pytest

pytest.importorskip("mcp")

from demand_scanner import mcp_server  # noqa: E402

from .test_dashboard import server  # noqa: E402,F401  (fixture writes a real scan)


def test_tools_and_compact_report(server, monkeypatch, tmp_path):  # noqa: F811
    _, sid = server
    reports = tmp_path  # the fixture wrote the scan into tmp_path
    monkeypatch.setattr(mcp_server, "REPORTS", reports)
    scans = mcp_server.list_scans()
    assert scans and scans[0]["scan_id"] == sid
    data = mcp_server.get_scan(sid, top=3)
    assert data["niche"] == "freelance invoicing" and 1 <= len(data["pain_points"]) <= 3
    p = data["pain_points"][0]
    assert {"pain_point", "score", "components", "evidence", "solution_fit"} <= set(p)
    assert "Build brief #1" in mcp_server.get_build_brief(sid, 1)
    with pytest.raises(mcp_server.ToolError):
        mcp_server.get_scan("../etc")
    with pytest.raises(mcp_server.ToolError):
        mcp_server.get_build_brief(sid, 99)
