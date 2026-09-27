"""The pipeline: collect -> filter -> detect pain -> cluster -> score -> recommend -> (LLM) -> report."""
from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from . import pain as pain_mod
from .cluster import cluster
from .http import Http
from .models import PainPoint, Signal, SourceResult
from .scoring import grade, niche_score, score_points
from .solutions import recommend
from .sources import REGISTRY, ScanContext
from .text import mentions_niche, niche_keywords


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


@dataclass
class ScanResult:
    niche: str
    keywords: list[str]
    generated_at: str
    summary: dict[str, Any]
    points: list[PainPoint]
    sources: list[SourceResult]
    trend: dict[str, Any] = field(default_factory=dict)
    queries: list[Signal] = field(default_factory=list)   # autocomplete & trend queries
    llm: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, top: int = 25) -> dict[str, Any]:
        return {
            "niche": self.niche,
            "keywords": self.keywords,
            "generated_at": self.generated_at,
            "summary": self.summary,
            "trend": self.trend,
            "llm_summary": self.llm.get("niche_summary", ""),
            "sources": [s.status() for s in self.sources],
            "pain_points": [p.to_dict() for p in self.points[:top]],
            "search_demand": [
                {"query": q.title, "source": q.source, "engine": q.meta.get("engine") or q.meta.get("list"),
                 "pain_tags": q.pain_tags, "url": q.url}
                for q in sorted(self.queries, key=lambda q: (q.pain, q.score), reverse=True)[:80]
            ],
        }


def run_scan(niche: str, *, sources: list[str] | None = None, keywords: list[str] | None = None,
             limit: int = 60, days: int = 730, deep: bool = False, geo: str = "US", use_cache: bool = True,
             llm_provider: str | None = None, llm_model: str | None = None, top: int = 25,
             min_signals: int = 2) -> ScanResult:
    kw = keywords or niche_keywords(niche)
    ctx = ScanContext(niche=niche, keywords=kw, limit=limit, days=days, deep=deep, geo=geo)
    http = Http(use_cache=use_cache)
    names = sources or [n for n, cls in REGISTRY.items() if cls.default_enabled]

    results: list[SourceResult] = []
    runnable = []
    for name in names:
        cls = REGISTRY.get(name)
        if cls is None:
            results.append(SourceResult(name=name, ok=False, error="unknown source"))
            continue
        src = cls(http)
        ok, why = src.configured()
        if not ok:
            results.append(SourceResult(name=name, ok=False, skipped=True, error=why))
            continue
        runnable.append(src)

    log(f"Scanning '{niche}' across {len(runnable)} sources: {', '.join(s.name for s in runnable)}")

    def _run(src) -> SourceResult:
        t0 = time.time()
        try:
            sigs = src.collect(ctx)
            res = SourceResult(name=src.name, signals=sigs)
            if getattr(src, "mode", None):
                res.extra["mode"] = src.mode
        except Exception as exc:  # one broken source must never kill the scan
            res = SourceResult(name=src.name, ok=False, error=f"{type(exc).__name__}: {exc}"[:300])
        res.elapsed = time.time() - t0
        return res

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_run, s) for s in runnable]
        for fut in as_completed(futures):
            r = fut.result()
            status = f"{len(r.signals)} signals" if r.ok else f"FAILED ({r.error})"
            log(f"  - {r.name:<15} {status} [{r.elapsed:.1f}s]")
            results.append(r)

    # Dedupe + relevance filter
    seen: set[str] = set()
    signals: list[Signal] = []
    for r in results:
        for s in r.signals:
            key = s.url + "|" + s.body[:80] if s.url else s.body[:160]
            if key in seen or len(s.body) < 8:
                continue
            seen.add(key)
            # queries come from the niche and reviews from niche apps: relevant by construction
            if s.kind in ("query", "trend", "review") or mentions_niche(
                    s.body + " " + str(s.meta.get("post", "")), kw):
                signals.append(s)

    pain_mod.annotate(signals)
    queries = [s for s in signals if s.kind in ("query", "trend")]
    points = cluster(signals, kw)
    points = [p for p in points if len(p.signals) >= min_signals] or points[:10]

    momentum = ctx.extra.get("trend_momentum")
    sources_ok = sum(1 for r in results if r.ok and r.signals)
    score_points(points, momentum, sources_ok)
    for p in points:
        p.solutions = recommend(p)

    llm_result: dict[str, Any] = {}
    if llm_provider:
        log(f"Synthesizing top {min(top, len(points))} pain points with {llm_provider}...")
        try:
            from .llm import synthesize
            llm_result = synthesize(niche, points[:top], llm_provider, llm_model)
        except Exception as exc:
            log(f"  LLM synthesis failed: {type(exc).__name__}: {exc}")
            llm_result = {"error": str(exc)}

    summary = niche_score(points, signals, momentum, sources_ok)
    summary["grade"] = grade(summary["score"])
    trend = {k.replace("trend_", ""): v for k, v in ctx.extra.items() if k.startswith("trend_")}
    return ScanResult(
        niche=niche, keywords=kw, generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        summary=summary, points=points, sources=sorted(results, key=lambda r: r.name), trend=trend,
        queries=queries, llm=llm_result,
    )
