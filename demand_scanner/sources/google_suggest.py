"""Google + YouTube autocomplete ("alphabet soup").

Autocomplete only shows queries with real search volume, so every suggestion is a
lightweight proof that people search for it. Pain-shaped suggestions ("X not working",
"X alternative", "how to X without Y") are especially valuable.
"""
from __future__ import annotations

import string

from ..models import Signal
from .base import ScanContext, Source

URL = "https://suggestqueries.google.com/complete/search"

TEMPLATES = [
    "{n}", "how to {n}", "why is {n}", "{n} app", "{n} tool", "{n} software", "best {n}",
    "{n} alternative", "{n} vs", "{n} problem", "{n} not working", "{n} without", "{n} for",
    "{n} too expensive", "{n} help", "{n} template", "can't {n}", "{n} automation", "{n} ai",
]


class GoogleSuggest(Source):
    name = "google_suggest"
    description = "Google & YouTube autocomplete - proof of real search demand (no key)"

    def _suggest(self, q: str, ds: str = "") -> list[str]:
        params = {"client": "firefox", "q": q, "hl": "en"}
        if ds:
            params["ds"] = ds
        data = self.http.get(URL, params=params)
        return [s for s in (data[1] if isinstance(data, list) and len(data) > 1 else []) if isinstance(s, str)]

    def collect(self, ctx: ScanContext) -> list[Signal]:
        n = ctx.niche.lower()
        seeds = [t.format(n=n) for t in TEMPLATES]
        if ctx.deep:
            seeds += [f"{n} for {c}" for c in string.ascii_lowercase]
            seeds += [f"{n} {c}" for c in string.ascii_lowercase]
        seen: dict[str, Signal] = {}
        for engine, ds in (("google", ""), ("youtube", "yt")):
            for seed in (seeds if engine == "google" else seeds[:10]):
                for pos, sug in enumerate(self._suggest(seed, ds)):
                    key = sug.lower().strip()
                    if key == n or key in seen:
                        continue
                    seen[key] = Signal(
                        source=self.name, kind="query", title=sug,
                        url=("https://www.google.com/search?q=" if engine == "google"
                             else "https://www.youtube.com/results?search_query=") + sug.replace(" ", "+"),
                        # earlier autocomplete positions ~= more searched
                        score=float(max(1, 10 - pos)),
                        meta={"engine": engine, "seed": seed, "position": pos},
                    )
        return list(seen.values())
