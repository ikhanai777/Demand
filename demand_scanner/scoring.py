"""Demand scoring.

Every pain point gets a 0-100 Demand Score built from interpretable components (0..1 each),
so you can see *why* something ranks high, not just that it does.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

from .models import PainPoint, Signal

WEIGHTS = {
    "volume": 0.18,        # how many independent mentions
    "engagement": 0.14,    # upvotes / comments / views behind those mentions
    "intensity": 0.14,     # how painful the language is
    "wtp": 0.16,           # willingness to pay / price complaints
    "breadth": 0.10,       # seen on several platforms, not one echo chamber
    "recency": 0.10,       # still being talked about
    "gap": 0.12,           # people explicitly seeking a tool / alternative / missing feature
    "momentum": 0.06,      # Google Trends direction for the niche
}

GAP_TAGS = {"tool_seeking", "alternative", "feature_gap"}
WTP_TAGS = {"willingness_to_pay", "price"}


def _engagement(s: Signal) -> float:
    return math.log1p(max(0.0, s.score) + 2 * s.comments + s.views / 500)


def grade(score: float) -> str:
    if score >= 75:
        return "HOT"
    if score >= 60:
        return "STRONG"
    if score >= 45:
        return "PROMISING"
    if score >= 30:
        return "WEAK"
    return "NOISE"


def score_points(points: list[PainPoint], momentum: float | None, n_sources: int) -> None:
    if not points:
        return
    max_eng = max((_engagement(s) for p in points for s in p.signals), default=1.0) or 1.0
    mom = 0.5 if momentum is None else max(0.0, min(1.0, 0.5 + momentum))
    for p in points:
        sigs = p.signals
        n = len(sigs)
        tags = Counter(t for s in sigs for t in s.pain_tags)
        p.tags = dict(tags.most_common())
        # unique authors guard against one person spamming the same complaint
        authors = len({s.author for s in sigs if s.author}) or n
        eff_n = min(n, authors + sum(1 for s in sigs if not s.author))
        top_eng = sorted((_engagement(s) for s in sigs), reverse=True)[:5]
        dated = [s.age_days for s in sigs if s.age_days is not None]
        c = {
            "volume": min(1.0, math.log1p(eff_n) / math.log1p(40)),
            "engagement": (sum(top_eng) / len(top_eng)) / max_eng if top_eng else 0.0,
            "intensity": sum(s.pain for s in sigs) / n,
            # search queries like "X free" show price sensitivity, not willingness to pay
            "wtp": min(1.0, sum(1 for s in sigs if s.kind != "query" and set(s.pain_tags) & WTP_TAGS)
                       / max(3.0, n * 0.25)),
            "breadth": min(1.0, len(p.sources) / max(1, min(4, n_sources))),
            "recency": (sum(1 for d in dated if d <= 180) / len(dated)) if dated else 0.5,
            "gap": min(1.0, sum(1 for s in sigs if set(s.pain_tags) & GAP_TAGS) / max(3.0, n * 0.3)),
            "momentum": mom,
        }
        p.components = c
        p.score = 100 * sum(WEIGHTS[k] * v for k, v in c.items())
    points.sort(key=lambda p: p.score, reverse=True)


def niche_score(points: list[PainPoint], signals: list[Signal], momentum: float | None,
                sources_ok: int) -> dict[str, Any]:
    """Overall demand for the niche: strength of the best pain points + total pain volume."""
    top = [p.score for p in points[:5]]
    best = (top[0] * 0.5 + (sum(top) / len(top)) * 0.5) if top else 0.0
    painful = [s for s in signals if s.pain > 0]
    volume = min(1.0, math.log1p(len(painful)) / math.log1p(300))
    wtp = sum(1 for s in painful if s.kind != "query" and set(s.pain_tags) & WTP_TAGS)
    mom = 0.5 if momentum is None else max(0.0, min(1.0, 0.5 + momentum))
    score = 0.6 * best + 100 * (0.2 * volume + 0.1 * min(1.0, wtp / 15) + 0.1 * mom)
    return {
        "score": round(score, 1),
        "grade": grade(score),
        "signals_total": len(signals),
        "signals_with_pain": len(painful),
        "wtp_signals": wtp,
        "pain_points": len(points),
        "trend_momentum": momentum,
        "sources_ok": sources_ok,
    }
