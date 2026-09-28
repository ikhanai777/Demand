"""Command-line interface.

  demand-scanner scan "meal prep for diabetics" [--deep] [--llm anthropic|hermes]
  demand-scanner compare "niche a" "niche b" ...        # rank several niches
  demand-scanner sources                                 # which sources are configured
  demand-scanner brief reports/<scan>/report.json 1      # print a build brief for Claude Code
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .http import Http
from .sources import REGISTRY


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Load .env from the current directory, falling back to the project root."""
    p = next((c for c in (Path(".env"), REPO_ROOT / ".env") if c.is_file()), None)
    if p is None:
        return
    for line in p.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            v = v.strip()
            if v[:1] in ('"', "'") and v[:1] in v[1:]:
                v = v[1:v.index(v[0], 1)]          # quoted value: keep '#' inside quotes
            else:
                v = v.split(" #", 1)[0].strip()   # drop inline comments
            if v:
                os.environ.setdefault(k.strip().removeprefix("export "), v)


def _scan_kwargs(a: argparse.Namespace) -> dict:
    return dict(
        sources=[s.strip() for s in a.sources.split(",")] if a.sources else None,
        keywords=[k.strip() for k in a.keywords.split(",")] if getattr(a, "keywords", None) else None,
        limit=a.limit, days=a.days, deep=a.deep, geo=a.geo, use_cache=not a.no_cache,
        llm_provider=None if a.llm == "none" else a.llm, llm_model=a.model, top=a.top,
    )


def cmd_scan(a: argparse.Namespace) -> int:
    from .report import write_all
    from .scanner import run_scan

    result = run_scan(a.niche, **_scan_kwargs(a))
    folder = write_all(result, a.out, top=a.top, briefs=a.briefs)
    s = result.summary
    print(f"\n{a.niche}: demand {s['score']}/100 ({s['grade']}) - {s['pain_points']} pain points "
          f"from {s['signals_total']} signals\n")
    for i, p in enumerate(result.points[:10], 1):
        name = p.llm.get("name") or p.label
        best = p.solutions[0]["type"] if p.solutions else "-"
        print(f"  {i:>2}. [{p.score:5.1f}] {name[:70]:<70} {len(p.signals):>3} sig  -> {best}")
    print(f"\nReport: {folder}/report.html\nJSON:   {folder}/report.json\nBriefs: {folder}/briefs/")
    if a.json:
        print(json.dumps(result.to_dict(a.top), indent=2, ensure_ascii=False))
    return 0


def cmd_compare(a: argparse.Namespace) -> int:
    from .report import write_all
    from .scanner import run_scan

    niches = list(a.niches)
    if a.file:
        niches += [n.strip() for n in Path(a.file).read_text(encoding="utf-8").splitlines() if n.strip() and not n.startswith("#")]
    rows = []
    for n in niches:
        r = run_scan(n, **_scan_kwargs(a))
        folder = write_all(r, a.out, top=a.top, briefs=a.briefs)
        best = r.points[0] if r.points else None
        rows.append((r.summary["score"], n, r.summary, best, folder))
    rows.sort(key=lambda x: x[0], reverse=True)
    lines = ["# Niche leaderboard", "", "| Rank | Niche | Demand | Grade | Pain pts | WTP | Momentum | Top pain point |",
             "|---|---|---|---|---|---|---|---|"]
    for i, (score, n, s, best, folder) in enumerate(rows, 1):
        top = (best.llm.get("name") or best.label) if best else "-"
        mom = s.get("trend_momentum")
        lines.append(f"| {i} | [{n}]({folder.name}/report.html) | **{score}** | {s['grade']} | {s['pain_points']} | "
                     f"{s['wtp_signals']} | {'n/a' if mom is None else f'{mom:+.0%}'} | {top} |")
    out = Path(a.out) / "leaderboard.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nSaved {out}")
    return 0


def cmd_sources(a: argparse.Namespace) -> int:
    http = Http(use_cache=False)
    for name, cls in REGISTRY.items():
        ok, why = cls(http).configured()
        extra = [e for e in cls.optional_env if not os.environ.get(e)]
        note = why or (f"optional: {', '.join(extra)}" if extra else "")
        print(f"  {'✓' if ok else '·'} {name:<15} {cls.description}" + (f"\n{'':19}{note}" if note else ""))
    return 0


def cmd_brief(a: argparse.Namespace) -> int:
    folder = Path(a.report).parent if a.report.endswith(".json") else Path(a.report)
    files = sorted((folder / "briefs").glob(f"{int(a.rank):02d}-*.md"))
    if not files:
        print(f"No brief #{a.rank} in {folder}/briefs", file=sys.stderr)
        return 1
    print(files[0].read_text(encoding="utf-8"))
    return 0


def cmd_mcp(a: argparse.Namespace) -> int:
    try:
        from .mcp_server import main as mcp_main
    except ImportError as exc:
        print(f"MCP support is not installed ({exc}). Run: pip install -e \".[mcp]\"", file=sys.stderr)
        return 1
    mcp_main()
    return 0


def cmd_dashboard(a: argparse.Namespace) -> int:
    from .dashboard import serve

    serve(host=a.host, port=a.port, reports_dir=a.out, open_browser=a.open)
    return 0


def main(argv: list[str] | None = None) -> int:
    # Windows consoles default to cp1252; never crash on a non-ASCII niche or quote.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    _load_dotenv()
    ap = argparse.ArgumentParser(prog="demand-scanner", description="Find and score pain points in any niche.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--sources", help=f"comma list (default: all configured). Available: {','.join(REGISTRY)}")
        p.add_argument("--limit", type=int, default=60, help="max items per source query (default 60)")
        p.add_argument("--days", type=int, default=730, help="look-back window in days (default 730)")
        p.add_argument("--deep", action="store_true", help="more queries, comments and reviews (slower)")
        p.add_argument("--geo", default="US", help="country code for Trends / app stores (default US)")
        p.add_argument("--llm", default=os.environ.get("DEMAND_SCANNER_LLM", "none"),
                       choices=["none", "anthropic", "hermes", "openai"],
                       help="synthesize pain points with an LLM (hermes/openai = any OpenAI-compatible endpoint)")
        p.add_argument("--model", help="override LLM model id")
        p.add_argument("--top", type=int, default=25, help="pain points to keep in the report")
        p.add_argument("--briefs", type=int, default=10, help="build briefs to generate")
        p.add_argument("--out", default=os.environ.get("DEMAND_SCANNER_REPORTS", "reports"),
                       help="output directory (env DEMAND_SCANNER_REPORTS)")
        p.add_argument("--no-cache", action="store_true", help="ignore the 6h HTTP cache")

    p = sub.add_parser("scan", help="scan one niche")
    p.add_argument("niche")
    p.add_argument("--keywords", help="comma list of relevance keywords (default: words in the niche)")
    p.add_argument("--json", action="store_true", help="also print report JSON to stdout")
    common(p)
    p.set_defaults(fn=cmd_scan)

    p = sub.add_parser("compare", help="scan several niches and rank them")
    p.add_argument("niches", nargs="*")
    p.add_argument("--file", help="text file with one niche per line")
    common(p)
    p.set_defaults(fn=cmd_compare)

    p = sub.add_parser("sources", help="list data sources and configuration status")
    p.set_defaults(fn=cmd_sources)

    p = sub.add_parser("dashboard", help="run the local web dashboard")
    p.add_argument("--host", default=os.environ.get("DEMAND_DASHBOARD_HOST", "127.0.0.1"),
                   help="bind address (default 127.0.0.1 = this computer only)")
    p.add_argument("--port", type=int, default=int(os.environ.get("DEMAND_DASHBOARD_PORT", 8765)))
    p.add_argument("--out", default=os.environ.get("DEMAND_SCANNER_REPORTS", "reports"),
                   help="reports directory to serve and write to")
    p.add_argument("--open", action="store_true", help="open the dashboard in the default browser")
    p.set_defaults(fn=cmd_dashboard)

    p = sub.add_parser("mcp", help="run the MCP server so Claude Desktop / Claude Code can use the scanner")
    p.set_defaults(fn=cmd_mcp)

    p = sub.add_parser("brief", help="print a build brief from a finished scan")
    p.add_argument("report", help="path to report.json or the scan folder")
    p.add_argument("rank", nargs="?", default=1)
    p.set_defaults(fn=cmd_brief)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
