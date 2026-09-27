"""Hacker News via the free Algolia search API (no key)."""
from __future__ import annotations

import time

from ..models import Signal
from ..text import clean
from .base import ScanContext, Source

API = "https://hn.algolia.com/api/v1/search"


class HackerNews(Source):
    name = "hackernews"
    description = "Hacker News stories, Ask HN posts and comments (Algolia API)"

    def collect(self, ctx: ScanContext) -> list[Signal]:
        since = int(time.time() - ctx.days * 86400)
        out: dict[str, Signal] = {}
        jobs = [(ctx.niche, "story"), (f"Ask HN {ctx.niche}", "ask_hn")]
        jobs += [(q, "comment") for q in self.pain_queries(ctx)]
        for query, tag in jobs:
            params = {"query": query, "tags": tag, "hitsPerPage": min(ctx.limit, 100),
                      "numericFilters": f"created_at_i>{since}"}
            data = self.http.get(API, params=params)
            for h in data.get("hits", []):
                oid = h.get("objectID")
                if not oid or oid in out:
                    continue
                is_comment = tag == "comment"
                title = h.get("story_title") if is_comment else h.get("title")
                text = h.get("comment_text") if is_comment else (h.get("story_text") or "")
                out[oid] = Signal(
                    source=self.name,
                    kind="comment" if is_comment else "post",
                    title=clean(title or "") if not is_comment else "",
                    text=clean(text or ""),
                    url=f"https://news.ycombinator.com/item?id={oid}",
                    score=float(h.get("points") or 0),
                    comments=int(h.get("num_comments") or 0),
                    created_utc=float(h.get("created_at_i") or 0) or None,
                    author=h.get("author") or "",
                    meta={"story": h.get("story_title") or ""},
                )
        return list(out.values())
