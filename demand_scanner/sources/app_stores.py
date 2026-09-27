"""App store reviews: what users of *existing* apps hate (competitor weaknesses).

* Apple App Store - iTunes Search API + public customer-review RSS (no key).
* Google Play      - needs the optional `google-play-scraper` package (pip install google-play-scraper).
"""
from __future__ import annotations

from datetime import datetime

from ..models import Signal
from .base import ScanContext, Source


class AppStore(Source):
    name = "app_store"
    description = "Apple App Store low-star reviews of competing apps (no key)"

    def collect(self, ctx: ScanContext) -> list[Signal]:
        country = ctx.geo.lower()
        found = self.http.get("https://itunes.apple.com/search", params={
            "term": ctx.niche, "entity": "software", "limit": 8 if ctx.deep else 5, "country": country})
        out: list[Signal] = []
        for app in found.get("results", []):
            app_id, app_name = app.get("trackId"), app.get("trackName", "")
            for page in range(1, 3 if ctx.deep else 2):
                feed = self.http.get(
                    f"https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json")
                entries = feed.get("feed", {}).get("entry", [])
                if isinstance(entries, dict):
                    entries = [entries]
                for e in entries:
                    if "im:rating" not in e:
                        continue
                    rating = int(e["im:rating"]["label"])
                    if rating > 3:
                        continue
                    out.append(Signal(
                        source=self.name, kind="review", title=e.get("title", {}).get("label", ""),
                        text=e.get("content", {}).get("label", ""), url=app.get("trackViewUrl", ""),
                        score=float(e.get("im:voteSum", {}).get("label", 0) or 0),
                        created_utc=_ts(e.get("updated", {}).get("label", "")),
                        author=e.get("author", {}).get("name", {}).get("label", ""),
                        meta={"app": app_name, "rating": rating, "app_rating": app.get("averageUserRating"),
                              "app_reviews": app.get("userRatingCount")},
                    ))
        return out


class GooglePlay(Source):
    name = "google_play"
    description = "Google Play low-star reviews of competing Android apps (pip install google-play-scraper)"

    def configured(self) -> tuple[bool, str]:
        try:
            import google_play_scraper  # noqa: F401
        except ImportError:
            return False, "pip install google-play-scraper to enable"
        return True, ""

    def collect(self, ctx: ScanContext) -> list[Signal]:
        from google_play_scraper import Sort, reviews, search

        apps = search(ctx.niche, lang="en", country=ctx.geo.lower(), n_hits=8 if ctx.deep else 5)
        out: list[Signal] = []
        for app in apps:
            app_id = app.get("appId")
            if not app_id:
                continue
            for stars in (1, 2):
                result, _ = reviews(app_id, lang="en", country=ctx.geo.lower(), sort=Sort.MOST_RELEVANT,
                                    count=40 if ctx.deep else 20, filter_score_with=stars)
                for r in result:
                    out.append(Signal(
                        source=self.name, kind="review", title="", text=r.get("content") or "",
                        url=f"https://play.google.com/store/apps/details?id={app_id}",
                        score=float(r.get("thumbsUpCount") or 0),
                        created_utc=r["at"].timestamp() if r.get("at") else None,
                        author=r.get("userName", ""),
                        meta={"app": app.get("title"), "rating": stars, "installs": app.get("installs")},
                    ))
        return out


def _ts(s: str) -> float | None:
    try:
        return datetime.fromisoformat(s).timestamp()
    except (ValueError, TypeError):
        return None
