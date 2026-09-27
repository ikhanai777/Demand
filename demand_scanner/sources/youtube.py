"""YouTube: what people watch to solve the problem (content demand), plus comments with an API key."""
from __future__ import annotations

import json
import os
import re
import time

from ..http import HttpError
from ..models import Signal
from ..text import clean
from .base import ScanContext, Source

_INITIAL = re.compile(r"var ytInitialData = (\{.*?\});</script>", re.S)
_AGO = re.compile(r"(\d+)\s+(hour|day|week|month|year)")
_UNIT_DAYS = {"hour": 1 / 24, "day": 1, "week": 7, "month": 30, "year": 365}


def _views(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else 0


def _walk(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                yield v
            else:
                yield from _walk(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, key)


class YouTube(Source):
    name = "youtube"
    description = "YouTube search results (views = content demand); comments with YOUTUBE_API_KEY"
    optional_env = ("YOUTUBE_API_KEY",)

    def collect(self, ctx: ScanContext) -> list[Signal]:
        queries = [f"{ctx.niche} problem", f"how to {ctx.niche}", f"{ctx.niche} mistakes"]
        if ctx.deep:
            queries += [f"{ctx.niche} tips", f"best {ctx.niche} app", f"{ctx.niche} for beginners"]
        out: dict[str, Signal] = {}
        for q in queries:
            html = self.http.get("https://www.youtube.com/results", params={"search_query": q, "hl": "en"},
                                 as_json=False)
            m = _INITIAL.search(html)
            if not m:
                continue
            data = json.loads(m.group(1))
            for v in _walk(data, "videoRenderer"):
                vid = v.get("videoId")
                if not vid or vid in out:
                    continue
                title = "".join(r.get("text", "") for r in v.get("title", {}).get("runs", []))
                views = _views(v.get("viewCountText", {}).get("simpleText", ""))
                ago = _AGO.search(v.get("publishedTimeText", {}).get("simpleText", ""))
                created = time.time() - int(ago.group(1)) * _UNIT_DAYS[ago.group(2)] * 86400 if ago else None
                snippet = " ".join(r.get("text", "") for sn in v.get("detailedMetadataSnippets", [])
                                   for r in sn.get("snippetText", {}).get("runs", []))
                out[vid] = Signal(source=self.name, kind="video", title=clean(title), text=clean(snippet),
                                  url=f"https://www.youtube.com/watch?v={vid}", views=views,
                                  created_utc=created,
                                  author=v.get("ownerText", {}).get("runs", [{}])[0].get("text", ""),
                                  meta={"query": q, "video_id": vid})
        signals = list(out.values())
        key = os.environ.get("YOUTUBE_API_KEY")
        if key:
            for v in sorted(signals, key=lambda s: s.views, reverse=True)[: (8 if ctx.deep else 4)]:
                signals.extend(self._comments(v, key))
        return signals

    def _comments(self, video: Signal, key: str) -> list[Signal]:
        try:
            data = self.http.get("https://www.googleapis.com/youtube/v3/commentThreads", params={
                "part": "snippet", "videoId": video.meta["video_id"], "maxResults": 50, "order": "relevance",
                "textFormat": "plainText", "key": key})
        except HttpError:
            return []
        out = []
        for item in data.get("items", []):
            sn = item["snippet"]["topLevelComment"]["snippet"]
            out.append(Signal(source=self.name, kind="comment", title="", text=clean(sn.get("textDisplay", "")),
                              url=video.url, score=float(sn.get("likeCount") or 0),
                              comments=int(item["snippet"].get("totalReplyCount") or 0),
                              author=sn.get("authorDisplayName", ""), meta={"video": video.title}))
        return out
