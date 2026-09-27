from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..http import Http
from ..models import Signal

# Phrases people use when they are in pain. Sources combine them with the niche.
PAIN_QUERIES = [
    "frustrating", "i hate", "is there an app", "is there a tool", "wish there was",
    "alternative to", "too expensive", "struggling with", "how do you manage", "i would pay",
]


@dataclass
class ScanContext:
    niche: str
    keywords: list[str]
    limit: int = 60                 # soft cap per source per query
    days: int = 730                 # how far back to look
    deep: bool = False              # more queries, comments, reviews
    geo: str = "US"
    extra: dict = field(default_factory=dict)


class Source:
    name = "base"
    description = ""
    requires_env: tuple[str, ...] = ()      # all required for the source to run
    optional_env: tuple[str, ...] = ()      # improve results when present
    default_enabled = True

    def __init__(self, http: Http):
        self.http = http

    def configured(self) -> tuple[bool, str]:
        missing = [e for e in self.requires_env if not os.environ.get(e)]
        if missing:
            return False, f"set {', '.join(missing)} to enable"
        return True, ""

    def collect(self, ctx: ScanContext) -> list[Signal]:  # pragma: no cover - interface
        raise NotImplementedError

    def pain_queries(self, ctx: ScanContext) -> list[str]:
        qs = PAIN_QUERIES if ctx.deep else PAIN_QUERIES[:6]
        return [f"{ctx.niche} {q}" for q in qs]
