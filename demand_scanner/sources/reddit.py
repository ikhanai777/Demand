"""Reddit: the richest pain-point source.

Order of preference:
  1. Official OAuth API (REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET, free "script" app) - works everywhere.
  2. Public JSON endpoints (www.reddit.com/*.json) - works from most home connections,
     blocked from many cloud/datacenter IPs.
  3. PullPush archive (api.pullpush.io) - community mirror, rate limited.
"""
from __future__ import annotations

import os
import time

from ..http import HttpError
from ..models import Signal
from ..text import clean
from .base import ScanContext, Source

PAIN_OR = '(frustrating OR hate OR "wish there was" OR "is there an app" OR "is there a tool" OR "alternative to" OR "would pay" OR struggling)'


class Reddit(Source):
    name = "reddit"
    description = "Reddit posts + top comments (OAuth API, public JSON, or PullPush fallback)"
    optional_env = ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET")

    def __init__(self, http):
        super().__init__(http)
        self._token: str | None = None
        self.mode = "public"

    # -- transport ---------------------------------------------------------------
    def _auth(self) -> None:
        cid, secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
        if not (cid and secret) or self._token:
            return
        resp = self.http.session.post(
            "https://www.reddit.com/api/v1/access_token", auth=(cid, secret),
            data={"grant_type": "client_credentials"}, timeout=20)
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        self.mode = "oauth"

    def _get(self, path: str, params: dict) -> dict:
        if self._token:
            return self.http.get(f"https://oauth.reddit.com{path}", params={**params, "raw_json": 1},
                                 headers={"Authorization": f"bearer {self._token}"})
        return self.http.get(f"https://www.reddit.com{path}.json", params={**params, "raw_json": 1})

    # -- parsing -----------------------------------------------------------------
    def _post(self, d: dict) -> Signal:
        return Signal(
            source=self.name, kind="post", title=clean(d.get("title", "")),
            text=clean(d.get("selftext", ""))[:3000],
            url="https://www.reddit.com" + d.get("permalink", ""),
            score=float(d.get("score") or d.get("ups") or 0), comments=int(d.get("num_comments") or 0),
            created_utc=float(d.get("created_utc") or 0) or None, author=d.get("author") or "",
            meta={"subreddit": d.get("subreddit"), "id": d.get("id")},
        )

    def _comment(self, d: dict, post_title: str) -> Signal:
        return Signal(
            source=self.name, kind="comment", title="", text=clean(d.get("body", ""))[:2000],
            url="https://www.reddit.com" + d.get("permalink", ""), score=float(d.get("score") or 0),
            created_utc=float(d.get("created_utc") or 0) or None, author=d.get("author") or "",
            meta={"subreddit": d.get("subreddit"), "post": post_title},
        )

    # -- collection ----------------------------------------------------------------
    def collect(self, ctx: ScanContext) -> list[Signal]:
        try:
            self._auth()
            return self._collect_api(ctx)
        except HttpError as exc:
            if exc.status not in (401, 403, 429):
                raise
            self.mode = "pullpush"
            return self._collect_pullpush(ctx)

    def _collect_api(self, ctx: ScanContext) -> list[Signal]:
        t = "year" if ctx.days <= 400 else "all"
        posts: dict[str, Signal] = {}
        queries = [f'"{ctx.niche}" {PAIN_OR}', ctx.niche]
        if ctx.deep:
            queries += [f"{ctx.niche} {q}" for q in ("app", "tool", "software", "advice", "problem")]
        for q in queries:
            data = self._get("/search", {"q": q, "sort": "relevance", "t": t, "limit": min(100, ctx.limit)})
            for c in data.get("data", {}).get("children", []):
                s = self._post(c["data"])
                posts.setdefault(s.meta["id"], s)

        # Find the niche's home subreddits and mine them for pain phrasing.
        subs = self._get("/subreddits/search", {"q": ctx.niche, "limit": 5})
        names = [c["data"]["display_name"] for c in subs.get("data", {}).get("children", [])
                 if c["data"].get("subscribers", 0) > 2000][: (4 if ctx.deep else 2)]
        for sub in names:
            data = self._get(f"/r/{sub}/search", {"q": PAIN_OR, "restrict_sr": 1, "sort": "top", "t": t,
                                                  "limit": min(100, ctx.limit)})
            for c in data.get("data", {}).get("children", []):
                s = self._post(c["data"])
                posts.setdefault(s.meta["id"], s)

        signals = list(posts.values())
        # Comments on the most-discussed posts are where the detailed pain lives.
        top = sorted(signals, key=lambda s: s.comments, reverse=True)[: (12 if ctx.deep else 5)]
        for p in top:
            try:
                thread = self._get(f"/comments/{p.meta['id']}", {"limit": 60, "sort": "top", "depth": 1})
            except HttpError:
                continue
            if isinstance(thread, list) and len(thread) > 1:
                for c in thread[1]["data"]["children"]:
                    if c.get("kind") == "t1" and c["data"].get("body") not in (None, "[deleted]", "[removed]"):
                        signals.append(self._comment(c["data"], p.title))
        return signals

    def _collect_pullpush(self, ctx: ScanContext) -> list[Signal]:
        after = int(time.time() - ctx.days * 86400)
        out: list[Signal] = []
        for kind, q in (("submission", ctx.niche), ("comment", f"{ctx.niche} frustrating"),
                        ("comment", f"{ctx.niche} wish")):
            data = self.http.get(f"https://api.pullpush.io/reddit/search/{kind}/",
                                 params={"q": q, "size": min(100, ctx.limit), "after": after, "sort": "desc",
                                         "sort_type": "score"})
            for d in data.get("data", []):
                if kind == "submission":
                    d.setdefault("permalink", f"/comments/{d.get('id')}")
                    out.append(self._post(d))
                else:
                    d.setdefault("permalink", d.get("permalink") or "")
                    out.append(self._comment(d, ""))
        return out
