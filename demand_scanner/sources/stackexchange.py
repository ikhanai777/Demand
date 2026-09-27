"""Stack Exchange network: questions people couldn't solve (softwarerecs is a goldmine)."""
from __future__ import annotations

import os

from ..models import Signal
from ..text import clean
from .base import ScanContext, Source

API = "https://api.stackexchange.com/2.3/search/advanced"
DEFAULT_SITES = ["softwarerecs", "webapps", "superuser", "android", "stackoverflow", "money", "workplace",
                 "freelancing", "ux"]


class StackExchange(Source):
    name = "stackexchange"
    description = "Stack Exchange questions (Software Recs, Web Apps, Super User, Android, ...)"
    optional_env = ("STACKEXCHANGE_KEY",)

    def collect(self, ctx: ScanContext) -> list[Signal]:
        sites = ctx.extra.get("se_sites") or (DEFAULT_SITES if ctx.deep else DEFAULT_SITES[:6])
        out: list[Signal] = []
        for site in sites:
            params = {"q": ctx.niche, "site": site, "sort": "relevance", "order": "desc",
                      "pagesize": min(50, ctx.limit), "filter": "withbody"}
            if key := os.environ.get("STACKEXCHANGE_KEY"):
                params["key"] = key
            data = self.http.get(API, params=params)
            for q in data.get("items", []):
                out.append(Signal(
                    source=self.name, kind="post", title=clean(q.get("title", "")),
                    text=clean(q.get("body", ""))[:2000], url=q.get("link", ""),
                    score=float(q.get("score") or 0), comments=int(q.get("answer_count") or 0),
                    views=int(q.get("view_count") or 0), created_utc=float(q.get("creation_date") or 0) or None,
                    author=(q.get("owner") or {}).get("display_name", ""),
                    meta={"site": site, "unanswered": not q.get("is_answered"), "tags": q.get("tags", [])},
                ))
            if data.get("quota_remaining", 1) < 5:
                break
        return out
