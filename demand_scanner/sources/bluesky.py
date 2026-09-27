"""Bluesky public search (no key) - real-time social chatter."""
from __future__ import annotations

from datetime import datetime

from ..models import Signal
from .base import ScanContext, Source

API = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"


def _ts(s: str) -> float | None:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


class Bluesky(Source):
    name = "bluesky"
    description = "Bluesky posts (public AppView search, no key)"

    def collect(self, ctx: ScanContext) -> list[Signal]:
        out: dict[str, Signal] = {}
        for q in [ctx.niche] + self.pain_queries(ctx)[:4]:
            data = self.http.get(API, params={"q": q, "limit": min(100, ctx.limit), "sort": "top", "lang": "en"})
            for p in data.get("posts", []):
                uri = p.get("uri", "")
                if uri in out:
                    continue
                handle = p.get("author", {}).get("handle", "")
                rkey = uri.rsplit("/", 1)[-1]
                rec = p.get("record", {})
                out[uri] = Signal(
                    source=self.name, kind="post", title="", text=rec.get("text", ""),
                    url=f"https://bsky.app/profile/{handle}/post/{rkey}",
                    score=float(p.get("likeCount", 0) + p.get("repostCount", 0)),
                    comments=int(p.get("replyCount", 0)), created_utc=_ts(rec.get("createdAt", "")),
                    author=handle,
                )
        return list(out.values())
