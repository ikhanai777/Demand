"""Google Trends (unofficial web API, no key).

Produces:
  * momentum  - last-quarter interest vs. the prior 9 months (-1..+1), fed into scoring
  * signals   - rising & top related queries (what people search next to the niche)
Google rate-limits this endpoint aggressively; failures degrade gracefully.
"""
from __future__ import annotations

import json

from ..models import Signal
from .base import ScanContext, Source

BASE = "https://trends.google.com/trends/api"


def _parse(text: str):
    return json.loads(text[text.index("{"):] if "{" in text[:10] else text[text.index("\n") + 1:])


class GoogleTrends(Source):
    name = "google_trends"
    description = "Google Trends interest-over-time momentum + rising related queries (no key)"

    def collect(self, ctx: ScanContext) -> list[Signal]:
        self.http.get("https://trends.google.com/trends/?geo=" + ctx.geo, as_json=False, cache=False)
        req = {"comparisonItem": [{"keyword": ctx.niche, "geo": ctx.geo, "time": "today 5-y"}],
               "category": 0, "property": ""}
        explore = _parse(self.http.get(f"{BASE}/explore", params={"hl": "en-US", "tz": 0, "req": json.dumps(req)},
                                       as_json=False))
        widgets = {w["id"]: w for w in explore.get("widgets", [])}
        signals: list[Signal] = []

        ts = widgets.get("TIMESERIES")
        if ts:
            data = _parse(self.http.get(f"{BASE}/widgetdata/multiline", as_json=False, params={
                "hl": "en-US", "tz": 0, "req": json.dumps(ts["request"]), "token": ts["token"]}))
            values = [p["value"][0] for p in data["default"]["timelineData"] if p.get("value")]
            ctx.extra["trend_series"] = values
            ctx.extra["trend_momentum"] = momentum(values)
            ctx.extra["trend_level"] = round(sum(values[-13:]) / max(1, len(values[-13:])), 1)

        for wid, w in widgets.items():
            if not wid.startswith("RELATED_QUERIES"):
                continue
            data = _parse(self.http.get(f"{BASE}/widgetdata/relatedsearches", as_json=False, params={
                "hl": "en-US", "tz": 0, "req": json.dumps(w["request"]), "token": w["token"]}))
            for idx, ranked in enumerate(data["default"].get("rankedList", [])):
                label = "top" if idx == 0 else "rising"
                for item in ranked.get("rankedKeyword", []):
                    q = item.get("query", "")
                    val = item.get("value", 0)
                    signals.append(Signal(
                        source=self.name, kind="trend", title=q,
                        url="https://trends.google.com/trends/explore?q=" + q.replace(" ", "+"),
                        score=float(min(val, 5000) / 50 if label == "rising" else val / 10),
                        meta={"list": label, "value": item.get("formattedValue", str(val))},
                    ))
        return signals


def momentum(values: list[float]) -> float | None:
    """Compare the last ~13 weeks to the ~39 weeks before (5y weekly series).

    Returns None when search volume is too low for the series to mean anything
    (Google reports mostly zeros with random spikes for tiny queries).
    """
    if len(values) < 26:
        return None
    window = values[-52:]
    if sum(1 for v in window if v == 0) > len(window) * 0.4 or sum(window) / len(window) < 3:
        return None
    recent = values[-13:]
    prior = values[-52:-13]
    a, b = sum(recent) / len(recent), (sum(prior) / len(prior)) or 1e-9
    change = (a - b) / b
    return round(max(-1.0, min(1.0, change)), 3)
