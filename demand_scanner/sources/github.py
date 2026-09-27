"""GitHub issues: feature requests with many 👍 reactions = unmet demand in existing tools."""
from __future__ import annotations

import os
from datetime import datetime

from ..models import Signal
from ..text import clean
from .base import ScanContext, Source


class GitHubIssues(Source):
    name = "github"
    description = "GitHub feature-request issues ranked by reactions (GITHUB_TOKEN recommended)"
    optional_env = ("GITHUB_TOKEN",)

    def collect(self, ctx: ScanContext) -> list[Signal]:
        headers = {"Accept": "application/vnd.github+json"}
        if tok := os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {tok}"
        out: dict[str, Signal] = {}
        for q in (f"{ctx.niche} in:title,body is:issue label:enhancement",
                  f'{ctx.niche} "feature request" is:issue'):
            data = self.http.get("https://api.github.com/search/issues", headers=headers, params={
                "q": q, "sort": "reactions", "order": "desc", "per_page": min(50, ctx.limit)})
            for it in data.get("items", []):
                url = it.get("html_url", "")
                if url in out:
                    continue
                reactions = (it.get("reactions") or {}).get("total_count", 0)
                out[url] = Signal(
                    source=self.name, kind="issue", title=clean(it.get("title", "")),
                    text=clean(it.get("body") or "")[:2000], url=url, score=float(reactions),
                    comments=int(it.get("comments") or 0),
                    created_utc=datetime.fromisoformat(it["created_at"].replace("Z", "+00:00")).timestamp()
                    if it.get("created_at") else None,
                    author=(it.get("user") or {}).get("login", ""),
                    meta={"repo": it.get("repository_url", "").split("repos/")[-1], "state": it.get("state")},
                )
        return list(out.values())
