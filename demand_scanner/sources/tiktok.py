"""TikTok.

TikTok has no free public search API and blocks anonymous scraping, so this source uses
Apify (https://apify.com, free tier available) when APIFY_TOKEN is set. The actor can be
swapped with TIKTOK_APIFY_ACTOR (default: clockworks~tiktok-scraper).
"""
from __future__ import annotations

import os

from ..models import Signal
from .base import ScanContext, Source


class TikTok(Source):
    name = "tiktok"
    description = "TikTok videos for the niche (views/likes/comments) via Apify - needs APIFY_TOKEN"
    requires_env = ("APIFY_TOKEN",)

    def collect(self, ctx: ScanContext) -> list[Signal]:
        actor = os.environ.get("TIKTOK_APIFY_ACTOR", "clockworks~tiktok-scraper")
        queries = [ctx.niche, f"{ctx.niche} problem", f"{ctx.niche} hack"]
        items = self.http.post(
            f"https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items",
            params={"token": os.environ["APIFY_TOKEN"], "timeout": 240},
            json_body={"searchQueries": queries, "resultsPerPage": min(ctx.limit, 40),
                       "shouldDownloadVideos": False, "shouldDownloadCovers": False},
        )
        out: list[Signal] = []
        for it in items if isinstance(items, list) else []:
            out.append(Signal(
                source=self.name, kind="video", title="", text=it.get("text", ""),
                url=it.get("webVideoUrl", ""), score=float(it.get("diggCount") or 0),
                comments=int(it.get("commentCount") or 0), views=int(it.get("playCount") or 0),
                created_utc=float(it.get("createTime") or 0) or None,
                author=(it.get("authorMeta") or {}).get("name", ""),
                meta={"hashtags": [h.get("name") for h in it.get("hashtags", []) if isinstance(h, dict)],
                      "shares": it.get("shareCount")},
            ))
        return out
