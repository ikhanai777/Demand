"""Core data structures shared by every stage of the pipeline."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Signal:
    """One piece of raw evidence: a post, comment, search query, review, video..."""

    source: str                 # "reddit", "hackernews", ...
    kind: str                   # post | comment | query | review | video | issue | trend
    title: str
    text: str = ""
    url: str = ""
    score: float = 0.0          # upvotes / likes / reactions
    comments: int = 0
    views: int = 0
    created_utc: float | None = None
    author: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    # Filled in by analysis
    pain: float = 0.0
    pain_tags: list[str] = field(default_factory=list)

    @property
    def body(self) -> str:
        return f"{self.title}\n{self.text}".strip()

    @property
    def age_days(self) -> float | None:
        if not self.created_utc:
            return None
        return max(0.0, (time.time() - self.created_utc) / 86400)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["text"] = self.text[:1200]
        return d


@dataclass
class SourceResult:
    name: str
    signals: list[Signal] = field(default_factory=list)
    ok: bool = True
    error: str = ""
    skipped: bool = False       # not configured / optional dependency missing
    elapsed: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)  # e.g. trends momentum

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "skipped": self.skipped,
            "error": self.error,
            "signals": len(self.signals),
            "elapsed_s": round(self.elapsed, 1),
        }


@dataclass
class PainPoint:
    id: int
    label: str
    keywords: list[str]
    signals: list[Signal]
    score: float = 0.0
    components: dict[str, float] = field(default_factory=dict)
    tags: dict[str, int] = field(default_factory=dict)
    solutions: list[dict[str, Any]] = field(default_factory=list)
    llm: dict[str, Any] = field(default_factory=dict)

    @property
    def sources(self) -> list[str]:
        return sorted({s.source for s in self.signals})

    def top_quotes(self, n: int = 5, max_queries: int = 3) -> list[Signal]:
        """Most telling evidence first; terse search queries are capped so real voices show."""
        ranked = sorted(self.signals, key=lambda s: (s.kind not in ("query", "trend"), s.pain,
                                                     s.score + s.comments), reverse=True)
        out, q = [], 0
        for s in ranked:
            if s.kind in ("query", "trend"):
                if q >= max_queries:
                    continue
                q += 1
            out.append(s)
            if len(out) == n:
                break
        return out

    def to_dict(self, max_signals: int = 25) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.llm.get("name") or self.label,
            "keywords": self.keywords,
            "score": round(self.score, 1),
            "components": {k: round(v, 3) for k, v in self.components.items()},
            "tags": self.tags,
            "sources": self.sources,
            "signal_count": len(self.signals),
            "solutions": self.solutions,
            "llm": self.llm,
            "evidence": [s.to_dict() for s in self.top_quotes(max_signals, max_queries=10)],
        }
